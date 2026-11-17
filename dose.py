#!/usr/bin/env python3
# aid-cut-violence / dose.py -- Apache-2.0
# Copyright 2026 Munim, Inc. Made by MV2 of Munim, Inc. with AI agents.
"""Third pre-registered step (PREREG-3.md): the size of the cut, holding dependence fixed.

Countries that depended equally on USAID lost very different shares of their USAID
programme in March 2025 (Liberia about 98%, Ethiopia about 30%). If the violence came
from the cut itself, the share terminated should predict the post-shock change in
organized violence among equally USAID-dependent countries; if exposure designs only
pick up fragility, it should not.

  T1  delta ~ S + E_usaid           S = share of the country's USAID programme terminated
                                    (CGD, Sandefur and Kenny, 26 March 2025, revised Aug 2025)
  T1v delta ~ S + E_usaid + pre     pre = pre-shock violence level (selection check)
  T2  delta ~ log1p(cut per person) + E_usaid
  T3  delta ~ log1p(cut per person) + log1p(retained per person)   (Wald cut - retained)
  P   T1 with a fake shock in February 2023 (FY2020-2022 exposure)
  D   descriptive: corr(S, pre-shock violence), corr(S, E_usaid)

Randomization inference permutes S within terciles of E_usaid. Outcomes, sample and
windows are those of aidcut.py. Standard library only.

    python dose.py --data-dir data --out-dir out
"""
import argparse
import csv
import json
import math
import os
import random
import time
import unicodedata
from collections import defaultdict
from html.parser import HTMLParser

import aidcut as ac
import mechanism as mc

__version__ = "0.3.0"

CGD_URL = "https://www.cgdev.org/blog/usaid-cuts-new-estimates-country-level"
CGD_ARCHIVE_URL = "https://web.archive.org/web/2026id_/" + CGD_URL
STRATA = 3
MIN_COUNTRIES = 40
NAN = float("nan")


# ---------------------------------------------------------------- the CGD table
class _Tables(HTMLParser):
    """Collect every <table> as a list of rows of cell texts."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.tables = []
        self._stack = []
        self._row = None
        self._cell = None

    def _close_cell(self):
        if self._cell is not None and self._row is not None:
            self._row.append(" ".join("".join(self._cell).split()))
        self._cell = None

    def _close_row(self):
        self._close_cell()
        if self._row and self._stack:
            self._stack[-1].append(self._row)
        self._row = None

    def handle_starttag(self, tag, attrs):
        if tag == "table":
            self._stack.append([])
        elif tag == "tr" and self._stack:
            self._close_row()
            self._row = []
        elif tag in ("td", "th") and self._row is not None:
            self._close_cell()
            self._cell = []
        elif tag == "br" and self._cell is not None:
            self._cell.append(" ")

    def handle_endtag(self, tag):
        if tag in ("td", "th"):
            self._close_cell()
        elif tag == "tr":
            self._close_row()
        elif tag == "table" and self._stack:
            self._close_row()
            self.tables.append(self._stack.pop())

    def handle_data(self, data):
        if self._cell is not None:
            self._cell.append(data)


def num(s):
    """'1,433' -> 1433.0, '15%' -> 15.0, 'NA' or '' -> None."""
    t = (s or "").replace(",", "").replace("%", "").replace("$", "").strip()
    if t.lower() in ("", "na", "n/a", "-", "—", "–", "nan"):
        return None
    try:
        return float(t)
    except ValueError:
        return None


def parse_cut_table(html_text):
    """Find the table with a 'Country' column and a '% country program' column and return
    [{'name', 'pct', 'gni', 'cut_musd'}]; [] if no such table."""
    p = _Tables()
    p.feed(html_text)
    p.close()
    for table in p.tables:
        for h, row in enumerate(table):
            low = [c.lower() for c in row]
            i_pct = next((i for i, c in enumerate(low) if "program" in c), None)
            i_cty = next((i for i, c in enumerate(low) if "country" in c and "program" not in c),
                         None)
            if i_pct is None or i_cty is None:
                continue
            i_gni = next((i for i, c in enumerate(low) if "gni" in c), None)
            i_abs = next((i for i, c in enumerate(low)
                          if "absolute" in c or "($m)" in c or "$m" in c), None)
            out = []
            for r in table[h + 1:]:
                if len(r) <= max(i_cty, i_pct):
                    continue
                name = r[i_cty].strip()
                if not name or name.lower() in ("total", "all countries"):
                    continue
                out.append({"name": name, "pct": num(r[i_pct]),
                            "gni": num(r[i_gni]) if i_gni is not None and i_gni < len(r) else None,
                            "cut_musd": num(r[i_abs]) if i_abs is not None and i_abs < len(r)
                            else None})
            if out:
                return out
    return []


# ---------------------------------------------------------------- names
_EXTRA = {
    "burma": "MMR", "myanmar (burma)": "MMR", "kyrgyz republic": "KGZ", "lao pdr": "LAO",
    "lao people's democratic republic": "LAO", "west bank and gaza": "PSE",
    "west bank/gaza": "PSE", "palestinian territories": "PSE", "palestine": "PSE",
    "congo (kinshasa)": "COD", "congo, dem. rep.": "COD", "drc": "COD",
    "congo (brazzaville)": "COG", "congo, rep.": "COG", "republic of the congo": "COG",
    "eswatini": "SWZ", "gambia, the": "GMB", "micronesia": "FSM",
    "micronesia, fed. sts.": "FSM", "federated states of micronesia": "FSM",
    "marshall islands": "MHL", "palau": "PLW", "viet nam": "VNM",
    "united republic of tanzania": "TZA", "syrian arab republic": "SYR",
    "egypt, arab rep.": "EGY", "yemen, rep.": "YEM", "iran, islamic rep.": "IRN",
    "venezuela, rb": "VEN", "turkiye": "TUR", "cabo verde": "CPV", "kosovo": "XKX",
    "north macedonia": "MKD", "moldova": "MDA", "republic of moldova": "MDA",
    "south sudan": "SSD", "sudan": "SDN", "timor-leste": "TLS", "east timor": "TLS",
    "slovak republic": "SVK", "russian federation": "RUS", "korea, dem. people's rep.": "PRK",
    "sao tome and principe": "STP", "st. lucia": "LCA", "saint lucia": "LCA",
    "dominica": "DMA", "grenada": "GRD", "kiribati": "KIR", "tuvalu": "TUV", "nauru": "NRU",
}


def norm(name):
    s = unicodedata.normalize("NFKD", name or "")
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    s = s.replace("’", "'").replace("&", "and").replace("*", "")
    return " ".join(s.lower().split()).strip(" .")


_EXTRA_N = {norm(k): v for k, v in _EXTRA.items()}


def wb_name_map(meta):
    return {norm(m.get("name") or ""): iso for iso, m in meta.items() if m.get("name")}


def iso_for(name, wbmap=None):
    n = norm(name)
    if n in _EXTRA_N:
        return _EXTRA_N[n]
    if wbmap and n in wbmap:
        return wbmap[n]
    return ac.ged_iso3(n)


def build_dose(rows, wbmap=None):
    """CGD rows -> ({iso3: {name, share, cut_usd, retained_usd, gni_pct}}, info)."""
    out = {}
    info = {"unmatched": [], "duplicates": [], "missing_values": []}
    for r in rows:
        iso = iso_for(r["name"], wbmap)
        if iso is None:
            info["unmatched"].append([r["name"], r["cut_musd"]])
            continue
        if r["pct"] is None or r["cut_musd"] is None:
            info["missing_values"].append(r["name"])
            continue
        if iso in out:
            info["duplicates"].append(r["name"])
            continue
        pct = min(max(r["pct"], 0.0), 100.0)
        cut = max(r["cut_musd"], 0.0) * 1e6
        ret = cut * (100.0 - pct) / pct if pct > 0 else None
        out[iso] = {"name": r["name"], "share": pct / 100.0, "cut_usd": cut,
                    "retained_usd": ret, "gni_pct": r["gni"]}
    tot = sum(max(r["cut_musd"] or 0.0, 0.0) for r in rows)
    lost = sum(max(c or 0.0, 0.0) for _, c in info["unmatched"])
    info["unmatched_cut_share"] = lost / tot if tot > 0 else 0.0
    return out, info


# ---------------------------------------------------------------- statistics
def coef(y, cols, j=1):
    """OLS coefficient j (0 = constant) of y on a constant and cols."""
    n = len(y)
    K = len(cols) + 1
    if n <= K:
        raise ValueError("too few observations")
    X = [[1.0] + [float(c[i]) for c in cols] for i in range(n)]
    XtX = [[sum(X[i][a] * X[i][b] for i in range(n)) for b in range(K)] for a in range(K)]
    Xty = [sum(X[i][a] * y[i] for i in range(n)) for a in range(K)]
    return ac.solve(XtX, Xty)[j]


def strata_by_quantile(v, k=STRATA):
    """Equal-size quantile groups 0..k-1 of v (ties broken by position)."""
    order = sorted(range(len(v)), key=lambda i: (v[i], i))
    g = [0] * len(v)
    for rank, i in enumerate(order):
        g[i] = rank * k // len(v)
    return g


def ri_coef(y, S, controls, strata, reps=ac.RI_REPS, seed=ac.SEED):
    """Two-sided RI p for the coefficient on S (controls held fixed), permuting S within
    strata. Returns (b0, p, permutations used)."""
    b0 = coef(y, [S] + controls)
    rng = random.Random(seed)
    groups = defaultdict(list)
    for i, g in enumerate(strata):
        groups[g].append(i)
    hits = done = 0
    for _ in range(reps):
        perm = list(S)
        for idx in groups.values():
            vals = [S[i] for i in idx]
            rng.shuffle(vals)
            for i, v in zip(idx, vals):
                perm[i] = v
        try:
            b = coef(y, [perm] + controls)
        except ValueError:
            continue
        done += 1
        if abs(b) >= abs(b0) - 1e-12:
            hits += 1
    return b0, (hits + 1.0) / (done + 1.0), done


def corr(a, b):
    n = len(a)
    if n <= 2:
        raise ValueError("too few observations")
    ma, mb = sum(a) / n, sum(b) / n
    sab = sum((x - ma) * (y - mb) for x, y in zip(a, b))
    saa = sum((x - ma) ** 2 for x in a)
    sbb = sum((y - mb) ** 2 for y in b)
    if saa <= 0 or sbb <= 0:
        raise ValueError("constant variable")
    r = sab / math.sqrt(saa * sbb)
    if abs(r) >= 1.0:
        return {"r": r, "p": 0.0, "n": n}
    t = r * math.sqrt((n - 2) / (1.0 - r * r))
    return {"r": r, "p": ac.t_two_sided_p(t, n - 2), "n": n}


def quantile(v, q):
    s = sorted(v)
    return s[int(q * (len(s) - 1))]


# ---------------------------------------------------------------- analysis
def analyze(counts, pop, meta, agency, dose, reps=ac.RI_REPS):
    res = {"models": {}, "descriptive": {}}
    base = ac.build_sample(pop, meta)
    U_pre = mc.per_person(agency[("usaid", "disb")], pop, mc.PRE_YEARS)
    U_plc = mc.per_person(agency[("usaid", "disb")], pop, mc.PLACEBO_YEARS)
    units = [u for u in base if u in dose]
    res["descriptive"]["base_not_in_cgd_table"] = [u for u in base if u not in dose]
    res["descriptive"]["cgd_not_in_base"] = sorted(u for u in dose if u not in set(base))
    samples = {"global": units,
               "africa": [u for u in units if ac.is_africa(u, meta)],
               "rest": [u for u in units if not ac.is_africa(u, meta)]}
    res["descriptive"]["sample_sizes"] = {k: len(v) for k, v in samples.items()}
    if len(units) < MIN_COUNTRIES:
        res["stopped"] = "fewer than %d matched countries (%d)" % (MIN_COUNTRIES, len(units))
        return res
    lg = math.log1p
    shares = [dose[u]["share"] for u in units]
    res["descriptive"]["share_quantiles"] = {
        "q10": quantile(shares, .1), "q25": quantile(shares, .25), "q50": quantile(shares, .5),
        "q75": quantile(shares, .75), "q90": quantile(shares, .9)}
    iqr = quantile(shares, .75) - quantile(shares, .25)
    res["descriptive"]["share_iqr"] = iqr
    e_all = [lg(U_pre.get(u, 0.0)) for u in units]
    res["descriptive"]["E_usaid_iqr"] = quantile(e_all, .75) - quantile(e_all, .25)

    win = {w: tuple(ac.parse_ym(x) for x in ac.WINDOWS[w])
           for w in ("primary", "extended", "placebo")}

    def series(us, wname, outcome):
        f, l, s = win[wname]
        Y = ac.panel(counts, us, f, l, outcome)
        d = ac.deltas(Y, f, l, s)
        pre = [sum(row[:s - f]) / float(s - f) for row in Y]
        return d, pre

    def fit(name, func):
        try:
            res["models"][name] = func()
        except (ValueError, ZeroDivisionError) as exc:
            res["models"][name] = {"error": str(exc)}

    def t1(us, d, E, extra=None, loo=False):
        S = [dose[u]["share"] for u in us]
        controls = [E] + ([extra] if extra is not None else [])
        names = ["S", "E_usaid"] + (["pre_level"] if extra is not None else [])
        f = mc.ols_hc1(d, [S] + controls, names)
        b, p, done = ri_coef(d, S, controls, strata_by_quantile(E), reps)
        se = f["se"][1]
        out = {"beta_S": f["beta"][1], "se_hc1": se, "p_hc1": f["p"][1], "p_ri": p,
               "ri_reps": done, "ci95_normal": [f["beta"][1] - 1.96 * se,
                                                f["beta"][1] + 1.96 * se],
               "beta_S_times_iqr": f["beta"][1] * iqr, "fit": mc.compact(f), "n": len(d)}
        if loo:
            vals = []
            for j in range(len(us)):
                cols = [[c[i] for i in range(len(us)) if i != j] for c in [S] + controls]
                vals.append((coef([d[i] for i in range(len(us)) if i != j], cols), us[j]))
            vals.sort()
            out["leave_one_out"] = {"min": vals[0][0], "min_dropped": vals[0][1],
                                    "max": vals[-1][0], "max_dropped": vals[-1][1],
                                    "sign_flips": [u for v, u in vals
                                                   if (v > 0) != (f["beta"][1] > 0)]}
        return out

    for oc in ("events", "deaths"):
        for wname in ("primary", "extended", "placebo"):
            Ex = U_plc if wname == "placebo" else U_pre
            for sname, us in samples.items():
                if wname == "extended" and sname != "global":
                    continue
                d, _ = series(us, wname, oc)
                E = [lg(Ex.get(u, 0.0)) for u in us]
                loo = (wname == "primary" and sname == "global" and oc == "events")
                fit("T1|%s|%s|%s" % (wname, sname, oc),
                    lambda us=us, d=d, E=E, loo=loo: t1(us, d, E, loo=loo))

        us = samples["global"]
        d, pre = series(us, "primary", oc)
        E = [lg(U_pre.get(u, 0.0)) for u in us]
        fit("T1v|primary|global|%s" % oc, lambda d=d, E=E, pre=pre: t1(us, d, E, extra=pre))
        cut_pc = [lg(dose[u]["cut_usd"] / pop[u]) for u in us]
        fit("T2|primary|global|%s" % oc,
            lambda d=d, c=cut_pc, E=E: {"fit": mc.compact(
                mc.ols_hc1(d, [c, E], ["log_cut_pc", "E_usaid"]))})
        keep = [i for i, u in enumerate(us) if dose[u]["retained_usd"] is not None]

        def t3(d=d, keep=keep):
            c = [lg(dose[us[i]]["cut_usd"] / pop[us[i]]) for i in keep]
            r = [lg(dose[us[i]]["retained_usd"] / pop[us[i]]) for i in keep]
            f = mc.ols_hc1([d[i] for i in keep], [c, r], ["log_cut_pc", "log_retained_pc"])
            return {"fit": mc.compact(f), "cut_minus_retained": mc.diff_test(f, 1, 2)}
        fit("T3|primary|global|%s" % oc, t3)

    us = samples["global"]
    _, pre = series(us, "primary", "events")
    S = [dose[u]["share"] for u in us]
    E = [lg(U_pre.get(u, 0.0)) for u in us]
    fit("D|corr_S_pre_events", lambda: corr(S, pre))
    fit("D|corr_S_E_usaid", lambda: corr(S, E))
    return res


def summarize(key, m):
    if "error" in m:
        return "- %s: error: %s" % (key, m["error"])
    if "beta_S" in m:
        return ("- %s: b_S %.4f (SE %.4f, p HC1 %.3f, p RI %.4f), 95%% CI [%.4f, %.4f], "
                "b_S x IQR %.4f, n %d" % (key, m["beta_S"], m["se_hc1"], m["p_hc1"], m["p_ri"],
                                          m["ci95_normal"][0], m["ci95_normal"][1],
                                          m["beta_S_times_iqr"], m["n"]))
    if "cut_minus_retained" in m:
        c = m["fit"]["coef"]
        dt = m["cut_minus_retained"]
        return ("- %s: b_cut %.4f (p %.3f), b_retained %.4f (p %.3f), diff %.4f (p %.3f), n %d"
                % (key, c["log_cut_pc"]["beta"], c["log_cut_pc"]["p"],
                   c["log_retained_pc"]["beta"], c["log_retained_pc"]["p"], dt["diff"], dt["p"],
                   m["fit"]["n"]))
    if "fit" in m:
        parts = ["%s %.4f (p %.3f)" % (nm, v["beta"], v["p"]) for nm, v in m["fit"]["coef"].items()]
        return "- %s: %s, n %d" % (key, "; ".join(parts), m["fit"]["n"])
    if "r" in m:
        return "- %s: r %.3f, p %.4f, n %d" % (key, m["r"], m["p"], m["n"])
    return "- %s: %s" % (key, json.dumps(m, sort_keys=True))


# ---------------------------------------------------------------- main
def fetch_cgd(data_dir, log):
    path = os.path.join(data_dir, "cgd_usaid_cuts_country_level.html")
    errors = []
    for url in (CGD_URL, CGD_ARCHIVE_URL):
        try:
            mc.download(url, path)
            with open(path, encoding="utf-8", errors="replace") as fh:
                rows = parse_cut_table(fh.read())
            if rows:
                log["cgd_source_used"] = url
                return rows, path
            errors.append("%s: no country table" % url)
            os.remove(path)
        except RuntimeError as exc:
            errors.append(str(exc))
    raise SystemExit("CGD country table not found: %s" % errors)


def run(data_dir, out_dir, reps=ac.RI_REPS):
    os.makedirs(out_dir, exist_ok=True)
    j = os.path.join
    log = {"version": __version__,
           "started": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
           "sources": {"ged": ac.GED_URL, "candidate": ac.CAND_URL, "agency": mc.AGENCY_URL,
                       "cgd": CGD_URL, "wb_pop": ac.WB_POP_URL, "wb_meta": ac.WB_META_URL}}
    paths = {"ged": mc.download(ac.GED_URL, j(data_dir, "ged261-csv.zip")),
             "cand": mc.download(ac.CAND_URL, j(data_dir, "GEDEvent_v26_01_26_09.csv")),
             "wb_pop": mc.download(ac.WB_POP_URL, j(data_dir, "wb_pop_2023.json")),
             "wb_meta": mc.download(ac.WB_META_URL, j(data_dir, "wb_meta.json")),
             "agency": mc.download(mc.AGENCY_URL, j(data_dir, "us_foreign_aid_implementing.csv"))}
    rows, paths["cgd"] = fetch_cgd(data_dir, log)
    log["sha256"] = {k: ac.sha256_file(p) for k, p in paths.items()}
    log["cgd_rows"] = len(rows)

    first_all, ged_last = ac.parse_ym("2021-02"), ac.parse_ym("2025-12")
    counts, unmatched, _ = ac.count_events(
        ac.iter_csv_rows(ac.open_csv_maybe_zip(paths["ged"])), first_all, ged_last)
    ged_months = sorted({m for (_, m) in counts})
    log["ged_last_month"] = ac.ym_str(ged_months[-1]) if ged_months else None
    if not ged_months or ged_months[-1] < ged_last:
        raise SystemExit("GED 26.1 does not reach 2025-12; stopping as pre-registered")
    ac.count_events(ac.iter_csv_rows(ac.open_csv_maybe_zip(paths["cand"])),
                    ac.parse_ym("2026-01"), ac.parse_ym("2026-09"), counts, unmatched)
    log["ged_unmatched_country_names"] = dict(unmatched.most_common())

    with open(paths["agency"], encoding="utf-8-sig", newline="") as fh:
        agency, _ = mc.read_agency(ac.iter_csv_rows(fh))
    with open(paths["wb_pop"], encoding="utf-8") as fh:
        pop_json = json.load(fh)
    with open(paths["wb_meta"], encoding="utf-8") as fh:
        meta_json = json.load(fh)
    pop, meta = ac.read_wb(pop_json, meta_json)
    dose, info = build_dose(rows, wb_name_map(meta))
    log["cgd_match"] = info

    results = analyze(counts, pop, meta, agency, dose, reps)
    log["finished"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    results["meta"] = log
    with open(j(out_dir, "dose_results.json"), "w", encoding="utf-8") as fh:
        json.dump(results, fh, indent=1, sort_keys=True)

    U_pre = mc.per_person(agency[("usaid", "disb")], pop, mc.PRE_YEARS)
    f, l, s = (ac.parse_ym(x) for x in ac.WINDOWS["primary"])
    with open(j(out_dir, "dose_table.csv"), "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["iso3", "cgd_name", "in_sample", "share_terminated", "cut_usd",
                    "retained_usd", "usaid_disb_fy22_24_per_person", "events_pre_per_month",
                    "events_post_per_month"])
        base = set(ac.build_sample(pop, meta))
        for u in sorted(dose):
            pre = [counts.get((u, m), [0] * 5)[0] for m in range(f, s)]
            post = [counts.get((u, m), [0] * 5)[0] for m in range(s, l + 1)]
            r = dose[u]
            w.writerow([u, r["name"], int(u in base), round(r["share"], 4), round(r["cut_usd"]),
                        "" if r["retained_usd"] is None else round(r["retained_usd"]),
                        round(U_pre.get(u, 0.0), 4), round(sum(pre) / len(pre), 3),
                        round(sum(post) / len(post), 3)])

    lines = ["# aid-cut-violence dose %s results (PREREG-3)" % __version__, ""]
    if "stopped" in results:
        lines.append("STOPPED: " + results["stopped"])
    lines += ["## Descriptive", ""]
    for k, v in sorted(results["descriptive"].items()):
        lines.append("- %s: %s" % (k, json.dumps(v, sort_keys=True)))
    lines += ["", "## CGD table match", "", "- %s" % json.dumps(info, sort_keys=True),
              "", "## Models", ""]
    for key in sorted(results["models"]):
        lines.append(summarize(key, results["models"][key]))
    with open(j(out_dir, "dose_results.md"), "w", encoding="utf-8") as fh:
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
