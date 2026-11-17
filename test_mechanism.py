# aid-cut-violence mechanism tests -- Apache-2.0. Made by MV2 of Munim, Inc. with AI agents.
# Offline, standard library only.
import io
import math
import unittest

import aidcut as ac
import mechanism as mc


class Stats(unittest.TestCase):
    x = [0.0, 1.0, 2.0, 3.0]
    y = [0.0, 2.0, 1.0, 3.0]

    def test_ols_hc1_by_hand(self):
        # slope 0.8, intercept 0.3, residuals -.3 .9 -.9 .3;
        # HC1 var = 4/2 * sum(xt^2 u^2) / (sum xt^2)^2 = 2 * 0.81 / 25 = 0.0648
        f = mc.ols_hc1(self.y, [self.x], ["x"])
        self.assertAlmostEqual(f["beta"][0], 0.3, places=10)
        self.assertAlmostEqual(f["beta"][1], 0.8, places=10)
        self.assertAlmostEqual(f["se"][1], math.sqrt(0.0648), places=9)
        self.assertEqual(f["df"], 2)
        self.assertEqual(f["names"], ["const", "x"])
        self.assertAlmostEqual(f["beta"][1], ac.did_closed(self.x, self.y), places=10)

    def test_ols_exact_two_regressors(self):
        a = [0.0, 1.0, 2.0, 3.0, 4.0, 5.0]
        b = [1.0, 0.0, 2.0, 5.0, 3.0, 4.0]
        y = [1.0 + 2.0 * ai - 3.0 * bi for ai, bi in zip(a, b)]
        f = mc.ols_hc1(y, [a, b], ["a", "b"])
        self.assertAlmostEqual(f["beta"][0], 1.0, places=8)
        self.assertAlmostEqual(f["beta"][1], 2.0, places=8)
        self.assertAlmostEqual(f["beta"][2], -3.0, places=8)
        dt = mc.diff_test(f, 1, 2)
        self.assertAlmostEqual(dt["diff"], 5.0, places=8)

    def test_ols_too_small(self):
        with self.assertRaises(ValueError):
            mc.ols_hc1([1.0, 2.0], [[0.0, 1.0]])

    def test_iv_equals_ols_when_z_is_x(self):
        iv = mc.iv_just(self.y, self.x, self.x)
        self.assertAlmostEqual(iv["beta"], 0.8, places=10)
        self.assertAlmostEqual(iv["se"], math.sqrt(0.0648), places=9)
        self.assertEqual(iv["n"], 4)

    def test_iv_recovers_slope(self):
        z = [0.0, 1.0, 2.0, 3.0, 4.0]
        x = [0.5 * v for v in z]
        y = [3.0 + 2.0 * v for v in x]
        self.assertAlmostEqual(mc.iv_just(y, x, z)["beta"], 2.0, places=10)
        with self.assertRaises(ValueError):
            mc.iv_just(y, [1.0] * 5, z)


class Data(unittest.TestCase):
    def test_read_agency(self):
        text = ('"Managing Agency ID","Managing Agency Acronym","Managing Agency Name","Country Code",'
                '"Country Name","Transaction Type ID","Transaction Type Name","Fiscal Year",'
                '"current_amount","constant_amount"\n'
                '1,USAID,U.S. Agency for International Development,AFG,Afghanistan,3,Disbursements,2023,10,20\n'
                '1,USAID,U.S. Agency for International Development,AFG,Afghanistan,3,Disbursements,2023,1,2\n'
                '1,USAID,U.S. Agency for International Development,AFG,Afghanistan,2,Obligations,2025,-4,-4\n'
                '7,DOD,Department of Defense,AFG,Afghanistan,3,Disbursements,2023,50,60\n'
                '9,STATE,Department of State,XKS,Kosovo,3,Disbursements,2024,5,7\n'
                '9,STATE,Department of State,XKS,Kosovo,1,Appropriated and Planned,2024,5,7\n')
        out, agencies = mc.read_agency(ac.iter_csv_rows(io.StringIO(text)))
        self.assertEqual(out[("usaid", "disb")]["AFG"][2023], 22.0)
        self.assertEqual(out[("usaid", "oblig")]["AFG"][2025], -4.0)
        self.assertEqual(out[("other", "disb")]["AFG"][2023], 60.0)
        self.assertEqual(out[("other", "disb")]["XKX"][2024], 7.0)
        self.assertEqual(agencies["USAID"], 3)
        self.assertEqual(agencies["STATE"], 1)

    def test_sector_group(self):
        cases = {"Humanitarian Assistance": "humanitarian", "Health": "health",
                 "Health and Population": "health",
                 "Democracy, Human Rights, and Governance": "governance",
                 "Peace and Security": "peace_security", "Economic Development": "other",
                 "Education and Social Services": "other", "": "other"}
        for name, g in cases.items():
            self.assertEqual(mc.sector_group(name), g, name)

    def test_pick_column(self):
        keys = ["country code", "us sector name", "us category name"]
        self.assertEqual(mc.pick_column(keys, [("category", "name")]), "us category name")
        self.assertIsNone(mc.pick_column(["a", "b"], [("category", "name")]))

    def test_read_sector(self):
        text = ("Country Code,Country Name,US Category ID,US Category Name,US Sector Name,"
                "Transaction Type Name,Fiscal Year,current_amount,constant_amount\n"
                "SDN,Sudan,1,Humanitarian Assistance,Emergency Response,Disbursements,2023,1,100\n"
                "SDN,Sudan,2,Health,HIV/AIDS,Disbursements,2023,1,50\n"
                "SDN,Sudan,2,Health,HIV/AIDS,Obligations,2023,1,999\n"
                "SDN,Sudan,3,Peace and Security,Counter-Terrorism,Disbursements,2024,1,30\n")
        out, info = mc.read_sector(ac.iter_csv_rows(io.StringIO(text)))
        self.assertTrue(info["usable"])
        self.assertEqual(info["column"], "us category name")
        self.assertEqual(out["humanitarian"]["SDN"][2023], 100.0)
        self.assertEqual(out["health"]["SDN"][2023], 50.0)
        self.assertEqual(out["peace_security"]["SDN"][2024], 30.0)
        self.assertEqual(info["names"]["Health"], [1, "health"])

    def test_read_sector_unusable(self):
        text = "Region,Sector Name,Transaction Type Name,Fiscal Year,constant_amount\nX,Y,Disbursements,2023,1\n"
        out, info = mc.read_sector(ac.iter_csv_rows(io.StringIO(text)))
        self.assertFalse(info["usable"])
        self.assertIsNone(info["column"])

    def test_per_person(self):
        series = {"KEN": {2022: 3e6, 2023: 3e6, 2024: 0.0}, "TCD": {2022: -5.0}}
        pp = mc.per_person(series, {"KEN": 1e6, "TCD": 1e6, "MLI": 2e6, "XXX": 0}, (2022, 2023, 2024))
        self.assertAlmostEqual(pp["KEN"], 2.0)
        self.assertEqual(pp["TCD"], 0.0)
        self.assertEqual(pp["MLI"], 0.0)
        self.assertNotIn("XXX", pp)


class EndToEnd(unittest.TestCase):
    ISOS = ["AAA", "BBB", "CCC", "DDD", "EEE", "FFF", "GGG", "HHH"]

    def build(self):
        pop = {u: 2e6 for u in self.ISOS}
        meta = {u: {"name": u, "region": "SSF" if k < 4 else "EAS", "income": "LIC"}
                for k, u in enumerate(self.ISOS)}
        lines = ['"Managing Agency Acronym","Country Code","Transaction Type Name","Fiscal Year",'
                 '"constant_amount"']
        sec = ["Country Code,US Category Name,Transaction Type Name,Fiscal Year,constant_amount"]
        cats = ["Humanitarian Assistance", "Health", "Democracy, Human Rights, and Governance",
                "Peace and Security", "Economic Development"]
        for k, u in enumerate(self.ISOS):
            for fy in range(2020, 2026):
                usaid = (k + 1) * 1e6 * (0.3 if fy == 2025 else 1.0)
                other = ((3 * k) % 8 + 1) * 1e6
                lines.append("USAID,%s,Disbursements,%d,%f" % (u, fy, usaid))
                lines.append("DOD,%s,Disbursements,%d,%f" % (u, fy, other))
                for g, cat in enumerate(cats):
                    v = (1 + ((k + 1) * (g + 1)) % 7) * 1e6
                    sec.append('%s,"%s",Disbursements,%d,%f' % (u, cat, fy, v))
        agency, _ = mc.read_agency(ac.iter_csv_rows(io.StringIO("\n".join(lines) + "\n")))
        sector, info = mc.read_sector(ac.iter_csv_rows(io.StringIO("\n".join(sec) + "\n")))
        self.assertTrue(info["usable"])
        counts = {}
        shock = ac.parse_ym("2025-02")
        for k, u in enumerate(self.ISOS):
            for m in range(ac.parse_ym("2021-02"), ac.parse_ym("2026-09") + 1):
                ev = 1 + (k + m) % 3 + (k if m >= shock else 0)
                counts[(u, m)] = [ev, 2 * ev, ev, 0, 0]
        return counts, pop, meta, agency, sector

    def test_analyze_runs(self):
        counts, pop, meta, agency, sector = self.build()
        res = mc.analyze(counts, pop, meta, agency, sector, reps=99)
        self.assertEqual(res["descriptive"]["sample_sizes"], {"global": 8, "africa": 4, "rest": 4})
        self.assertAlmostEqual(res["descriptive"]["usaid_fy2025_over_pre"], 0.3, places=9)
        m = res["models"]
        for key in ("A1|primary|global|events", "A2|primary|global|events",
                    "A1|extended|global|deaths", "D1|placebo|global|events",
                    "B|primary|global|events", "A2|primary|africa|deaths"):
            self.assertIn(key, m)
            self.assertNotIn("error", m[key], key)
        a1 = m["A1|primary|global|events"]
        self.assertTrue(0.0 < a1["p_ri"] <= 1.0)
        self.assertIn("leave_one_out", a1)
        self.assertGreater(m["B|primary|global|events"]["first_stage"]["slope"], 0.0)
        self.assertIn("C|primary|global|events", m)
        for key in sorted(m):
            self.assertTrue(mc.summarize(key, m[key]).startswith("- " + key))

    def test_analyze_without_sector(self):
        counts, pop, meta, agency, _ = self.build()
        res = mc.analyze(counts, pop, meta, agency, None, reps=19)
        self.assertEqual(res["models"]["C|primary|global|events"],
                         {"skipped": "no usable sector file"})


if __name__ == "__main__":
    unittest.main()
