#!/usr/bin/env python3
# aid-cut-violence / mechanism.py -- Apache-2.0
# Copyright 2026 Munim, Inc. Made by MV2 of Munim, Inc. with AI agents.
"""Second pre-registered step (PREREG-2.md): was it USAID's money, and which kind?

  A. Agency test: exposure to USAID-managed aid versus exposure to all other US aid
     (State, DoD, MCC, HHS and others, which the January 2025 shutdown did not end).
  B. Dose response: the realized FY2025 drop in USAID disbursements per person,
     instrumented by pre-period USAID aid per person (just-identified IV).
  C. Sector test: humanitarian, health, governance, peace-and-security and other US aid
     per person, entered together.
  D. Placebo: test A with a fake shock in February 2023 and FY2020-2022 exposure.

Outcomes, sample and windows are those of aidcut.py (PREREGISTRATION.md). Standard
library only.

    python mechanism.py --data-dir data --out-dir out
"""
import argparse
import json
import math
import os
import random
import time
import urllib.request
from collections import Counter, defaultdict

import aidcut as ac

__version__ = "0.2.0"

AGENCY_URL = "https://s3.amazonaws.com/files.explorer.devtechlab.com/us_foreign_aid_implementing.csv"
SECTOR_URL = "https://s3.amazonaws.com/files.explorer.devtechlab.com/us_foreign_aid_usg_sector.csv"

PRE_YEARS = (2022, 2023, 2024)
PLACEBO_YEARS = (2020, 2021, 2022)
CUT_YEAR = 2025
GROUPS = ("humanitarian", "health", "governance", "peace_security", "other")
NAN = float("nan")


# ---------------------------------------------------------------- data
def download(url, path, tries=4):
    """Like aidcut.download, but with a unique temporary name so two jobs sharing one
    data volume never write the same partial file."""
    if os.path.exists(path) and os.path.getsize(path) > 0:
        return path
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    part = "%s.part-%d-%d" % (path, os.getpid(), random.SystemRandom().randrange(1 << 30))
    last = None
    for k in range(tries):
        try:
            req = urllib.request.Request(url, headers={
                "User-Agent": "aid-cut-violence/%s (MV2, Munim, Inc.; mv2@munimtech.com)" % __version__})
            with urllib.request.urlopen(req, timeout=300) as r, open(part, "wb") as f:
                while True:
                    chunk = r.read(1 << 20)
                    if not chunk:
                        break
                    f.write(chunk)
            os.replace(part, path)
            return path
        except Exception as exc:  # noqa: BLE001
            last = exc
            time.sleep(5 * (k + 1))
    raise RuntimeError("download failed: %s (%s)" % (url, last))


def _kind(r):
    tl = (r.get("transaction type name") or "").strip().lower()
    if "disburse" in tl or "spent" in tl:
        return "disb"
    if "obligat" in tl:
        return "oblig"
    return None


def _iso(r):
    iso = (r.get("country code") or "").strip().upper()
    return ac.FA_CODE_ALIASES.get(iso, iso)


def _fy_amt(r):
    return int(float(r.get("fiscal year") or 0)), float(r.get("constant_amount") or 0)


def _nested():
    return defaultdict(lambda: defaultdict(float))


def read_agency(rows):
    """ForeignAssistance.gov managing-agency summary ->
    {(who, kind): {iso3: {fy: constant USD}}} with who in usaid/other and kind in
    disb/oblig, plus a Counter of managing-agency acronyms."""
    out = {(w, k): _nested() for w in ("usaid", "other") for k in ("disb", "oblig")}
    agencies = Counter()
    for r in rows:
        kind = _kind(r)
        if kind is None:
            continue
        acr = (r.get("managing agency acronym") or "").strip().upper()
        agencies[acr] += 1
        who = "usaid" if acr == "USAID" else "other"
        try:
            fy, amt = _fy_amt(r)
        except ValueError:
            continue
        out[(who, kind)][_iso(r)][fy] += amt
    return out, agencies


def sector_group(name):
    """US Government sector category name -> one of GROUPS (fixed in PREREG-2.md)."""
    n = (name or "").lower()
    if "humanitarian" in n:
        return "humanitarian"
    if "health" in n or "population" in n:
        return "health"
    if "democracy" in n or "governance" in n or "human rights" in n:
        return "governance"
    if "peace" in n or "security" in n:
        return "peace_security"
    return "other"


def pick_column(keys, preferences):
    """First key that contains every needle of the first preference that matches."""
    for needles in preferences:
        for k in keys:
            if all(n in k for n in needles):
                return k
    return None


def read_sector(rows):
    """USG sector summary -> ({group: {iso3: {fy: constant USD disbursed}}}, info).
    The category column is found by name ('category' and 'name'); if there is no such
    column or no 'country code' column, the sector test is not run (info says why)."""
    out = {g: _nested() for g in GROUPS}
    names = Counter()
    info = {"column": None, "names": {}, "usable": False}
    col = None
    for r in rows:
        if col is None:
            keys = list(r.keys())
            col = pick_column(keys, [("category", "name")]) or ""
            info["column"] = col or None
            info["keys"] = keys
            if not col or "country code" not in keys:
                break
            info["usable"] = True
        if _kind(r) != "disb":
            continue
        name = (r.get(col) or "").strip()
        names[name] += 1
        try:
            fy, amt = _fy_amt(r)
        except ValueError:
            continue
        out[sector_group(name)][_iso(r)][fy] += amt
    info["names"] = {k: [v, sector_group(k)] for k, v in names.most_common()}
    return out, info


def per_person(series, pop, years):
    """{iso3: mean annual constant USD per person over years, floored at 0}."""
    out = {}
    for iso, p in pop.items():
        if not p:
            continue
        s = series.get(iso, {})
        tot = sum(s.get(y, 0.0) for y in years) / float(len(years))
        out[iso] = max(tot, 0.0) / p
    return out


# ---------------------------------------------------------------- statistics
def ols_hc1(y, cols, names=None):
    """Cross-section OLS of y on a constant and cols, HC1 standard errors."""
    n = len(y)
    K = len(cols) + 1
    if n <= K:
        raise ValueError("too few observations (%d for %d parameters)" % (n, K))
    X = [[1.0] + [float(c[i]) for c in cols] for i in range(n)]
    XtX = [[sum(X[i][a] * X[i][b] for i in range(n)) for b in range(K)] for a in range(K)]
    Xty = [sum(X[i][a] * y[i] for i in range(n)) for a in range(K)]
    beta = ac.solve(XtX, Xty)
    u = [y[i] - sum(beta[k] * X[i][k] for k in range(K)) for i in range(n)]
    B = ac.inverse(XtX)
    M = [[sum(X[i][a] * X[i][b] * u[i] * u[i] for i in range(n)) for b in range(K)]
         for a in range(K)]
    c = n / float(n - K)
    BM = [[sum(B[a][k] * M[k][b] for k in range(K)) for b in range(K)] for a in range(K)]
    V = [[c * sum(BM[a][k] * B[k][b] for k in range(K)) for b in range(K)] for a in range(K)]
    se = [math.sqrt(max(V[k][k], 0.0)) for k in range(K)]
    t = [beta[k] / se[k] if se[k] > 0 else NAN for k in range(K)]
    p = [ac.t_two_sided_p(tv, n - K) for tv in t]
    names = ["const"] + list(names or ["x%d" % j for j in range(1, K)])
    return {"names": names, "beta": beta, "se": se, "t": t, "p": p, "vcov": V,
            "n": n, "df": n - K}


def diff_test(fit, i, j):
    """Wald test of beta_i - beta_j = 0 from an ols_hc1 fit."""
    d = fit["beta"][i] - fit["beta"][j]
    v = fit["vcov"][i][i] + fit["vcov"][j][j] - 2.0 * fit["vcov"][i][j]
    se = math.sqrt(max(v, 0.0))
    t = d / se if se > 0 else NAN
    return {"diff": d, "se": se, "t": t, "p": ac.t_two_sided_p(t, fit["df"])}


def iv_just(y, x, z):
    """Just-identified IV slope of y on x with instrument z (both with a constant),
    HC1 standard error."""
    n = len(y)
    if n <= 2:
        raise ValueError("too few observations")
    zm, xm, ym = sum(z) / n, sum(x) / n, sum(y) / n
    zt = [v - zm for v in z]
    sxz = sum(a * (b - xm) for a, b in zip(zt, x))
    if abs(sxz) < 1e-14:
        raise ValueError("zero first stage")
    b = sum(a * (v - ym) for a, v in zip(zt, y)) / sxz
    a0 = ym - b * xm
    u = [yi - a0 - b * xi for yi, xi in zip(y, x)]
    var = n / float(n - 2) * sum((a * ui) ** 2 for a, ui in zip(zt, u)) / (sxz * sxz)
    se = math.sqrt(var)
    t = b / se if se > 0 else NAN
    return {"beta": b, "se": se, "t": t, "p": ac.t_two_sided_p(t, n - 2), "n": n}


def compact(fit):
    return {"n": fit["n"], "df": fit["df"],
            "coef": {nm: {"beta": b, "se": s, "p": p}
                     for nm, b, s, p in zip(fit["names"], fit["beta"], fit["se"], fit["p"])
                     if nm != "const"}}


# ---------------------------------------------------------------- analysis
def analyze(counts, pop, meta, agency, sector=None, reps=ac.RI_REPS):
    res = {"models": {}, "descriptive": {}}
    base = ac.build_sample(pop, meta)
    samples = {"global": base,
               "africa": [u for u in base if ac.is_africa(u, meta)],
               "rest": [u for u in base if not ac.is_africa(u, meta)]}
    res["descriptive"]["sample_sizes"] = {k: len(v) for k, v in samples.items()}

    U_pre = per_person(agency[("usaid", "disb")], pop, PRE_YEARS)
    O_pre = per_person(agency[("other", "disb")], pop, PRE_YEARS)
    U_cut = per_person(agency[("usaid", "disb")], pop, (CUT_YEAR,))
    U_plc = per_person(agency[("usaid", "disb")], pop, PLACEBO_YEARS)
    O_plc = per_person(agency[("other", "disb")], pop, PLACEBO_YEARS)
    lg = math.log1p
    tot_u = sum(U_pre.get(u, 0.0) * pop[u] for u in base)
    tot_o = sum(O_pre.get(u, 0.0) * pop[u] for u in base)
    tot_c = sum(U_cut.get(u, 0.0) * pop[u] for u in base)
    res["descriptive"].update({
        "usaid_disb_fy22_24_mean_usd": tot_u,
        "other_disb_fy22_24_mean_usd": tot_o,
        "usaid_disb_fy2025_usd": tot_c,
        "usaid_share_of_us_aid_pre": tot_u / (tot_u + tot_o) if tot_u + tot_o > 0 else NAN,
        "usaid_fy2025_over_pre": tot_c / tot_u if tot_u > 0 else NAN})

    def fit(name, func):
        try:
            res["models"][name] = func()
        except (ValueError, ZeroDivisionError) as exc:
            res["models"][name] = {"error": str(exc)}

    win = {w: tuple(ac.parse_ym(x) for x in ac.WINDOWS[w])
           for w in ("primary", "extended", "placebo")}

    def delta(units, wname, outcome):
        f, l, s = win[wname]
        return ac.deltas(ac.panel(counts, units, f, l, outcome), f, l, s)

    def a1(E, d, units=None):
        b, p = ac.ri_pvalue(E, d, reps=reps)
        f1 = ols_hc1(d, [E], ["E_usaid"])
        out = {"beta": b, "p_ri": p, "ri_reps": reps, "se_hc1": f1["se"][1],
               "p_hc1": f1["p"][1], "n": len(d)}
        if units is not None:
            out["leave_one_out"] = ac.leave_one_out(E, d, units)
        return out

    def a2(Eu, Eo, d):
        f2 = ols_hc1(d, [Eu, Eo], ["E_usaid", "E_other"])
        return {"fit": compact(f2), "usaid_minus_other": diff_test(f2, 1, 2)}

    for oc in ("events", "deaths"):
        for sname, units in samples.items():
            d = delta(units, "primary", oc)
            Eu = [lg(U_pre[u]) for u in units]
            Eo = [lg(O_pre[u]) for u in units]
            loo = units if (sname == "global" and oc == "events") else None
            fit("A1|primary|%s|%s" % (sname, oc), lambda E=Eu, d=d, loo=loo: a1(E, d, loo))
            fit("A2|primary|%s|%s" % (sname, oc), lambda Eu=Eu, Eo=Eo, d=d: a2(Eu, Eo, d))

        units = samples["global"]
        d = delta(units, "extended", oc)
        Eu = [lg(U_pre[u]) for u in units]
        Eo = [lg(O_pre[u]) for u in units]
        fit("A1|extended|global|%s" % oc, lambda E=Eu, d=d: a1(E, d))
        fit("A2|extended|global|%s" % oc, lambda Eu=Eu, Eo=Eo, d=d: a2(Eu, Eo, d))

        # D. placebo: fake shock 2023-02, exposure FY2020-2022
        for sname in ("global", "africa"):
            units = samples[sname]
            d = delta(units, "placebo", oc)
            Eu = [lg(U_plc[u]) for u in units]
            Eo = [lg(O_plc[u]) for u in units]
            fit("D1|placebo|%s|%s" % (sname, oc), lambda E=Eu, d=d: a1(E, d))
            fit("D2|placebo|%s|%s" % (sname, oc), lambda Eu=Eu, Eo=Eo, d=d: a2(Eu, Eo, d))

        # B. dose response: realized FY2025 log drop, instrumented by pre-period level
        for sname, units in samples.items():
            d = delta(units, "primary", oc)
            z = [lg(U_pre[u]) for u in units]
            x = [lg(U_pre[u]) - lg(U_cut[u]) for u in units]

            def b_model(d=d, z=z, x=x):
                fs = ols_hc1(x, [z], ["E_usaid"])
                t = fs["t"][1]
                return {"first_stage": {"slope": fs["beta"][1], "se": fs["se"][1],
                                        "F": t * t if t == t else NAN},
                        "iv": iv_just(d, x, z),
                        "ols_on_realized_drop": compact(ols_hc1(d, [x], ["log_drop"])),
                        "mean_log_drop": sum(x) / len(x)}
            fit("B|primary|%s|%s" % (sname, oc), b_model)

        # C. sectors entered together
        if sector is None:
            res["models"]["C|primary|global|%s" % oc] = {"skipped": "no usable sector file"}
        else:
            units = samples["global"]
            d = delta(units, "primary", oc)
            pcs = {g: per_person(sector[g], pop, PRE_YEARS) for g in GROUPS}
            cols = [[lg(pcs[g][u]) for u in units] for g in GROUPS]
            fit("C|primary|global|%s" % oc,
                lambda d=d, cols=cols: {"fit": compact(ols_hc1(d, cols, list(GROUPS)))})
    if sector is not None:
        res["descriptive"]["sector_disb_fy22_24_mean_usd"] = {
            g: sum(per_person(sector[g], pop, PRE_YEARS).get(u, 0.0) * pop[u] for u in base)
            for g in GROUPS}
    return res


def summarize(key, m):
    if "error" in m:
        return "- %s: error: %s" % (key, m["error"])
    if "skipped" in m:
        return "- %s: skipped: %s" % (key, m["skipped"])
    if "p_ri" in m:
        return "- %s: b_usaid %.4f, p RI %.4f, SE HC1 %.4f, n %d" % (
            key, m["beta"], m["p_ri"], m["se_hc1"], m["n"])
    if "usaid_minus_other" in m:
        c = m["fit"]["coef"]
        dt = m["usaid_minus_other"]
        return ("- %s: b_usaid %.4f (p %.3f), b_other %.4f (p %.3f), diff %.4f (p %.3f), n %d" % (
            key, c["E_usaid"]["beta"], c["E_usaid"]["p"], c["E_other"]["beta"],
            c["E_other"]["p"], dt["diff"], dt["p"], m["fit"]["n"]))
    if "iv" in m:
        fs, iv = m["first_stage"], m["iv"]
        return ("- %s: first stage %.4f (F %.1f), IV %.4f (SE %.4f, p %.3f), mean log drop %.3f, n %d"
                % (key, fs["slope"], fs["F"], iv["beta"], iv["se"], iv["p"], m["mean_log_drop"],
                   iv["n"]))
    if "fit" in m:
        parts = ["%s %.4f (p %.3f)" % (nm, v["beta"], v["p"]) for nm, v in m["fit"]["coef"].items()]
        return "- %s: %s, n %d" % (key, "; ".join(parts), m["fit"]["n"])
    return "- %s: %s" % (key, json.dumps(m, sort_keys=True))


def run(data_dir, out_dir, reps=ac.RI_REPS):
    os.makedirs(out_dir, exist_ok=True)
    j = os.path.join
    log = {"version": __version__,
           "started": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
           "sources": {"ged": ac.GED_URL, "candidate": ac.CAND_URL, "agency": AGENCY_URL,
                       "sector": SECTOR_URL, "wb_pop": ac.WB_POP_URL, "wb_meta": ac.WB_META_URL}}
    paths = {"ged": download(ac.GED_URL, j(data_dir, "ged261-csv.zip")),
             "cand": download(ac.CAND_URL, j(data_dir, "GEDEvent_v26_01_26_09.csv")),
             "wb_pop": download(ac.WB_POP_URL, j(data_dir, "wb_pop_2023.json")),
             "wb_meta": download(ac.WB_META_URL, j(data_dir, "wb_meta.json")),
             "agency": download(AGENCY_URL, j(data_dir, "us_foreign_aid_implementing.csv"))}
    try:
        paths["sector"] = download(SECTOR_URL, j(data_dir, "us_foreign_aid_usg_sector.csv"))
    except RuntimeError as exc:
        log["sector_download_error"] = str(exc)
    log["sha256"] = {k: ac.sha256_file(p) for k, p in paths.items()}

    first_all, ged_last = ac.parse_ym("2021-02"), ac.parse_ym("2025-12")
    counts, unmatched, by_year = ac.count_events(
        ac.iter_csv_rows(ac.open_csv_maybe_zip(paths["ged"])), first_all, ged_last)
    ged_months = sorted({m for (_, m) in counts})
    log["ged_last_month"] = ac.ym_str(ged_months[-1]) if ged_months else None
    if not ged_months or ged_months[-1] < ged_last:
        raise SystemExit("GED 26.1 does not reach 2025-12; stopping as pre-registered")
    ac.count_events(ac.iter_csv_rows(ac.open_csv_maybe_zip(paths["cand"])),
                    ac.parse_ym("2026-01"), ac.parse_ym("2026-09"), counts, unmatched, Counter())
    log["unmatched_country_names"] = dict(unmatched.most_common())

    with open(paths["agency"], encoding="utf-8-sig", newline="") as fh:
        agency, agencies = read_agency(ac.iter_csv_rows(fh))
    log["managing_agencies_rows"] = dict(agencies.most_common())
    sector = None
    if "sector" in paths:
        with open(paths["sector"], encoding="utf-8-sig", newline="") as fh:
            sec, info = read_sector(ac.iter_csv_rows(fh))
        log["sector_file"] = info
        if info["usable"]:
            sector = sec
    with open(paths["wb_pop"], encoding="utf-8") as fh:
        pop_json = json.load(fh)
    with open(paths["wb_meta"], encoding="utf-8") as fh:
        meta_json = json.load(fh)
    pop, meta = ac.read_wb(pop_json, meta_json)

    results = analyze(counts, pop, meta, agency, sector, reps)
    log["finished"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    results["meta"] = log
    with open(j(out_dir, "mechanism_results.json"), "w", encoding="utf-8") as fh:
        json.dump(results, fh, indent=1, sort_keys=True)
    lines = ["# aid-cut-violence mechanism %s results (PREREG-2)" % __version__, "",
             "## Descriptive", ""]
    for k, v in sorted(results["descriptive"].items()):
        lines.append("- %s: %s" % (k, json.dumps(v, sort_keys=True)))
    lines += ["", "## Models", ""]
    for key in sorted(results["models"]):
        lines.append(summarize(key, results["models"][key]))
    with open(j(out_dir, "mechanism_results.md"), "w", encoding="utf-8") as fh:
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
