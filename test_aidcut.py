# aid-cut-violence tests -- Apache-2.0. Made by MV2 of Munim, Inc. with AI agents.
# Offline, standard library only.
import io
import math
import random
import unittest
from collections import defaultdict

import aidcut as ac


def dummy_ols(Y, X, groups):
    """Brute-force OLS with explicit unit and group-by-month dummies (coefficient on X)."""
    n, T = len(Y), len(Y[0])
    gl = sorted(set(groups))
    rows, ys = [], []
    for i in range(n):
        for t in range(T):
            r = [X[i][t]]
            r += [1.0 if j == i else 0.0 for j in range(n)]
            for g in gl:
                for s in range(1, T):
                    r.append(1.0 if (groups[i] == g and t == s) else 0.0)
            rows.append(r)
            ys.append(Y[i][t])
    K = len(rows[0])
    XtX = [[sum(r[a] * r[b] for r in rows) for b in range(K)] for a in range(K)]
    Xty = [sum(r[a] * y for r, y in zip(rows, ys)) for a in range(K)]
    return ac.solve(XtX, Xty)[0]


class Months(unittest.TestCase):
    def test_parse(self):
        self.assertEqual(ac.parse_month("2025-01-03 00:00:00.000"), ac.ym_index(2025, 1))
        self.assertEqual(ac.parse_month("2025-12-31"), ac.ym_index(2025, 12))
        self.assertEqual(ac.ym_str(ac.ym_index(2025, 2)), "2025-02")
        self.assertEqual(ac.parse_ym("2026-09"), ac.ym_index(2026, 9))
        with self.assertRaises(ValueError):
            ac.parse_month("")

    def test_bins(self):
        s = ac.parse_ym("2025-02")
        self.assertEqual(ac.event_bin(ac.parse_ym("2025-02"), s), 0)
        self.assertEqual(ac.event_bin(ac.parse_ym("2025-04"), s), 0)
        self.assertEqual(ac.event_bin(ac.parse_ym("2025-05"), s), 1)
        self.assertEqual(ac.event_bin(ac.parse_ym("2025-01"), s), -1)
        self.assertEqual(ac.event_bin(ac.parse_ym("2024-11"), s), -1)
        self.assertEqual(ac.event_bin(ac.parse_ym("2024-10"), s), -2)
        self.assertEqual(ac.event_bin(ac.parse_ym("2023-02"), s), -8)
        self.assertEqual(ac.event_bin(ac.parse_ym("2025-12"), s), 3)


class Names(unittest.TestCase):
    def test_ucdp_names(self):
        cases = {"DR Congo (Zaire)": "COD", "Myanmar (Burma)": "MMR",
                 "Yemen (North Yemen)": "YEM", "Ivory Coast": "CIV",
                 "Kingdom of eSwatini (Swaziland)": "SWZ", "Russia (Soviet Union)": "RUS",
                 "Sudan": "SDN", "South Sudan": "SSD", "Congo": "COG",
                 "Cambodia (Kampuchea)": "KHM", "Zimbabwe (Rhodesia)": "ZWE",
                 "Madagascar (Malagasy)": "MDG", "Bosnia-Herzegovina": "BIH",
                 "Serbia (Yugoslavia)": "SRB", "Burkina Faso": "BFA", "Haiti": "HTI"}
        for name, iso in cases.items():
            self.assertEqual(ac.ged_iso3(name), iso, name)
        self.assertIsNone(ac.ged_iso3("Atlantis"))
        self.assertIsNone(ac.ged_iso3(""))


class Distributions(unittest.TestCase):
    def test_t(self):
        self.assertAlmostEqual(ac.t_two_sided_p(2.0, 10), 0.07339, places=4)
        self.assertAlmostEqual(ac.t_two_sided_p(1.959964, 10 ** 4), 0.05, places=3)
        self.assertAlmostEqual(ac.t_two_sided_p(0.0, 5), 1.0, places=9)
        self.assertTrue(math.isnan(ac.t_two_sided_p(float("nan"), 5)))

    def test_chi2_f(self):
        self.assertAlmostEqual(ac.chi2_sf(3.841458820694124, 1), 0.05, places=6)
        self.assertAlmostEqual(ac.chi2_sf(0.5, 4), 0.973500, places=5)
        self.assertAlmostEqual(ac.chi2_sf(18.307038, 10), 0.05, places=5)
        self.assertAlmostEqual(ac.f_sf(4.964603, 1, 10), 0.05, places=5)
        self.assertEqual(ac.f_sf(0.0, 2, 10), 1.0)


class Estimators(unittest.TestCase):
    def setUp(self):
        self.rng = random.Random(1)

    def rand_panel(self, n, T):
        return [[self.rng.gauss(0, 1) for _ in range(T)] for _ in range(n)]

    def test_demean_matches_dummies(self):
        Y = self.rand_panel(6, 5)
        X = self.rand_panel(6, 5)
        for groups in (None, [0, 0, 0, 1, 1, 1]):
            b = ac.fe_ols(Y, [X], groups)["beta"][0]
            ref = dummy_ols(Y, X, groups if groups is not None else [0] * 6)
            self.assertAlmostEqual(b, ref, places=8)

    def test_closed_form(self):
        n, T, shock = 8, 6, 3
        Y = self.rand_panel(n, T)
        E = [self.rng.uniform(0, 3) for _ in range(n)]
        X = [[E[i] * (1.0 if t >= shock else 0.0) for t in range(T)] for i in range(n)]
        d = ac.deltas(Y, 0, T - 1, shock)
        for groups in (None, [0, 0, 1, 1, 1, 2, 2, 2]):
            b = ac.fe_ols(Y, [X], groups)["beta"][0]
            self.assertAlmostEqual(b, ac.did_closed(E, d, groups), places=9)

    def test_recovers_effect(self):
        n, T, shock = 60, 24, 12
        E = [self.rng.uniform(0, 3) for _ in range(n)]
        a = [self.rng.gauss(0, 2) for _ in range(n)]
        g = [self.rng.gauss(0, 1) for _ in range(T)]
        Y = [[a[i] + g[t] + 0.3 * E[i] * (t >= shock) + self.rng.gauss(0, 0.1)
              for t in range(T)] for i in range(n)]
        b = ac.did_closed(E, ac.deltas(Y, 0, T - 1, shock))
        self.assertLess(abs(b - 0.3), 0.03)

    def test_ri(self):
        E = [float(i) for i in range(20)]
        b, p = ac.ri_pvalue(E, list(E), reps=199)
        self.assertAlmostEqual(b, 1.0, places=9)
        self.assertAlmostEqual(p, 1.0 / 200.0, places=12)
        noise = [self.rng.gauss(0, 1) for _ in range(20)]
        b, p = ac.ri_pvalue(E, noise, reps=199)
        self.assertTrue(0.0 < p <= 1.0)


class Data(unittest.TestCase):
    def test_iter_csv_rows_keeps_first_row(self):
        text = chr(0xFEFF) + "ID,Country,Date_Start\n1,Sudan,2025-01-02\n2,Chad,2025-03-01\n"
        rows = list(ac.iter_csv_rows(io.StringIO(text)))
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0], {"id": "1", "country": "Sudan", "date_start": "2025-01-02"})

    def test_count_events(self):
        rows = [
            {"country": "DR Congo (Zaire)", "date_start": "2025-02-03 00:00:00.000",
             "best": "5", "type_of_violence": "1"},
            {"country": "DR Congo (Zaire)", "date_start": "2025-02-20", "best": "0",
             "type_of_violence": "3"},
            {"country": "Atlantis", "date_start": "2025-02-01", "best": "1",
             "type_of_violence": "2"},
            {"country": "Sudan", "date_start": "2019-01-01", "best": "9",
             "type_of_violence": "1"},
            {"country": "Sudan", "date_start": "", "best": "9", "type_of_violence": "1"},
        ]
        counts, unmatched, by_year = ac.count_events(rows, ac.parse_ym("2021-02"),
                                                     ac.parse_ym("2025-12"))
        self.assertEqual(counts[("COD", ac.parse_ym("2025-02"))], [2, 5, 1, 0, 1])
        self.assertEqual(dict(unmatched), {"Atlantis": 1})
        self.assertNotIn(("SDN", ac.parse_ym("2019-01")), counts)
        self.assertEqual(by_year[2025], 2)

    def test_fa_and_exposure(self):
        rows = []
        for fy in (2022, 2023, 2024):
            rows.append({"country code": "KEN", "transaction type name": "Disbursements",
                         "fiscal year": str(fy), "constant_amount": "1000000"})
            rows.append({"country code": "KEN", "transaction type name": "Obligations",
                         "fiscal year": str(fy), "constant_amount": "9000000"})
        rows.append({"country code": "KEN", "transaction type name": "Disbursements",
                     "fiscal year": "2019", "constant_amount": "5e9"})
        rows.append({"country code": "XKS", "transaction type name": "Disbursements",
                     "fiscal year": "2023", "constant_amount": "3000000"})
        fa, types = ac.read_fa(rows)
        self.assertEqual(types["Disbursements"], 5)
        E, pc = ac.exposure(fa["disb"], {"KEN": 1e6, "XKX": 1e6, "TCD": 2e6})
        self.assertAlmostEqual(pc["KEN"], 1.0)
        self.assertAlmostEqual(E["KEN"], math.log(2.0))
        self.assertAlmostEqual(pc["XKX"], 1.0)
        self.assertEqual(pc["TCD"], 0.0)
        Eo, pco = ac.exposure(fa["oblig"], {"KEN": 1e6})
        self.assertAlmostEqual(pco["KEN"], 9.0)

    def test_wb_and_sample(self):
        pop_json = [{}, [{"countryiso3code": "KEN", "value": 5e7},
                         {"countryiso3code": "EGY", "value": 1e8},
                         {"countryiso3code": "USA", "value": 3e8},
                         {"countryiso3code": "UKR", "value": 4e7},
                         {"countryiso3code": "TUV", "value": 1e4},
                         {"countryiso3code": "WLD", "value": 8e9}]]
        meta_json = [{}, [
            {"id": "KEN", "name": "Kenya", "region": {"id": "SSF", "value": "Sub-Saharan Africa"},
             "incomeLevel": {"id": "LMC"}},
            {"id": "EGY", "name": "Egypt", "region": {"id": "MEA", "value": "Middle East"},
             "incomeLevel": {"id": "LMC"}},
            {"id": "USA", "name": "United States", "region": {"id": "NAC", "value": "NA"},
             "incomeLevel": {"id": "HIC"}},
            {"id": "UKR", "name": "Ukraine", "region": {"id": "ECS", "value": "Europe"},
             "incomeLevel": {"id": "UMC"}},
            {"id": "TUV", "name": "Tuvalu", "region": {"id": "EAS", "value": "East Asia"},
             "incomeLevel": {"id": "UMC"}},
            {"id": "WLD", "name": "World", "region": {"id": "NA", "value": "Aggregates"},
             "incomeLevel": {"id": "NA"}}]]
        pop, meta = ac.read_wb(pop_json, meta_json)
        self.assertNotIn("WLD", meta)
        self.assertEqual(ac.build_sample(pop, meta), ["EGY", "KEN"])
        self.assertEqual(ac.build_sample(pop, meta, exclude=()), ["EGY", "KEN", "UKR"])
        self.assertTrue(ac.is_africa("EGY", meta))
        self.assertTrue(ac.is_africa("KEN", meta))
        self.assertFalse(ac.is_africa("UKR", meta))


class EndToEnd(unittest.TestCase):
    def make_counts(self, units, first, last, shock, E):
        rng = random.Random(7)
        counts = defaultdict(lambda: [0, 0, 0, 0, 0])
        for i, u in enumerate(units):
            for m in range(first, last + 1):
                lam = 2 + 3 * E[i] * (m >= shock) + rng.randint(0, 3)
                c = counts[(u, m)]
                c[0] = lam
                c[1] = 2 * lam
                c[2] = lam
        return counts

    def test_pooled_and_event_study(self):
        units = ["A", "B", "C", "D", "E", "F"]
        E = [0.0, 0.5, 1.0, 1.5, 2.0, 3.0]
        first, last, shock = ac.parse_ym("2024-05"), ac.parse_ym("2025-07"), ac.parse_ym("2025-02")
        counts = self.make_counts(units, first, last, shock, E)
        r, d = ac.pooled(counts, units, E, first, last, shock, "events", reps=99)
        self.assertAlmostEqual(r["beta"], r["beta_closed_form"], places=9)
        self.assertGreater(r["beta"], 0)
        self.assertEqual(r["n_countries"], 6)
        self.assertEqual(r["n_exposed"], 5)
        loo = ac.leave_one_out(E, d, units)
        self.assertLessEqual(loo["min"], loo["max"])
        for oc in ac.OUTCOMES:
            Y = ac.panel(counts, units, first, last, oc)
            self.assertEqual(len(Y), 6)
            self.assertEqual(len(Y[0]), last - first + 1)
        es = ac.event_study(counts, units, E, first, last, shock, "events")
        self.assertEqual([b["bin"] for b in es["bins"]], [-3, -2, 0, 1])
        self.assertEqual(es["pretrend"]["q"], 2)
        self.assertTrue(0.0 <= es["pretrend"]["p_F"] <= 1.0)


if __name__ == "__main__":
    unittest.main()
