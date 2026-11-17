# aid-cut-violence dose tests -- Apache-2.0. Made by MV2 of Munim, Inc. with AI agents.
# Offline, standard library only.
import io
import math
import unittest

import aidcut as ac
import dose as ds
import mechanism as mc

HTML = """<html><body>
<table><tr><th>Sector</th><th>Cut</th></tr><tr><td>Health</td><td>40%</td></tr></table>
<p>Table 2. Country cuts data</p>
<table>
 <thead><tr><th>Country</th><th>Cut as % country program</th><th>Cut as % GNI</th>
 <th>Absolute cut ($m)</th></tr></thead>
 <tbody>
 <tr><td>Ukraine</td><td>15</td><td>0.78</td><td>1,433</td></tr>
 <tr><td>Democratic Republic of the Congo</td><td>34%</td><td>0.6</td><td>387</td></tr>
 <tr><td><strong>C&ocirc;te d&#8217;Ivoire</strong></td><td>12</td><td>0.01</td><td>9</td></tr>
 <tr><td>Burma</td><td>100</td><td>NA</td><td>120</td></tr>
 <tr><td>Atlantis</td><td>50</td><td>1</td><td>5</td></tr>
 <tr><td>Kyrgyz Republic</td><td></td><td>0.2</td><td>20</td></tr>
 <tr><td>Total</td><td>38</td><td></td><td>2,000</td></tr>
 </tbody>
</table></body></html>"""


class Table(unittest.TestCase):
    def test_parse(self):
        rows = ds.parse_cut_table(HTML)
        self.assertEqual([r["name"] for r in rows],
                         ["Ukraine", "Democratic Republic of the Congo", "Côte d’Ivoire",
                          "Burma", "Atlantis", "Kyrgyz Republic"])
        self.assertEqual(rows[0]["pct"], 15.0)
        self.assertEqual(rows[0]["cut_musd"], 1433.0)
        self.assertEqual(rows[0]["gni"], 0.78)
        self.assertEqual(rows[1]["pct"], 34.0)
        self.assertIsNone(rows[3]["gni"])
        self.assertIsNone(rows[5]["pct"])

    def test_no_table(self):
        self.assertEqual(ds.parse_cut_table("<html><p>blocked</p></html>"), [])

    def test_unclosed_cells(self):
        html = ("<table><tr><td>Country<td>Cut as % country program<td>Absolute cut ($m)"
                "<tr><td>Kenya<td>46<td>225</table>")
        rows = ds.parse_cut_table(html)
        self.assertEqual(rows, [{"name": "Kenya", "pct": 46.0, "gni": None, "cut_musd": 225.0}])

    def test_num(self):
        self.assertEqual(ds.num("1,433"), 1433.0)
        self.assertEqual(ds.num(" 15% "), 15.0)
        self.assertIsNone(ds.num("NA"))
        self.assertIsNone(ds.num(""))
        self.assertIsNone(ds.num("n/a"))

    def test_names(self):
        wb = ds.wb_name_map({"EGY": {"name": "Egypt, Arab Rep."}, "GMB": {"name": "Gambia, The"}})
        cases = {"Côte d’Ivoire": "CIV", "Burma": "MMR", "Kyrgyz Republic": "KGZ",
                 "Democratic Republic of the Congo": "COD", "Congo (Kinshasa)": "COD",
                 "Egypt, Arab Rep.": "EGY", "Kenya": "KEN", "West Bank and Gaza": "PSE",
                 "Atlantis": None, "Laos": "LAO", "Tanzania": "TZA"}
        for name, iso in cases.items():
            self.assertEqual(ds.iso_for(name, wb), iso, name)

    def test_build_dose(self):
        dose, info = ds.build_dose(ds.parse_cut_table(HTML))
        self.assertEqual(sorted(dose), ["CIV", "COD", "MMR", "UKR"])
        self.assertAlmostEqual(dose["COD"]["share"], 0.34)
        self.assertAlmostEqual(dose["COD"]["cut_usd"], 387e6)
        self.assertAlmostEqual(dose["COD"]["retained_usd"], 387e6 * 66 / 34)
        self.assertAlmostEqual(dose["MMR"]["retained_usd"], 0.0)
        self.assertEqual(info["unmatched"], [["Atlantis", 5.0]])
        self.assertEqual(info["missing_values"], ["Kyrgyz Republic"])
        self.assertAlmostEqual(info["unmatched_cut_share"], 5.0 / (1433 + 387 + 9 + 120 + 5 + 20))


class Stats(unittest.TestCase):
    def test_coef_matches_ols(self):
        a = [0.0, 1.0, 2.0, 3.0, 4.0, 5.0]
        b = [1.0, 0.0, 2.0, 5.0, 3.0, 4.0]
        y = [0.5, 1.0, 3.0, 2.0, 6.0, 4.0]
        f = mc.ols_hc1(y, [a, b])
        self.assertAlmostEqual(ds.coef(y, [a, b], 1), f["beta"][1], places=10)
        self.assertAlmostEqual(ds.coef(y, [a, b], 2), f["beta"][2], places=10)
        with self.assertRaises(ValueError):
            ds.coef([1.0, 2.0], [[0.0, 1.0]])

    def test_strata(self):
        self.assertEqual(ds.strata_by_quantile([5.0, 1.0, 3.0, 2.0, 4.0, 0.0], 3),
                         [2, 0, 1, 1, 2, 0])

    def test_ri(self):
        S = [0.1, 0.9, 0.4, 0.7, 0.2, 0.8, 0.5, 0.3, 0.6]
        E = [1.0, 1.0, 1.0, 2.0, 2.0, 2.0, 3.0, 3.0, 3.0]
        y = [2.0 * s + 0.1 * e for s, e in zip(S, E)]
        b, p, done = ds.ri_coef(y, S, [E], [0, 0, 0, 1, 1, 1, 2, 2, 2], reps=199)
        self.assertAlmostEqual(b, 2.0, places=8)
        self.assertEqual(done, 199)
        self.assertLess(p, 0.05)
        b2, p2, _ = ds.ri_coef([1.0] * 9, S, [E], [0] * 9, reps=99)
        self.assertAlmostEqual(b2, 0.0, places=8)
        self.assertEqual(p2, 1.0)

    def test_corr(self):
        c = ds.corr([1.0, 2.0, 3.0, 4.0], [2.0, 4.0, 6.0, 8.0])
        self.assertAlmostEqual(c["r"], 1.0)
        c = ds.corr([1.0, 2.0, 3.0, 4.0], [1.0, 3.0, 2.0, 4.0])
        self.assertAlmostEqual(c["r"], 0.8)
        with self.assertRaises(ValueError):
            ds.corr([1.0, 1.0, 1.0], [1.0, 2.0, 3.0])


class EndToEnd(unittest.TestCase):
    N = 44

    def build(self):
        isos = ["C%02d" % k for k in range(self.N)]
        pop = {u: 2e6 for u in isos}
        meta = {u: {"name": u, "region": "SSF" if k % 2 else "EAS", "income": "LIC"}
                for k, u in enumerate(isos)}
        lines = ['"Managing Agency Acronym","Country Code","Transaction Type Name",'
                 '"Fiscal Year","constant_amount"']
        dose = {}
        counts = {}
        shock = ac.parse_ym("2025-02")
        for k, u in enumerate(isos):
            for fy in range(2020, 2026):
                lines.append("USAID,%s,Disbursements,%d,%f" % (u, fy, (1 + k % 7) * 1e6))
            share = ((k * 37) % 100 + 1) / 101.0
            dose[u] = {"name": u, "share": share, "cut_usd": share * 1e7,
                       "retained_usd": (1 - share) * 1e7 if k % 5 else None, "gni_pct": None}
            for m in range(ac.parse_ym("2021-02"), ac.parse_ym("2026-09") + 1):
                ev = 1 + (k + m) % 3 + k % 4 + (int(4 * share) if m >= shock else 0)
                counts[(u, m)] = [ev, 2 * ev, ev, 0, 0]
        agency, _ = mc.read_agency(ac.iter_csv_rows(io.StringIO("\n".join(lines) + "\n")))
        return counts, pop, meta, agency, dose

    def test_analyze_runs(self):
        counts, pop, meta, agency, dose = self.build()
        res = ds.analyze(counts, pop, meta, agency, dose, reps=49)
        self.assertNotIn("stopped", res)
        self.assertEqual(res["descriptive"]["sample_sizes"], {"global": 44, "africa": 22,
                                                              "rest": 22})
        m = res["models"]
        for key in ("T1|primary|global|events", "T1|primary|africa|deaths",
                    "T1|extended|global|events", "T1|placebo|rest|events",
                    "T1v|primary|global|events", "T2|primary|global|deaths",
                    "T3|primary|global|events", "D|corr_S_pre_events", "D|corr_S_E_usaid"):
            self.assertIn(key, m)
            self.assertNotIn("error", m[key], key)
        t1 = m["T1|primary|global|events"]
        self.assertGreater(t1["beta_S"], 0.0)
        self.assertIn("leave_one_out", t1)
        self.assertEqual(m["T3|primary|global|events"]["fit"]["n"], 44 - 9)
        for key in sorted(m):
            self.assertTrue(ds.summarize(key, m[key]).startswith("- " + key))

    def test_stops_when_too_few(self):
        counts, pop, meta, agency, dose = self.build()
        small = {u: dose[u] for u in sorted(dose)[:10]}
        res = ds.analyze(counts, pop, meta, agency, small, reps=9)
        self.assertIn("stopped", res)


if __name__ == "__main__":
    unittest.main()
