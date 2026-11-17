# aid-cut-violence forecast tests -- Apache-2.0. Made by MV2 of Munim, Inc. with AI agents.
# Offline, standard library only.
import io
import json
import math
import os
import shutil
import tempfile
import unittest

import aidcut as ac
import forecast as fv
import mechanism as mc


class Basics(unittest.TestCase):
    def test_window_and_years(self):
        f, l = fv.window(2025)
        self.assertEqual(ac.ym_str(f), "2025-02")
        self.assertEqual(ac.ym_str(l), "2025-12")
        self.assertEqual(fv.exposure_years(2025), (2022, 2023, 2024))
        self.assertEqual(fv.exposure_years(2024), (2021, 2022, 2023))

    def test_url(self):
        self.assertEqual(fv.views_url("fatalities002_2025_01_t01"),
                         "https://api.viewsforecasting.org/fatalities002_2025_01_t01/cm/sb"
                         "?pagesize=10000")
        self.assertTrue(fv.views_url("r", 2).endswith("&page=2"))

    def test_read_views_field_styles(self):
        new = {"data": [
            {"isoab": "COD", "year": 2025, "month": 2, "main_mean": 360.9561,
             "main_mean_ln": 5.8915, "main_dich": 0.9958},
            {"isoab": "GUY", "year": 2025, "month": 2, "main_mean": 0.0086}]}
        old = {"data": [
            {"isoab": "SOM", "year": 2023, "month": 2, "sc_cm_sb_main": 6.7289,
             "sc_cm_sb_dich_main": 0.9983},
            {"isoab": "", "year": 2023, "month": 2, "sc_cm_sb_main": 1.0},
            {"isoab": "MLI", "year": "x", "month": 2, "sc_cm_sb_main": 1.0},
            {"isoab": "NER", "year": 2023, "month": 2, "sc_cm_sb_main": None}]}
        fc, info = fv.read_views([new, old])
        self.assertEqual(fc[("COD", ac.ym_index(2025, 2))], (5.8915, 0.9958))
        ln, p = fc[("GUY", ac.ym_index(2025, 2))]
        self.assertAlmostEqual(ln, math.log1p(0.0086))
        self.assertIsNone(p)
        self.assertEqual(fc[("SOM", ac.ym_index(2023, 2))], (6.7289, 0.9983))
        self.assertEqual(info["rows"], 3)
        self.assertEqual(info["bad_rows"], 3)
        self.assertEqual(info["fields"]["main_mean_ln"], 1)
        self.assertEqual(info["fields"]["log1p(main_mean)"], 1)
        self.assertEqual(info["fields"]["sc_cm_sb_main"], 1)
        self.assertAlmostEqual(info["max_ln"], 6.7289)
        self.assertEqual(info["first_month"], "2023-02")
        self.assertEqual(info["last_month"], "2025-02")

    def test_fetch_follows_pages(self):
        tmp = tempfile.mkdtemp()
        pages = {
            fv.views_url("run"): {"next_page": fv.views_url("run", 2),
                                  "data": [{"isoab": "KEN", "year": 2025, "month": 2,
                                            "main_mean_ln": 1.0}]},
            fv.views_url("run", 2): {"next_page": "",
                                     "data": [{"isoab": "KEN", "year": 2025, "month": 3,
                                               "main_mean_ln": 2.0}]}}
        seen = []

        def fake_download(url, path, tries=4):
            seen.append(url)
            with open(path, "w", encoding="utf-8") as fh:
                json.dump(pages[url], fh)
            return path

        orig = mc.download
        mc.download = fake_download
        try:
            docs = fv.fetch_views("run", tmp)
        finally:
            mc.download = orig
            shutil.rmtree(tmp)
        self.assertEqual(len(docs), 2)
        self.assertEqual(seen, [fv.views_url("run"), fv.views_url("run", 2)])
        fc, _ = fv.read_views(docs)
        self.assertEqual(len(fc), 2)

    def test_count_sb(self):
        csv_text = ("type_of_violence,country,date_start,best\n"
                    "1,Somalia,2025-03-04,10\n"
                    "1,Somalia,2025-03-20 00:00:00.000,5\n"
                    "2,Somalia,2025-03-04,100\n"
                    "3,Somalia,2025-03-04,100\n"
                    "1,DR Congo (Zaire),2025-03-01,7\n"
                    "1,Atlantis,2025-03-01,9\n"
                    "1,Somalia,2021-03-01,50\n")
        rows = ac.iter_csv_rows(io.StringIO(csv_text))
        out, unmatched = fv.count_sb(rows, ac.parse_ym("2022-02"), ac.parse_ym("2025-12"))
        m = ac.ym_index(2025, 3)
        self.assertEqual(out[("SOM", m)], 15)
        self.assertEqual(out[("COD", m)], 7)
        self.assertEqual(unmatched["Atlantis"], 1)
        self.assertNotIn(("SOM", ac.ym_index(2021, 3)), out)

    def test_country_errors(self):
        f, l = ac.ym_index(2025, 2), ac.ym_index(2025, 3)
        fc = {("A", f): (math.log1p(10), 0.5), ("A", l): (math.log1p(10), 0.5),
              ("B", f): (0.0, None), ("B", l): (0.0, 0.1), ("C", f): (1.0, 0.2)}
        actual = {("A", f): 30, ("A", l): 10, ("B", l): 3}
        out, missing = fv.country_errors(fc, actual, ["A", "B", "C"], f, l)
        self.assertEqual(missing, ["C"])
        self.assertAlmostEqual(out["A"]["e"], 0.5 * (math.log1p(30) - math.log1p(10)))
        self.assertAlmostEqual(out["A"]["ed"], 0.5 * ((1 - 0.5) + (0 - 0.5)))
        self.assertAlmostEqual(out["A"]["a_sum"], 40.0)
        self.assertAlmostEqual(out["A"]["f_sum"], 20.0)
        self.assertIsNone(out["B"]["ed"])
        self.assertAlmostEqual(out["B"]["e"], 0.5 * math.log1p(3))

    def test_terciles_quantile_corr(self):
        self.assertEqual(fv.terciles([5.0, 1.0, 3.0, 2.0, 4.0, 0.0]), [2, 0, 1, 1, 2, 0])
        self.assertEqual(fv.quantile([3.0, 1.0, 2.0], 0.5), 2.0)
        self.assertAlmostEqual(fv.corr([1.0, 2.0, 3.0, 4.0], [1.0, 3.0, 2.0, 4.0]), 0.8)
        with self.assertRaises(ValueError):
            fv.corr([1.0, 1.0, 1.0], [1.0, 2.0, 3.0])


class EndToEnd(unittest.TestCase):
    N = 70

    def build(self, effect=True):
        isos = ["C%02d" % k for k in range(self.N)]
        pop = {u: 2e6 for u in isos}
        meta = {u: {"name": u, "region": ("SSF", "EAS", "LCR")[k % 3], "income": "LIC"}
                for k, u in enumerate(isos)}
        lines = ['"Managing Agency Acronym","Country Code","Transaction Type Name",'
                 '"Fiscal Year","constant_amount"']
        for k, u in enumerate(isos):
            for fy in range(2018, 2026):
                lines.append("USAID,%s,Disbursements,%d,%f" % (u, fy, (1 + k % 7) * 1e6))
        agency, _ = mc.read_agency(ac.iter_csv_rows(io.StringIO("\n".join(lines) + "\n")))
        shock = ac.parse_ym("2025-02")
        actual = {}
        for k, u in enumerate(isos):
            for m in range(ac.parse_ym("2022-02"), ac.parse_ym("2026-09") + 1):
                bump = 4 * (k % 7) if (effect and m >= shock) else 0
                actual[(u, m)] = 5 + (k + m) % 4 + bump + (30 if k % 5 == 0 else 0)
        fcs = {}
        for o in (2022, 2023, 2024, 2025):
            first = ac.ym_index(o, 2)
            fcs[o] = {(u, m): (math.log1p(6.5 + (30 if k % 5 == 0 else 0)), 0.3)
                      for k, u in enumerate(isos) for m in range(first, first + 36)}
        return actual, fcs, pop, meta, agency

    def test_analyze_runs(self):
        actual, fcs, pop, meta, agency = self.build()
        res = fv.analyze(actual, fcs, pop, meta, agency, reps=49,
                         ext_last=ac.parse_ym("2026-09"))
        self.assertNotIn("stopped", res)
        self.assertEqual(res["descriptive"]["sample_sizes"]["global"], self.N)
        m = res["models"]
        for key in ("F1|global", "F2|global", "F2|africa", "F2|rest", "F2r|global",
                    "F2b|global", "F3|global|2024", "F3|africa|2023", "F3|global|2022",
                    "F3d|global|2024-2023", "F3d|global|2023-2022", "F4|global",
                    "F5|global", "F6|global", "F6d|global"):
            self.assertIn(key, m)
            self.assertNotIn("error", m[key], key)
        self.assertGreater(m["F2|global"]["beta"], 0.0)
        self.assertLess(m["F2|global"]["p_ri"], 0.05)
        self.assertIn("leave_one_out", m["F2|global"])
        self.assertAlmostEqual(m["F2|global"]["beta"], m["F2|global"]["beta_ols"], places=8)
        self.assertGreater(m["F6|global"]["beta"], 0.0)
        agg = res["descriptive"]["aggregate_by_E_tercile"]
        self.assertGreater(agg["2025|tercile3"]["actual_sb_deaths"],
                           agg["2024|tercile3"]["actual_sb_deaths"])
        for key in sorted(m):
            self.assertTrue(fv.summarize(key, m[key]).startswith("- " + key))

    def test_no_effect_placebo_is_flat(self):
        actual, fcs, pop, meta, agency = self.build(effect=False)
        res = fv.analyze(actual, fcs, pop, meta, agency, reps=49)
        self.assertLess(abs(res["models"]["F2|global"]["beta"]), 0.05)
        self.assertIn("error", res["models"]["F6|global"])

    def test_stops_when_runs_missing(self):
        actual, fcs, pop, meta, agency = self.build()
        del fcs[2024]
        res = fv.analyze(actual, fcs, pop, meta, agency, reps=9)
        self.assertIn("stopped", res)

    def test_stops_when_too_few(self):
        actual, fcs, pop, meta, agency = self.build()
        small = {o: {k: v for k, v in fc.items() if k[0] < "C20"} for o, fc in fcs.items()}
        res = fv.analyze(actual, small, pop, meta, agency, reps=9)
        self.assertIn("stopped", res)


if __name__ == "__main__":
    unittest.main()
