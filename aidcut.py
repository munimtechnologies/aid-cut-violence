#!/usr/bin/env python3
# aid-cut-violence -- Apache-2.0
# Copyright 2026 Munim, Inc. Made by MV2 of Munim, Inc. with AI agents.
"""Did the 2025 USAID shutdown raise organized violence worldwide, or only in Africa?

A pre-registered, country-month difference-in-differences on fully open data:
  outcome  : UCDP Georeferenced Event Dataset (GED 26.1, final, through 2025)
             + UCDP Candidate Events (Jan-Sep 2026) for the extended window
  exposure : US foreign assistance per person, FY2022-2024 mean disbursements
             (ForeignAssistance.gov country summary, constant USD)
  people   : World Bank SP.POP.TOTL 2023; World Bank region and income group

See PREREGISTRATION.md for the frozen design and predictions. Standard library only.

    python aidcut.py --data-dir data --out-dir out
"""
import argparse
import csv
import hashlib
import io
import json
import math
import os
import random
import sys
import time
import urllib.request
import zipfile
from collections import Counter, defaultdict

__version__ = "0.1.0"

GED_URL = "https://ucdp.uu.se/downloads/ged/ged261-csv.zip"
CAND_URL = "https://ucdp.uu.se/downloads/candidateged/GEDEvent_v26_01_26_09.csv"
FA_URL = "https://s3.amazonaws.com/files.explorer.devtechlab.com/us_foreign_aid_country.csv"
WB_POP_URL = ("https://api.worldbank.org/v2/country/all/indicator/SP.POP.TOTL"
              "?date=2023&format=json&per_page=20000")
WB_META_URL = "https://api.worldbank.org/v2/country?format=json&per_page=400"

# Countries whose 2025 violence was dominated by inter-state wars and ceasefire
# diplomacy, and whose US assistance is mostly security assistance that the
# January 2025 freeze did not stop. Excluded from the primary sample, included
# in robustness check "incl_wars".
WAR_EXCLUDE = ("UKR", "RUS", "ISR", "PSE")
# African countries outside the World Bank "Sub-Saharan Africa" region.
NORTH_AFRICA = ("DZA", "EGY", "LBY", "MAR", "TUN", "DJI")
FA_CODE_ALIASES = {"XKS": "XKX", "KSV": "XKX"}

MIN_POP = 1_000_000
EXPOSURE_YEARS = (2022, 2023, 2024)
RI_REPS = 9999
SEED = 20261117


# ---------------------------------------------------------------- months
def ym_index(year, month):
    return year * 12 + (month - 1)


def ym_str(i):
    return "%04d-%02d" % (i // 12, i % 12 + 1)


def parse_ym(s):
    """'2025-01' -> month index."""
    return ym_index(int(s[0:4]), int(s[5:7]))


def parse_month(s):
    """UCDP date_start ('2025-01-03', '2025-01-03 00:00:00.000') -> month index."""
    s = (s or "").strip()
    if len(s) < 7 or s[4] != "-":
        raise ValueError("bad date %r" % s)
    return ym_index(int(s[0:4]), int(s[5:7]))


def event_bin(month, shock):
    """Quarter-sized bins relative to the shock month: shock..shock+2 -> 0,
    shock-3..shock-1 -> -1, and so on (floor division)."""
    return (month - shock) // 3


WINDOWS = {
    # name: (first month, last month, shock month)
    "primary": ("2023-02", "2025-12", "2025-02"),
    "extended": ("2023-02", "2026-09", "2025-02"),
    "placebo": ("2021-02", "2023-12", "2023-02"),
}

# ---------------------------------------------------------------- names
_GED_NAMES = {
    "afghanistan": "AFG", "albania": "ALB", "algeria": "DZA", "angola": "AGO",
    "argentina": "ARG", "armenia": "ARM", "azerbaijan": "AZE", "bahrain": "BHR",
    "bangladesh": "BGD", "belarus": "BLR", "benin": "BEN", "bhutan": "BTN",
    "bolivia": "BOL", "bosnia-herzegovina": "BIH", "bosnia and herzegovina": "BIH",
    "botswana": "BWA", "brazil": "BRA", "burkina faso": "BFA", "burundi": "BDI",
    "cambodia": "KHM", "cameroon": "CMR", "central african republic": "CAF",
    "chad": "TCD", "chile": "CHL", "china": "CHN", "colombia": "COL",
    "comoros": "COM", "congo": "COG", "republic of congo": "COG",
    "congo, republic of": "COG", "dr congo": "COD",
    "democratic republic of congo": "COD", "democratic republic of the congo": "COD",
    "costa rica": "CRI", "croatia": "HRV", "cuba": "CUB", "cyprus": "CYP",
    "djibouti": "DJI", "dominican republic": "DOM", "ecuador": "ECU", "egypt": "EGY",
    "el salvador": "SLV", "equatorial guinea": "GNQ", "eritrea": "ERI",
    "eswatini": "SWZ", "kingdom of eswatini": "SWZ", "swaziland": "SWZ",
    "ethiopia": "ETH", "fiji": "FJI", "france": "FRA", "gabon": "GAB",
    "gambia": "GMB", "the gambia": "GMB", "georgia": "GEO", "germany": "DEU",
    "ghana": "GHA", "guatemala": "GTM", "guinea": "GIN", "guinea-bissau": "GNB",
    "guyana": "GUY", "haiti": "HTI", "honduras": "HND", "india": "IND",
    "indonesia": "IDN", "iran": "IRN", "iraq": "IRQ", "israel": "ISR",
    "palestine": "PSE", "state of palestine": "PSE", "ivory coast": "CIV",
    "cote d'ivoire": "CIV", "jamaica": "JAM", "jordan": "JOR", "kazakhstan": "KAZ",
    "kenya": "KEN", "kosovo": "XKX", "kuwait": "KWT", "kyrgyzstan": "KGZ",
    "laos": "LAO", "lebanon": "LBN", "lesotho": "LSO", "liberia": "LBR",
    "libya": "LBY", "macedonia, fyr": "MKD", "north macedonia": "MKD",
    "macedonia": "MKD", "madagascar": "MDG", "malawi": "MWI", "malaysia": "MYS",
    "mali": "MLI", "mauritania": "MRT", "mexico": "MEX", "moldova": "MDA",
    "mongolia": "MNG", "montenegro": "MNE", "morocco": "MAR", "mozambique": "MOZ",
    "myanmar": "MMR", "burma": "MMR", "namibia": "NAM", "nepal": "NPL",
    "nicaragua": "NIC", "niger": "NER", "nigeria": "NGA", "north korea": "PRK",
    "oman": "OMN", "pakistan": "PAK", "panama": "PAN", "papua new guinea": "PNG",
    "paraguay": "PRY", "peru": "PER", "philippines": "PHL", "qatar": "QAT",
    "russia": "RUS", "rwanda": "RWA", "saudi arabia": "SAU", "senegal": "SEN",
    "serbia": "SRB", "sierra leone": "SLE", "solomon islands": "SLB",
    "somalia": "SOM", "south africa": "ZAF", "south korea": "KOR",
    "south sudan": "SSD", "spain": "ESP", "sri lanka": "LKA", "sudan": "SDN",
    "suriname": "SUR", "syria": "SYR", "tajikistan": "TJK", "tanzania": "TZA",
    "thailand": "THA", "timor-leste": "TLS", "east timor": "TLS", "togo": "TGO",
    "trinidad and tobago": "TTO", "tunisia": "TUN", "turkey": "TUR",
    "turkiye": "TUR", "turkmenistan": "TKM", "uganda": "UGA", "ukraine": "UKR",
    "united arab emirates": "ARE", "united kingdom": "GBR",
    "united states of america": "USA", "united states": "USA", "uruguay": "URY",
    "uzbekistan": "UZB", "venezuela": "VEN", "vietnam": "VNM", "yemen": "YEM",
    "zambia": "ZMB", "zimbabwe": "ZWE", "cape verde": "CPV", "cabo verde": "CPV",
    "sao tome and principe": "STP", "belgium": "BEL", "netherlands": "NLD",
    "sweden": "SWE", "norway": "NOR", "denmark": "DNK", "austria": "AUT",
    "australia": "AUS", "new zealand": "NZL", "canada": "CAN", "japan": "JPN",
    "greece": "GRC", "italy": "ITA", "poland": "POL", "romania": "ROU",
    "hungary": "HUN", "bulgaria": "BGR", "slovakia": "SVK", "czech republic": "CZE",
    "czechia": "CZE", "lithuania": "LTU", "latvia": "LVA", "estonia": "EST",
    "finland": "FIN", "ireland": "IRL", "portugal": "PRT", "switzerland": "CHE",
    "slovenia": "SVN", "singapore": "SGP", "brunei": "BRN", "maldives": "MDV",
    "mauritius": "MUS", "seychelles": "SYC", "vanuatu": "VUT", "samoa": "WSM",
    "tonga": "TON", "belize": "BLZ", "barbados": "BRB", "bahamas": "BHS",
}


def ged_iso3(name):
    """UCDP country name (e.g. 'DR Congo (Zaire)', 'Yemen (North Yemen)') -> ISO3 or None."""
    if not name:
        return None
    key = name.strip().lower()
    if key in _GED_NAMES:
        return _GED_NAMES[key]
    base = key.split(" (")[0].strip()
    return _GED_NAMES.get(base)


# ---------------------------------------------------------------- statistics
def asinh(x):
    return math.log(x + math.sqrt(x * x + 1.0))


def _betacf(a, b, x):
    tiny = 1e-300
    qab, qap, qam = a + b, a + 1.0, a - 1.0
    c, d = 1.0, 1.0 - qab * x / qap
    d = 1.0 / (d if abs(d) > tiny else tiny)
    h = d
    for m in range(1, 20000):
        m2 = 2 * m
        aa = m * (b - m) * x / ((qam + m2) * (a + m2))
        d = 1.0 + aa * d
        d = 1.0 / (d if abs(d) > tiny else tiny)
        c = 1.0 + aa / c
        c = c if abs(c) > tiny else tiny
        h *= d * c
        aa = -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))
        d = 1.0 + aa * d
        d = 1.0 / (d if abs(d) > tiny else tiny)
        c = 1.0 + aa / c
        c = c if abs(c) > tiny else tiny
        delta = d * c
        h *= delta
        if abs(delta - 1.0) < 1e-14:
            break
    return h


def betainc(a, b, x):
    """Regularized incomplete beta I_x(a, b)."""
    if x <= 0.0:
        return 0.0
    if x >= 1.0:
        return 1.0
    lbt = (math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b)
           + a * math.log(x) + b * math.log(1.0 - x))
    bt = math.exp(lbt)
    if x < (a + 1.0) / (a + b + 2.0):
        return bt * _betacf(a, b, x) / a
    return 1.0 - bt * _betacf(b, a, 1.0 - x) / b


def gammaincc(a, x):
    """Regularized upper incomplete gamma Q(a, x)."""
    if x <= 0.0:
        return 1.0
    if x < a + 1.0:
        term = s = 1.0 / a
        ap = a
        for _ in range(1000):
            ap += 1.0
            term *= x / ap
            s += term
            if abs(term) < abs(s) * 1e-15:
                break
        return 1.0 - s * math.exp(-x + a * math.log(x) - math.lgamma(a))
    tiny = 1e-300
    b = x + 1.0 - a
    c = 1.0 / tiny
    d = 1.0 / b
    h = d
    for i in range(1, 1000):
        an = -i * (i - a)
        b += 2.0
        d = an * d + b
        d = d if abs(d) > tiny else tiny
        c = b + an / c
        c = c if abs(c) > tiny else tiny
        d = 1.0 / d
        delta = d * c
        h *= delta
        if abs(delta - 1.0) < 1e-15:
            break
    return math.exp(-x + a * math.log(x) - math.lgamma(a)) * h


def t_two_sided_p(t, df):
    if df <= 0 or t != t:
        return float("nan")
    return betainc(df / 2.0, 0.5, df / (df + t * t))


def chi2_sf(x, k):
    return gammaincc(k / 2.0, x / 2.0)


def f_sf(f, d1, d2):
    if f <= 0:
        return 1.0
    return betainc(d2 / 2.0, d1 / 2.0, d2 / (d2 + d1 * f))


def solve(A, b):
    """Gauss-Jordan with partial pivoting; A is KxK (list of lists), b length K."""
    n = len(A)
    M = [list(A[i]) + [b[i]] for i in range(n)]
    for col in range(n):
        piv = max(range(col, n), key=lambda r: abs(M[r][col]))
        if abs(M[piv][col]) < 1e-14:
            raise ValueError("singular matrix")
        M[col], M[piv] = M[piv], M[col]
        p = M[col][col]
        M[col] = [v / p for v in M[col]]
        for r in range(n):
            if r != col and M[r][col] != 0.0:
                f = M[r][col]
                M[r] = [vr - f * vc for vr, vc in zip(M[r], M[col])]
    return [M[i][n] for i in range(n)]


def inverse(A):
    n = len(A)
    cols = [solve(A, [1.0 if i == j else 0.0 for i in range(n)]) for j in range(n)]
    return [[cols[j][i] for j in range(n)] for i in range(n)]


def demean(A, groups=None):
    """Residual of an n x T balanced panel after unit effects and group-by-month
    effects (units nested in groups). groups=None means plain month effects."""
    n = len(A)
    T = len(A[0])
    B = []
    for row in A:
        m = sum(row) / T
        B.append([v - m for v in row])
    if groups is None:
        groups = [0] * n
    idx = defaultdict(list)
    for i, g in enumerate(groups):
        idx[g].append(i)
    for members in idx.values():
        k = len(members)
        for t in range(T):
            m = sum(B[i][t] for i in members) / k
            for i in members:
                B[i][t] -= m
    return B


def fe_ols(Y, Xs, groups=None):
    """OLS of Y on Xs with unit and (group x) month fixed effects, balanced panel.
    Standard errors clustered by unit (CR1). Returns dict."""
    n = len(Y)
    T = len(Y[0])
    K = len(Xs)
    Yd = demean(Y, groups)
    Xd = [demean(X, groups) for X in Xs]
    XtX = [[0.0] * K for _ in range(K)]
    Xty = [0.0] * K
    for i in range(n):
        for t in range(T):
            xs = [Xd[k][i][t] for k in range(K)]
            y = Yd[i][t]
            for a in range(K):
                xa = xs[a]
                if xa == 0.0:
                    continue
                Xty[a] += xa * y
                row = XtX[a]
                for b in range(K):
                    row[b] += xa * xs[b]
    beta = solve(XtX, Xty)
    meat = [[0.0] * K for _ in range(K)]
    for i in range(n):
        s = [0.0] * K
        for t in range(T):
            u = Yd[i][t] - sum(beta[k] * Xd[k][i][t] for k in range(K))
            for k in range(K):
                s[k] += Xd[k][i][t] * u
        for a in range(K):
            for b in range(K):
                meat[a][b] += s[a] * s[b]
    bread = inverse(XtX)
    ng = len(set(groups)) if groups is not None else 1
    N = n * T
    ktot = K + n + ng * T - ng
    G = n
    c = (G / (G - 1.0)) * ((N - 1.0) / max(N - ktot, 1.0))
    tmp = [[sum(bread[a][k] * meat[k][b] for k in range(K)) for b in range(K)] for a in range(K)]
    V = [[c * sum(tmp[a][k] * bread[k][b] for k in range(K)) for b in range(K)] for a in range(K)]
    se = [math.sqrt(max(V[k][k], 0.0)) for k in range(K)]
    tval = [beta[k] / se[k] if se[k] > 0 else float("nan") for k in range(K)]
    p = [t_two_sided_p(tv, G - 1) for tv in tval]
    return {"beta": beta, "se": se, "t": tval, "p": p, "vcov": V, "clusters": G,
            "n_obs": N}


def group_demean_vec(v, groups=None):
    if groups is None:
        groups = [0] * len(v)
    sums = defaultdict(float)
    cnt = Counter(groups)
    for x, g in zip(v, groups):
        sums[g] += x
    return [x - sums[g] / cnt[g] for x, g in zip(v, groups)]


def did_closed(E, delta, groups=None):
    """Pooled DiD slope with unit + (group x) month FE in a balanced panel equals the
    cross-sectional slope of delta_i (post mean - pre mean) on E_i, E demeaned
    within group."""
    e = group_demean_vec(E, groups)
    den = sum(x * x for x in e)
    if den == 0:
        return float("nan")
    return sum(x * d for x, d in zip(e, delta)) / den


def ri_pvalue(E, delta, groups=None, reps=RI_REPS, seed=SEED):
    """Two-sided randomization-inference p-value: permute exposure across units
    (within groups if given)."""
    b0 = did_closed(E, delta, groups)
    rng = random.Random(seed)
    if groups is None:
        groups = [0] * len(E)
    members = defaultdict(list)
    for i, g in enumerate(groups):
        members[g].append(i)
    e = group_demean_vec(E, groups)
    den = sum(x * x for x in e)
    hits = 0
    for _ in range(reps):
        perm = list(e)
        for idx in members.values():
            vals = [e[i] for i in idx]
            rng.shuffle(vals)
            for i, v in zip(idx, vals):
                perm[i] = v
        b = sum(x * d for x, d in zip(perm, delta)) / den
        if abs(b) >= abs(b0) - 1e-12:
            hits += 1
    return b0, (hits + 1.0) / (reps + 1.0)


# ---------------------------------------------------------------- data
def download(url, path, tries=4):
    if os.path.exists(path) and os.path.getsize(path) > 0:
        return path
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    last = None
    for k in range(tries):
        try:
            req = urllib.request.Request(url, headers={
                "User-Agent": "aid-cut-violence/%s (MV2, Munim, Inc.; mv2@munimtech.com)" % __version__})
            with urllib.request.urlopen(req, timeout=300) as r, open(path + ".part", "wb") as f:
                while True:
                    chunk = r.read(1 << 20)
                    if not chunk:
                        break
                    f.write(chunk)
            os.replace(path + ".part", path)
            return path
        except Exception as exc:  # noqa: BLE001
            last = exc
            time.sleep(5 * (k + 1))
    raise RuntimeError("download failed: %s (%s)" % (url, last))


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _set_csv_limit():
    lim = sys.maxsize
    while True:
        try:
            csv.field_size_limit(lim)
            return
        except OverflowError:
            lim //= 10


def iter_csv_rows(fh):
    """Yield dicts with lower-case keys from a text file handle."""
    _set_csv_limit()
    rdr = csv.reader(fh)
    bom = chr(0xFEFF)
    header = [h.replace(bom, "").strip().lower() for h in next(rdr)]
    for row in rdr:
        if len(row) < len(header):
            row = row + [""] * (len(header) - len(row))
        yield dict(zip(header, row))


def open_csv_maybe_zip(path):
    if path.lower().endswith(".zip"):
        z = zipfile.ZipFile(path)
        names = [n for n in z.namelist() if n.lower().endswith(".csv")]
        if not names:
            raise RuntimeError("no csv in %s" % path)
        return io.TextIOWrapper(z.open(names[0]), encoding="utf-8-sig", newline="")
    return open(path, encoding="utf-8-sig", newline="")


def count_events(rows, first, last, counts=None, unmatched=None, by_year=None):
    """Aggregate UCDP event rows into counts[(iso3, month)] = [events, deaths,
    ev_state, ev_nonstate, ev_onesided] for first <= month <= last."""
    counts = counts if counts is not None else defaultdict(lambda: [0, 0, 0, 0, 0])
    unmatched = unmatched if unmatched is not None else Counter()
    by_year = by_year if by_year is not None else Counter()
    for r in rows:
        try:
            m = parse_month(r.get("date_start", ""))
        except ValueError:
            continue
        if m < first or m > last:
            continue
        iso = ged_iso3(r.get("country", ""))
        if iso is None:
            unmatched[r.get("country", "")] += 1
            continue
        try:
            best = int(float(r.get("best") or 0))
        except ValueError:
            best = 0
        tv = (r.get("type_of_violence") or "").strip()
        c = counts[(iso, m)]
        c[0] += 1
        c[1] += best
        if tv == "1":
            c[2] += 1
        elif tv == "2":
            c[3] += 1
        elif tv == "3":
            c[4] += 1
        by_year[m // 12] += 1
    return counts, unmatched, by_year


def read_fa(rows):
    """ForeignAssistance.gov country summary -> {kind: {iso3: {fy: constant_usd}}}, type names."""
    out = {"disb": defaultdict(lambda: defaultdict(float)),
           "oblig": defaultdict(lambda: defaultdict(float))}
    types = Counter()
    for r in rows:
        tname = (r.get("transaction type name") or "").strip()
        types[tname] += 1
        tl = tname.lower()
        if "disburse" in tl or "spent" in tl:
            kind = "disb"
        elif "obligat" in tl:
            kind = "oblig"
        else:
            continue
        iso = (r.get("country code") or "").strip().upper()
        iso = FA_CODE_ALIASES.get(iso, iso)
        try:
            fy = int(float(r.get("fiscal year") or 0))
            amt = float(r.get("constant_amount") or 0)
        except ValueError:
            continue
        out[kind][iso][fy] += amt
    return out, types


def exposure(fa_kind, pop, years=EXPOSURE_YEARS):
    """{iso3: log(1 + mean annual constant USD per person)}; also raw USD per person."""
    E, pc = {}, {}
    for iso, p in pop.items():
        if not p:
            continue
        tot = sum(fa_kind.get(iso, {}).get(y, 0.0) for y in years) / len(years)
        pc[iso] = max(tot, 0.0) / p
        E[iso] = math.log1p(pc[iso])
    return E, pc


def read_wb(pop_json, meta_json):
    pop = {}
    for rec in pop_json[1] or []:
        iso = rec.get("countryiso3code") or ""
        if iso and rec.get("value") is not None:
            pop[iso] = float(rec["value"])
    meta = {}
    for rec in meta_json[1] or []:
        if (rec.get("region") or {}).get("value") == "Aggregates":
            continue
        meta[rec["id"]] = {"name": rec.get("name"),
                           "region": (rec.get("region") or {}).get("id"),
                           "income": (rec.get("incomeLevel") or {}).get("id")}
    return pop, meta


def build_sample(pop, meta, exclude=WAR_EXCLUDE, min_pop=MIN_POP):
    keep = []
    for iso, m in meta.items():
        if m["income"] == "HIC":
            continue
        if pop.get(iso, 0) < min_pop:
            continue
        if iso in exclude:
            continue
        keep.append(iso)
    return sorted(keep)


def is_africa(iso, meta):
    return meta.get(iso, {}).get("region") == "SSF" or iso in NORTH_AFRICA


OUTCOMES = ("events", "deaths", "any_event", "ev_state", "ev_nonstate", "ev_onesided")


def panel(counts, units, first, last, outcome):
    rows = []
    for iso in units:
        row = []
        for m in range(first, last + 1):
            c = counts.get((iso, m))
            if outcome == "any_event":
                row.append(1.0 if c and c[0] > 0 else 0.0)
            else:
                k = OUTCOMES.index(outcome)
                k = {0: 0, 1: 1, 3: 2, 4: 3, 5: 4}[k]
                row.append(asinh(c[k]) if c else 0.0)
        rows.append(row)
    return rows


def deltas(Y, first, last, shock):
    out = []
    pre_idx = [m - first for m in range(first, shock)]
    post_idx = [m - first for m in range(shock, last + 1)]
    for row in Y:
        pre = sum(row[i] for i in pre_idx) / len(pre_idx)
        post = sum(row[i] for i in post_idx) / len(post_idx)
        out.append(post - pre)
    return out


def pooled(counts, units, Evec, first, last, shock, outcome, groups=None, reps=RI_REPS):
    Y = panel(counts, units, first, last, outcome)
    X = [[Evec[i] * (1.0 if m >= shock else 0.0) for m in range(first, last + 1)]
         for i in range(len(units))]
    fit = fe_ols(Y, [X], groups)
    d = deltas(Y, first, last, shock)
    b_cf, p_ri = ri_pvalue(Evec, d, groups, reps=reps)
    return {"beta": fit["beta"][0], "beta_closed_form": b_cf, "se_cr1": fit["se"][0],
            "p_cluster_t": fit["p"][0], "p_ri": p_ri, "ri_reps": reps,
            "n_countries": len(units), "n_months": last - first + 1,
            "n_exposed": sum(1 for e in Evec if e > 0)}, d


def leave_one_out(Evec, d, units, groups=None):
    res = []
    for j in range(len(units)):
        E2 = Evec[:j] + Evec[j + 1:]
        d2 = d[:j] + d[j + 1:]
        g2 = None if groups is None else groups[:j] + groups[j + 1:]
        res.append((did_closed(E2, d2, g2), units[j]))
    res.sort()
    return {"min": res[0][0], "min_dropped": res[0][1], "max": res[-1][0],
            "max_dropped": res[-1][1],
            "sign_flips": [u for b, u in res if (b > 0) != (did_closed(Evec, d) > 0)]}


def event_study(counts, units, Evec, first, last, shock, outcome, ref=-1):
    Y = panel(counts, units, first, last, outcome)
    bins = sorted({event_bin(m, shock) for m in range(first, last + 1)})
    bins = [k for k in bins if k != ref]
    Xs = []
    for k in bins:
        Xs.append([[Evec[i] * (1.0 if event_bin(m, shock) == k else 0.0)
                    for m in range(first, last + 1)] for i in range(len(units))])
    fit = fe_ols(Y, Xs)
    pre = [j for j, k in enumerate(bins) if k < ref]
    out = {"ref_bin": ref, "bins": []}
    for j, k in enumerate(bins):
        months = [m for m in range(first, last + 1) if event_bin(m, shock) == k]
        out["bins"].append({"bin": k, "from": ym_str(months[0]), "to": ym_str(months[-1]),
                            "beta": fit["beta"][j], "se": fit["se"][j], "p": fit["p"][j]})
    if pre:
        b = [fit["beta"][j] for j in pre]
        V = [[fit["vcov"][a][c] for c in pre] for a in pre]
        Vi = inverse(V)
        W = sum(b[a] * Vi[a][c] * b[c] for a in range(len(pre)) for c in range(len(pre)))
        q = len(pre)
        out["pretrend"] = {"wald": W, "q": q, "p_chi2": chi2_sf(W, q),
                           "p_F": f_sf(W / q, q, fit["clusters"] - 1)}
    return out


# ---------------------------------------------------------------- main
def run(data_dir, out_dir, reps=RI_REPS):
    os.makedirs(out_dir, exist_ok=True)
    log = {"version": __version__, "started": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
           "sources": {"ged": GED_URL, "candidate": CAND_URL, "fa": FA_URL,
                       "wb_pop": WB_POP_URL, "wb_meta": WB_META_URL}}
    ged = download(GED_URL, os.path.join(data_dir, "ged261-csv.zip"))
    cand = download(CAND_URL, os.path.join(data_dir, "GEDEvent_v26_01_26_09.csv"))
    fa = download(FA_URL, os.path.join(data_dir, "us_foreign_aid_country.csv"))
    wbp = download(WB_POP_URL, os.path.join(data_dir, "wb_pop_2023.json"))
    wbm = download(WB_META_URL, os.path.join(data_dir, "wb_meta.json"))
    log["sha256"] = {os.path.basename(p): sha256_file(p) for p in (ged, cand, fa, wbp, wbm)}

    first_all = parse_ym("2021-02")
    ged_last = parse_ym("2025-12")
    cand_first, cand_last = parse_ym("2026-01"), parse_ym("2026-09")

    counts, unmatched, by_year = count_events(iter_csv_rows(open_csv_maybe_zip(ged)),
                                              first_all, ged_last)
    ged_months = sorted({m for (_, m) in counts})
    if not ged_months or ged_months[-1] < ged_last:
        raise SystemExit("GED 26.1 does not reach 2025-12 (last month %s); stopping as "
                         "pre-registered" % (ym_str(ged_months[-1]) if ged_months else "none"))
    by_year_c = Counter()
    count_events(iter_csv_rows(open_csv_maybe_zip(cand)), cand_first, cand_last,
                 counts, unmatched, by_year_c)
    cand_months = sorted({m for (_, m) in counts if m >= cand_first})
    log["ged_events_by_year"] = dict(sorted(by_year.items()))
    log["candidate_events_by_year"] = dict(sorted(by_year_c.items()))
    log["candidate_last_month"] = ym_str(cand_months[-1]) if cand_months else None
    log["unmatched_country_names"] = dict(unmatched.most_common())

    with open(fa, encoding="utf-8-sig", newline="") as fh:
        fa_data, fa_types = read_fa(iter_csv_rows(fh))
    log["fa_transaction_types"] = dict(fa_types)
    with open(wbp, encoding="utf-8") as fh:
        pop_json = json.load(fh)
    with open(wbm, encoding="utf-8") as fh:
        meta_json = json.load(fh)
    pop, meta = read_wb(pop_json, meta_json)

    E_disb, pc_disb = exposure(fa_data["disb"], pop)
    E_obl, _ = exposure(fa_data["oblig"], pop)

    samples = {}
    base = build_sample(pop, meta)
    samples["global"] = base
    samples["africa"] = [u for u in base if is_africa(u, meta)]
    samples["rest"] = [u for u in base if not is_africa(u, meta)]
    log["sample_sizes"] = {k: len(v) for k, v in samples.items()}
    in_sample_events = sum(c[0] for (iso, m), c in counts.items() if iso in set(base))
    log["events_in_sample_2021_2026"] = in_sample_events
    tot_matched = sum(c[0] for c in counts.values())
    log["unmatched_share"] = sum(unmatched.values()) / max(sum(unmatched.values()) + tot_matched, 1)

    results = {"meta": log, "main": {}, "robustness": {}, "event_study": {}}

    for wname, (f, l, s) in WINDOWS.items():
        f, l, s = parse_ym(f), parse_ym(l), parse_ym(s)
        for sname, units in samples.items():
            Ev = [E_disb[u] for u in units]
            for oc in OUTCOMES:
                r, d = pooled(counts, units, Ev, f, l, s, oc, reps=reps)
                if wname == "primary" and oc in ("events", "deaths"):
                    r["leave_one_out"] = leave_one_out(Ev, d, units)
                results["main"]["%s|%s|%s" % (wname, sname, oc)] = r

    f, l, s = (parse_ym(x) for x in WINDOWS["primary"])
    rob = results["robustness"]
    wide = build_sample(pop, meta, exclude=())
    for oc in ("events", "deaths"):
        rob["incl_wars|" + oc] = pooled(counts, wide, [E_disb[u] for u in wide], f, l, s, oc,
                                        reps=reps)[0]
        rob["obligations|" + oc] = pooled(counts, base, [E_obl[u] for u in base], f, l, s, oc,
                                          reps=reps)[0]
        pos = sorted(pc_disb[u] for u in base if pc_disb[u] > 0)
        q75 = pos[int(0.75 * (len(pos) - 1))] if pos else 0.0
        rob["top_quartile|" + oc] = pooled(counts, base,
                                           [1.0 if pc_disb[u] >= q75 and pc_disb[u] > 0 else 0.0
                                            for u in base], f, l, s, oc, reps=reps)[0]
        rob["top_quartile|" + oc]["q75_usd_per_person"] = q75
        groups = [meta[u]["region"] for u in base]
        rob["region_month_fe|" + oc] = pooled(counts, base, [E_disb[u] for u in base], f, l, s,
                                              oc, groups=groups, reps=reps)[0]
        nosdn = [u for u in base if u != "SDN"]
        rob["drop_sudan|" + oc] = pooled(counts, nosdn, [E_disb[u] for u in nosdn], f, l, s, oc,
                                         reps=reps)[0]
        a = results["main"]["primary|africa|%s" % oc]
        b = results["main"]["primary|rest|%s" % oc]
        diff = a["beta"] - b["beta"]
        se = math.sqrt(a["se_cr1"] ** 2 + b["se_cr1"] ** 2)
        z = diff / se if se > 0 else float("nan")
        rob["africa_minus_rest|" + oc] = {"diff": diff, "se": se, "z": z,
                                          "p_normal": math.erfc(abs(z) / math.sqrt(2))}

    for wname in ("primary", "extended"):
        f, l, s = (parse_ym(x) for x in WINDOWS[wname])
        for sname in ("global", "africa", "rest"):
            units = samples[sname]
            results["event_study"]["%s|%s|events" % (wname, sname)] = event_study(
                counts, units, [E_disb[u] for u in units], f, l, s, "events")

    # country table
    f, l, s = (parse_ym(x) for x in WINDOWS["primary"])
    with open(os.path.join(out_dir, "country_table.csv"), "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["iso3", "name", "wb_region", "africa", "pop_2023", "us_disb_usd_per_person",
                    "E_log1p", "events_pre_per_month", "events_post_per_month",
                    "deaths_pre_per_month", "deaths_post_per_month"])
        for u in base:
            pre = [counts.get((u, m), [0] * 5) for m in range(f, s)]
            post = [counts.get((u, m), [0] * 5) for m in range(s, l + 1)]
            w.writerow([u, meta[u]["name"], meta[u]["region"], int(is_africa(u, meta)),
                        int(pop[u]), round(pc_disb[u], 4), round(E_disb[u], 5),
                        round(sum(c[0] for c in pre) / len(pre), 3),
                        round(sum(c[0] for c in post) / len(post), 3),
                        round(sum(c[1] for c in pre) / len(pre), 2),
                        round(sum(c[1] for c in post) / len(post), 2)])

    log["finished"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    with open(os.path.join(out_dir, "results.json"), "w", encoding="utf-8") as fh:
        json.dump(results, fh, indent=1, sort_keys=True)
    lines = ["# aid-cut-violence %s results" % __version__, ""]
    lines.append("| window | sample | outcome | beta | SE (CR1) | p cluster-t | p RI | countries |")
    lines.append("|---|---|---|---|---|---|---|---|")
    for key, r in results["main"].items():
        wn, sn, oc = key.split("|")
        lines.append("| %s | %s | %s | %.4f | %.4f | %.3f | %.4f | %d |" % (
            wn, sn, oc, r["beta"], r["se_cr1"], r["p_cluster_t"], r["p_ri"], r["n_countries"]))
    lines += ["", "## Robustness (primary window, global)", ""]
    for key, r in rob.items():
        if "beta" in r:
            lines.append("- %s: beta %.4f, SE %.4f, p RI %.4f" % (key, r["beta"], r["se_cr1"],
                                                                  r["p_ri"]))
        else:
            lines.append("- %s: diff %.4f, SE %.4f, p %.3f" % (key, r["diff"], r["se"],
                                                               r["p_normal"]))
    lines += ["", "## Pre-trend tests (event study, events)", ""]
    for key, es in results["event_study"].items():
        pt = es.get("pretrend", {})
        lines.append("- %s: Wald %.2f on %d, p(F) %.3f" % (key, pt.get("wald", float("nan")),
                                                          pt.get("q", 0), pt.get("p_F", float("nan"))))
    with open(os.path.join(out_dir, "results.md"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")
    print("\n".join(lines))
    print(json.dumps({k: v for k, v in log.items() if k != "sources"}, indent=1))
    return results


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--data-dir", default="data")
    ap.add_argument("--out-dir", default="out")
    ap.add_argument("--reps", type=int, default=RI_REPS)
    a = ap.parse_args(argv)
    run(a.data_dir, a.out_dir, a.reps)


if __name__ == "__main__":
    main()
