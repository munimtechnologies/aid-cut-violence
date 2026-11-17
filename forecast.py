#!/usr/bin/env python3
# aid-cut-violence / forecast.py -- Apache-2.0
# Copyright 2026 Munim, Inc. Made by MV2 of Munim, Inc. with AI agents.
"""Fourth pre-registered step (PREREG-4.md): did violence beat a forecast made before the cut?

VIEWS (Uppsala University and PRIO) publishes monthly country-month forecasts of
state-based conflict deaths, and keeps every past run in its public API. The run
fatalities002_2025_01_t01 used data through January 2025 and no aid variables, so its
forecasts for February-December 2025 are a counterfactual fixed before the USAID shutdown
by people who knew nothing about it. If the cut raised violence, the forecast error

    e = mean over months of [log(1 + actual UCDP state-based deaths) - VIEWS log forecast]

should be larger in USAID-dependent countries in 2025 than in a pre-cut year.

  F1  e_2025 ~ E_usaid                      (one year; VIEWS may miss fragile states anyway)
  F2  e_2025 - e_2024 ~ E_usaid             PRIMARY: same model family, same horizons
  F2b e_2025 - mean(e_2024, e_2023) ~ E_usaid
  F2r F2 within World Bank regions
  F3  e_o ~ E_usaid(o) for pre-cut origins o = 2024, 2023, 2022 (placebos)
  F3d e_2024 - e_2023 ~ E_usaid(2024)       placebo of the primary design
  F4  F2 + mean VIEWS log forecast (2025) as a control
  F5  F2 with the dichotomous error 1[deaths >= 25] - P(deaths >= 25)
  F6  F1 over the extended window February 2025 - September 2026

E_usaid(o) = log(1 + mean USAID-managed disbursements per person over the three fiscal
years before o). Randomization inference permutes exposure across countries. Sample is
that of aidcut.py. Standard library only.

    python forecast.py --data-dir data --out-dir out
"""
import argparse
import csv
import json
import math
import os
import time
from collections import Counter, defaultdict

import aidcut as ac
import mechanism as mc

__version__ = "0.4.0"

VIEWS_API = "https://api.viewsforecasting.org/"
RUNS = {
    2025: "fatalities002_2025_01_t01",   # data through 2025-01: the counterfactual
    2024: "fatalities002_2024_01_t01",   # same model family: primary comparison year
    2023: "fatalities001_2023_01_t01",   # older model: placebo
    2022: "fatalities001_2022_01_t01",   # older model: exploratory placebo
}
TREATED = 2025
COMPARE = 2024
PLACEBOS = (2024, 2023, 2022)
REQUIRED = (2025, 2024)
LN_FIELDS = ("main_mean_ln", "sc_cm_sb_main")
COUNT_FIELDS = ("main_mean",)
DICH_FIELDS = ("main_dich", "sc_cm_sb_dich_main")
DICH_THRESHOLD = 25
MIN_COUNTRIES = 60
MAX_LN = 20.0
EXT_LAST = "2026-09"
NAN = float("nan")


def window(origin):
    """Primary window of a January run: February to December of the same year
    (forecast steps 1 to 11)."""
    return ac.ym_index(origin, 2), ac.ym_index(origin, 12)


def exposure_years(origin):
    """The three US fiscal years that ended before the origin: 2025 -> FY2022-2024."""
    return (origin - 3, origin - 2, origin - 1)


# ---------------------------------------------------------------- VIEWS forecasts
def views_url(run, page=None):
    url = "%s%s/cm/sb?pagesize=10000" % (VIEWS_API, run)
    return url if page is None else "%s&page=%d" % (url, page)


def fetch_views(run, data_dir, max_pages=50):
    """Download every page of a run's country-month state-based forecasts.
    Returns the parsed pages."""
    docs = []
    url = views_url(run)
    page = 1
    while url and page <= max_pages:
        path = os.path.join(data_dir, "views_%s_cm_sb_p%d.json" % (run, page))
        mc.download(url, path)
        with open(path, encoding="utf-8") as fh:
            doc = json.load(fh)
        docs.append(doc)
        url = doc.get("next_page") or ""
        page += 1
    return docs


def _pick(rec, fields):
    for f in fields:
        v = rec.get(f)
        if v is None:
            continue
        try:
            return f, float(v)
        except (TypeError, ValueError):
            continue
    return None, None


def read_views(docs):
    """VIEWS API pages -> ({(iso3, month): (log forecast, P(>=25 deaths) or None)}, info).
    The log forecast is main_mean_ln (fatalities002/003) or sc_cm_sb_main (fatalities001),
    both log(1 + predicted deaths); if neither exists, log1p(main_mean)."""
    out = {}
    used = Counter()
    bad = 0
    for doc in docs:
        for rec in doc.get("data") or []:
            iso = (rec.get("isoab") or "").strip().upper()
            try:
                m = ac.ym_index(int(rec["year"]), int(rec["month"]))
            except (KeyError, TypeError, ValueError):
                bad += 1
                continue
            f, ln = _pick(rec, LN_FIELDS)
            if ln is None:
                f, cnt = _pick(rec, COUNT_FIELDS)
                if cnt is not None:
                    ln = math.log1p(max(cnt, 0.0))
                    f = "log1p(%s)" % f
            if ln is None or not iso:
                bad += 1
                continue
            df, p = _pick(rec, DICH_FIELDS)
            used[f] += 1
            if df:
                used[df] += 1
            out[(iso, m)] = (ln, p)
    months = sorted({m for _, m in out})
    info = {"fields": dict(used), "rows": len(out), "bad_rows": bad,
            "first_month": ac.ym_str(months[0]) if months else None,
            "last_month": ac.ym_str(months[-1]) if months else None,
            "countries": len({i for i, _ in out}),
            "max_ln": max((v[0] for v in out.values()), default=None)}
    return out, info


# ---------------------------------------------------------------- UCDP actuals
def count_sb(rows, first, last, out=None, unmatched=None):
    """UCDP GED rows -> {(iso3, month): state-based deaths ('best')}, type_of_violence 1
    only, for first <= month <= last."""
    out = out if out is not None else defaultdict(int)
    unmatched = unmatched if unmatched is not None else Counter()
    for r in rows:
        if (r.get("type_of_violence") or "").strip() != "1":
            continue
        try:
            m = ac.parse_month(r.get("date_start", ""))
        except ValueError:
            continue
        if m < first or m > last:
            continue
        iso = ac.ged_iso3(r.get("country", ""))
        if iso is None:
            unmatched[r.get("country", "")] += 1
            continue
        try:
            best = int(float(r.get("best") or 0))
        except ValueError:
            best = 0
        out[(iso, m)] += best
    return out, unmatched


def country_errors(fc, actual, units, first, last):
    """Per unit with a forecast in every month of first..last: mean log error e, mean
    dichotomous error ed (None if any month lacks a probability), mean log forecast fbar,
    mean log actual abar, and summed actual and forecast deaths. Returns (dict, missing)."""
    out, missing = {}, []
    months = list(range(first, last + 1))
    for u in units:
        if any((u, m) not in fc for m in months):
            missing.append(u)
            continue
        es, eds, fs, la = [], [], [], []
        a_sum = f_sum = 0.0
        for m in months:
            ln, p = fc[(u, m)]
            a = actual.get((u, m), 0)
            es.append(math.log1p(a) - ln)
            fs.append(ln)
            la.append(math.log1p(a))
            a_sum += a
            f_sum += math.expm1(ln)
            if p is not None:
                eds.append((1.0 if a >= DICH_THRESHOLD else 0.0) - p)
        n = float(len(months))
        out[u] = {"e": sum(es) / n, "ed": sum(eds) / n if len(eds) == len(es) else None,
                  "fbar": sum(fs) / n, "abar": sum(la) / n, "a_sum": a_sum, "f_sum": f_sum}
    return out, missing


# ---------------------------------------------------------------- statistics
def slope_test(E, y, units, reps, groups=None, loo=False):
    b, p_ri = ac.ri_pvalue(E, y, groups, reps=reps)
    f = mc.ols_hc1(y, [E], ["E_usaid"])
    se = f["se"][1]
    out = {"beta": b, "p_ri": p_ri, "ri_reps": reps, "beta_ols": f["beta"][1],
           "se_hc1": se, "p_hc1": f["p"][1],
           "ci95_hc1": [f["beta"][1] - 1.96 * se, f["beta"][1] + 1.96 * se], "n": len(y)}
    if groups is not None:
        out["within"] = "groups: World Bank regions (beta and p_ri are within-region)"
    if loo:
        out["leave_one_out"] = ac.leave_one_out(E, y, units)
    return out


def terciles(v):
    order = sorted(range(len(v)), key=lambda i: (v[i], i))
    g = [0] * len(v)
    for rank, i in enumerate(order):
        g[i] = rank * 3 // len(v)
    return g


def quantile(v, q):
    s = sorted(v)
    return s[int(q * (len(s) - 1))]


def corr(a, b):
    n = len(a)
    ma, mb = sum(a) / n, sum(b) / n
    sab = sum((x - ma) * (y - mb) for x, y in zip(a, b))
    saa = sum((x - ma) ** 2 for x in a)
    sbb = sum((y - mb) ** 2 for y in b)
    if n < 3 or saa <= 0 or sbb <= 0:
        raise ValueError("correlation undefined")
    return sab / math.sqrt(saa * sbb)


# ---------------------------------------------------------------- analysis
def analyze(actual, fcs, pop, meta, agency, reps=ac.RI_REPS, ext_last=None):
    """fcs: {origin year: {(iso3, month): (log forecast, p)}}."""
    res = {"models": {}, "descriptive": {}}
    base = ac.build_sample(pop, meta)
    lg = math.log1p
    U = agency[("usaid", "disb")]
    Ex = {o: mc.per_person(U, pop, exposure_years(o)) for o in fcs}
    err, miss = {}, {}
    for o in sorted(fcs):
        f, l = window(o)
        err[o], miss[o] = country_errors(fcs[o], actual, base, f, l)
    res["descriptive"]["base_countries"] = len(base)
    res["descriptive"]["missing_forecasts"] = {str(o): miss[o] for o in sorted(fcs)}
    if TREATED not in err or COMPARE not in err:
        res["stopped"] = "missing the 2025 or 2024 VIEWS run"
        return res
    both = [u for u in base if u in err[TREATED] and u in err[COMPARE]]
    res["descriptive"]["n_with_2025_and_2024"] = len(both)
    if len(both) < MIN_COUNTRIES:
        res["stopped"] = "fewer than %d countries with both runs (%d)" % (MIN_COUNTRIES, len(both))
        return res
    samples = {"global": both,
               "africa": [u for u in both if ac.is_africa(u, meta)],
               "rest": [u for u in both if not ac.is_africa(u, meta)]}
    res["descriptive"]["sample_sizes"] = {k: len(v) for k, v in samples.items()}

    def fit(name, func):
        try:
            res["models"][name] = func()
        except (ValueError, ZeroDivisionError) as exc:
            res["models"][name] = {"error": str(exc)}

    def E_of(o, us):
        return [lg(Ex[o].get(u, 0.0)) for u in us]

    e25 = {u: err[TREATED][u]["e"] for u in both}
    e24 = {u: err[COMPARE][u]["e"] for u in both}

    us = samples["global"]
    fit("F1|global", lambda: slope_test(E_of(TREATED, us), [e25[u] for u in us], us, reps))
    for sname, us in samples.items():
        d = [e25[u] - e24[u] for u in us]
        fit("F2|%s" % sname, lambda us=us, d=d, loo=(sname == "global"):
            slope_test(E_of(TREATED, us), d, us, reps, loo=loo))

    us = samples["global"]
    d2 = [e25[u] - e24[u] for u in us]
    fit("F2r|global", lambda: slope_test(E_of(TREATED, us), d2, us, reps,
                                         groups=[meta[u]["region"] for u in us]))
    fit("F4|global", lambda: {"fit": mc.compact(mc.ols_hc1(
        d2, [E_of(TREATED, us), [err[TREATED][u]["fbar"] for u in us]],
        ["E_usaid", "fbar_2025"]))})

    if 2023 in err:
        us3 = [u for u in both if u in err[2023]]
        d3 = [e25[u] - 0.5 * (e24[u] + err[2023][u]["e"]) for u in us3]
        fit("F2b|global", lambda: slope_test(E_of(TREATED, us3), d3, us3, reps))
        dp = [e24[u] - err[2023][u]["e"] for u in us3]
        fit("F3d|global|2024-2023", lambda: slope_test(E_of(COMPARE, us3), dp, us3, reps))
        if 2022 in err:
            us2 = [u for u in us3 if u in err[2022]]
            dq = [err[2023][u]["e"] - err[2022][u]["e"] for u in us2]
            fit("F3d|global|2023-2022", lambda: slope_test(E_of(2023, us2), dq, us2, reps))

    for o in PLACEBOS:
        if o not in err:
            res["models"]["F3|global|%d" % o] = {"error": "run %s not available" % RUNS[o]}
            continue
        for sname in ("global", "africa"):
            us_o = [u for u in base if u in err[o]
                    and (sname == "global" or ac.is_africa(u, meta))]
            fit("F3|%s|%d" % (sname, o), lambda o=o, us_o=us_o: slope_test(
                E_of(o, us_o), [err[o][u]["e"] for u in us_o], us_o, reps))

    usd = [u for u in both if err[TREATED][u]["ed"] is not None
           and err[COMPARE][u]["ed"] is not None]
    dd = [err[TREATED][u]["ed"] - err[COMPARE][u]["ed"] for u in usd]
    fit("F5|global", lambda: slope_test(E_of(TREATED, usd), dd, usd, reps))

    if ext_last is not None and ext_last > window(TREATED)[1]:
        ext, miss_ext = country_errors(fcs[TREATED], actual, both, window(TREATED)[0], ext_last)
        use = [u for u in both if u in ext]
        res["descriptive"]["extended_window"] = [ac.ym_str(window(TREATED)[0]), ac.ym_str(ext_last)]
        res["descriptive"]["extended_missing"] = miss_ext
        fit("F6|global", lambda: slope_test(E_of(TREATED, use), [ext[u]["e"] for u in use],
                                            use, reps))
        fit("F6d|global", lambda: slope_test(E_of(TREATED, use),
                                             [ext[u]["e"] - e24[u] for u in use], use, reps))
    else:
        res["models"]["F6|global"] = {"error": "no extended months"}

    # descriptive
    us = samples["global"]
    E = E_of(TREATED, us)
    res["descriptive"]["E_usaid_quantiles"] = {
        "q25": quantile(E, .25), "q50": quantile(E, .5), "q75": quantile(E, .75)}
    iqr = quantile(E, .75) - quantile(E, .25)
    res["descriptive"]["E_usaid_iqr"] = iqr
    f2 = res["models"].get("F2|global", {})
    if "beta" in f2:
        res["descriptive"]["F2_beta_times_iqr"] = f2["beta"] * iqr
        res["descriptive"]["F2_implied_pct_more_deaths_than_forecast_q75_vs_q25"] = (
            100.0 * math.expm1(f2["beta"] * iqr))
    try:
        res["descriptive"]["corr_e2024_e2025"] = corr([e24[u] for u in us], [e25[u] for u in us])
    except ValueError as exc:
        res["descriptive"]["corr_e2024_e2025"] = str(exc)
    g = terciles(E)
    agg = {}
    for o in (COMPARE, TREATED):
        for t in range(3):
            members = [u for u, gi in zip(us, g) if gi == t]
            agg["%d|tercile%d" % (o, t + 1)] = {
                "countries": len(members),
                "actual_sb_deaths": sum(err[o][u]["a_sum"] for u in members),
                "forecast_sb_deaths": sum(err[o][u]["f_sum"] for u in members),
                "mean_log_error": sum(err[o][u]["e"] for u in members) / max(len(members), 1)}
    res["descriptive"]["aggregate_by_E_tercile"] = agg
    res["descriptive"]["mean_error_by_origin"] = {
        str(o): sum(v["e"] for v in err[o].values()) / max(len(err[o]), 1) for o in sorted(err)}
    res["country_errors"] = {str(o): err[o] for o in sorted(err)}
    return res


def summarize(key, m):
    if "error" in m:
        return "- %s: error: %s" % (key, m["error"])
    if "p_ri" in m:
        return ("- %s: b %.4f (p RI %.4f; OLS %.4f, SE HC1 %.4f, p %.3f, 95%% CI [%.4f, %.4f]), n %d"
                % (key, m["beta"], m["p_ri"], m["beta_ols"], m["se_hc1"], m["p_hc1"],
                   m["ci95_hc1"][0], m["ci95_hc1"][1], m["n"]))
    if "fit" in m:
        parts = ["%s %.4f (p %.3f)" % (nm, v["beta"], v["p"]) for nm, v in m["fit"]["coef"].items()]
        return "- %s: %s, n %d" % (key, "; ".join(parts), m["fit"]["n"])
    return "- %s: %s" % (key, json.dumps(m, sort_keys=True))


# ---------------------------------------------------------------- main
def run(data_dir, out_dir, reps=ac.RI_REPS):
    os.makedirs(out_dir, exist_ok=True)
    j = os.path.join
    log = {"version": __version__,
           "started": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
           "sources": {"ged": ac.GED_URL, "candidate": ac.CAND_URL, "agency": mc.AGENCY_URL,
                       "wb_pop": ac.WB_POP_URL, "wb_meta": ac.WB_META_URL,
                       "views": {str(o): views_url(r) for o, r in RUNS.items()}}}
    paths = {"ged": mc.download(ac.GED_URL, j(data_dir, "ged261-csv.zip")),
             "cand": mc.download(ac.CAND_URL, j(data_dir, "GEDEvent_v26_01_26_09.csv")),
             "wb_pop": mc.download(ac.WB_POP_URL, j(data_dir, "wb_pop_2023.json")),
             "wb_meta": mc.download(ac.WB_META_URL, j(data_dir, "wb_meta.json")),
             "agency": mc.download(mc.AGENCY_URL, j(data_dir, "us_foreign_aid_implementing.csv"))}
    log["sha256"] = {k: ac.sha256_file(p) for k, p in paths.items()}

    fcs, log["views"] = {}, {}
    for o, runname in sorted(RUNS.items()):
        try:
            docs = fetch_views(runname, data_dir)
        except (RuntimeError, ValueError) as exc:
            if o in REQUIRED:
                raise SystemExit("required VIEWS run %s failed: %s" % (runname, exc))
            log["views"][str(o)] = {"run": runname, "error": str(exc)}
            continue
        fc, info = read_views(docs)
        info["run"] = runname
        log["views"][str(o)] = info
        if not fc or info["max_ln"] is None or info["max_ln"] > MAX_LN:
            raise SystemExit("VIEWS run %s: forecasts missing or not on the log scale (%s)"
                             % (runname, info))
        fcs[o] = fc

    first, ged_last = ac.parse_ym("2022-02"), ac.parse_ym("2025-12")
    actual, unmatched = count_sb(ac.iter_csv_rows(ac.open_csv_maybe_zip(paths["ged"])),
                                 first, ged_last)
    ged_months = sorted({m for (_, m) in actual})
    log["ged_last_month"] = ac.ym_str(ged_months[-1]) if ged_months else None
    if not ged_months or ged_months[-1] < ged_last:
        raise SystemExit("GED 26.1 does not reach 2025-12; stopping as pre-registered")
    count_sb(ac.iter_csv_rows(ac.open_csv_maybe_zip(paths["cand"])), ac.parse_ym("2026-01"),
             ac.parse_ym(EXT_LAST), actual, unmatched)
    cand_months = sorted({m for (_, m) in actual if m > ged_last})
    ext_last = min(cand_months[-1], ac.parse_ym(EXT_LAST)) if cand_months else None
    log["candidate_last_month"] = ac.ym_str(ext_last) if ext_last else None
    log["unmatched_country_names_sb"] = dict(unmatched.most_common())
    tot = sum(actual.values()) + 0.0
    log["sb_deaths_2022_02_on"] = tot

    with open(paths["agency"], encoding="utf-8-sig", newline="") as fh:
        agency, agencies = mc.read_agency(ac.iter_csv_rows(fh))
    log["managing_agencies_rows_usaid"] = agencies.get("USAID", 0)
    with open(paths["wb_pop"], encoding="utf-8") as fh:
        pop_json = json.load(fh)
    with open(paths["wb_meta"], encoding="utf-8") as fh:
        meta_json = json.load(fh)
    pop, meta = ac.read_wb(pop_json, meta_json)
    views_isos = set()
    for fc in fcs.values():
        views_isos |= {i for i, _ in fc}
    base = ac.build_sample(pop, meta)
    log["base_not_in_views"] = [u for u in base if u not in views_isos]

    results = analyze(actual, fcs, pop, meta, agency, reps, ext_last)
    log["finished"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    results["meta"] = log
    with open(j(out_dir, "forecast_results.json"), "w", encoding="utf-8") as fh:
        json.dump(results, fh, indent=1, sort_keys=True)

    ce = results.get("country_errors", {})
    U = agency[("usaid", "disb")]
    U25 = mc.per_person(U, pop, exposure_years(TREATED))
    with open(j(out_dir, "forecast_table.csv"), "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["iso3", "name", "africa", "usaid_disb_fy22_24_per_person"]
                   + ["err_%d" % o for o in sorted(RUNS)]
                   + ["fbar_2025", "abar_2025", "sb_deaths_2025_02_12", "forecast_2025_02_12"])
        for u in base:
            r25 = ce.get(str(TREATED), {}).get(u)
            w.writerow([u, meta[u]["name"], int(ac.is_africa(u, meta)), round(U25.get(u, 0.0), 4)]
                       + [("" if u not in ce.get(str(o), {}) else round(ce[str(o)][u]["e"], 5))
                          for o in sorted(RUNS)]
                       + (["", "", "", ""] if r25 is None else
                          [round(r25["fbar"], 5), round(r25["abar"], 5), int(r25["a_sum"]),
                           round(r25["f_sum"], 1)]))

    lines = ["# aid-cut-violence forecast %s results (PREREG-4)" % __version__, ""]
    if "stopped" in results:
        lines.append("STOPPED: " + results["stopped"])
    lines += ["## Descriptive", ""]
    for k, v in sorted(results["descriptive"].items()):
        lines.append("- %s: %s" % (k, json.dumps(v, sort_keys=True)))
    lines += ["", "## VIEWS runs", ""]
    for k, v in sorted(log["views"].items()):
        lines.append("- %s: %s" % (k, json.dumps(v, sort_keys=True)))
    lines += ["", "## Models", ""]
    for key in sorted(results["models"]):
        lines.append(summarize(key, results["models"][key]))
    with open(j(out_dir, "forecast_results.md"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")
    print("\n".join(lines))
    return results


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--data-dir", default="data")
    ap.add_argument("--out-dir", default="out")
    ap.add_argument("--reps", type=int, default=ac.RI_REPS)
    a = ap.parse_args(argv)
    run(a.data_dir, a.out_dir, a.reps)


if __name__ == "__main__":
    main()
