#!/usr/bin/env python3
"""The reference editor transcript normalization (runs AFTER normalize_simple) — LOCKED caption-text SOP.

SOP subtitle rules (Operator SOP, baked 2026-06-04 — DO NOT regress these):
  LOWERCASE        : everything except proper nouns + I-forms (I, I'm, I'd, I've, I'll). (normalize_simple)
  SINGLE LINE      : captions are single-line by default (chunker: <=18 chars AND <=3 words). A 2nd
                     line / "(parenthetical explainer)" is a deliberate exception, never the default.
  TIME UNITS       : "<number> minutes/years/..." -> "<digit> min/yrs/..." merged into ONE token.
  ET CETERA        : "et cetera"/"etcetera" -> "etc."
  MONEY + SYMBOLS  : (the rules I previously missed — now automatic)
    * "$" PREFIX is ALWAYS kept on money numbers ($1, $2.5K, $600K, $3M).
    * SYMBOLS not words:  "<n> dollars" -> "$<n>",  "<n> percent|percentage(s)" -> "<n>%".
    * MAGNITUDE merges into the number:  "$<n> thousand|million|billion" -> "$<n>K|M|B"
      ("$46.2 million" -> "$46.2M", "$17 million" -> "$17M"); "a|one million [dollars]" -> "$1M".
    * ABBREVIATE big money (>= $100,000):  $100,000 -> $100K, $250,000 -> $250K,
      $1,200,000 -> $1.2M, $20,000,000 -> $20M, $3,000,000,000 -> $3B.
      Below $100,000 is left as-is ($1, $190, $1,600, $10,000, $75,000 all fine).
  PROPER NOUNS the base normalizer misses.
Numbers stay WHITE (the director handles color; money is NEVER yellow). Money/unit tokens are emitted
as ONE token so the number never splits from its unit/magnitude across caption lines.
Usage: spice_normalize.py <in.json> <out.json>
"""
import sys, json, re
from pathlib import Path

NUMWORD = {"zero":"0","one":"1","two":"2","three":"3","four":"4","five":"5","six":"6","seven":"7",
           "eight":"8","nine":"9","ten":"10","eleven":"11","twelve":"12","thirteen":"13","fourteen":"14",
           "fifteen":"15","sixteen":"16","seventeen":"17","eighteen":"18","nineteen":"19","twenty":"20",
           "thirty":"30","forty":"40","fifty":"50","sixty":"60","seventy":"70","eighty":"80","ninety":"90"}
UNIT = {"minute":"min","minutes":"min","hour":"hr","hours":"hr","year":"yrs","years":"yrs",
        "second":"sec","seconds":"sec","week":"wk","weeks":"wks","month":"mo","months":"mos",
        "day":"day","days":"days"}
MAG = {"thousand":"K","million":"M","billion":"B","trillion":"T"}
# Spoken SLANG money magnitudes: a number right before one of these is compact money with a symbol —
# "100 grand"->$100K, "50 k"->$50K, "3 mil"/"3 m"->$3M.  ⚠️ KEEP IN SYNC with spice_format.py's apply_money
# (the standalone caption path uses spice_format; this qa path uses spice_normalize — same SOP, two files).
SLANG_MAG = {"grand":"K", "k":"K", "mil":"M", "m":"M"}
DOLLAR_WORDS = {"dollar","dollars","buck","bucks"}
PERCENT_WORDS = {"percent","percents","percentage","percentages"}
PROPER = {"apollo":"Apollo","creed":"Creed","bangladesh":"Bangladesh",
          "princeton":"Princeton","samaritan":"Samaritan"}
# ACRONYMS stay UPPERCASE (the lowercase rule would mangle them — StageQA V3 shipped "not doing the md"
# instead of "MD", 2026-06-17). Business-Q&A acronyms; matched on the bare standalone word only, so they
# never fire inside a larger word (e.g. "command" ≠ "md"). Add new ones here as they come up.
ACRONYM = {"md":"MD","ceo":"CEO","cfo":"CFO","coo":"COO","cto":"CTO","cmo":"CMO","vp":"VP","gp":"GP",
           "roi":"ROI","roas":"ROAS","ltv":"LTV","cac":"CAC","kpi":"KPI","crm":"CRM","seo":"SEO",
           "llc":"LLC","mba":"MBA","dtc":"DTC","b2b":"B2B","b2c":"B2C","saas":"SaaS","ai":"AI","hr":"HR",
           "ceos":"CEOs","kpis":"KPIs"}
DOWNCASE = {"may"}  # normalize_simple capitalizes the month "May"; in speech it's usually the verb

def bare(w): return re.sub(r"[^a-z0-9]", "", w.lower())
def tail(w):
    m = re.search(r"[.,?!]+$", w.strip()); return m.group(0) if m else ""

NUM_IN = re.compile(r"(\$?)(\d[\d,]*(?:\.\d+)?)")  # a number, maybe $-prefixed, commas + decimal

def fmt_mant(x):
    s = f"{x:.1f}"
    return s[:-2] if s.endswith(".0") else s

def abbrev_money(numstr):
    """numstr like '100,000' / '46.2' -> '$<abbrev>' if >= $100,000, else None (leave as-is)."""
    try:
        v = float(numstr.replace(",", ""))
    except ValueError:
        return None
    if v >= 1e9: return "$" + fmt_mant(v / 1e9) + "B"
    if v >= 1e6: return "$" + fmt_mant(v / 1e6) + "M"
    if v >= 1e5: return "$" + fmt_mant(v / 1e3) + "K"
    return None

def find_num(tok):
    """Split the FIRST number out of a token: (prefix, dollar_sign, numstr, suffix) or None."""
    m = NUM_IN.search(tok)
    if not m: return None
    return tok[:m.start()], m.group(1), m.group(2), tok[m.end():]

def main():
    inp, out = Path(sys.argv[1]), Path(sys.argv[2])
    d = json.loads(inp.read_text())
    words = d.get("words", d) if isinstance(d, dict) else d
    res = []
    i = 0
    n = len(words)
    while i < n:
        w = words[i]; raw = w["word"]; b = bare(raw)
        nxt = words[i + 1] if i + 1 < n else None
        nb = bare(nxt["word"]) if nxt else ""
        nn = words[i + 2] if i + 2 < n else None
        nnb = bare(nn["word"]) if nn else ""

        # word-number FRACTION in a money context: "<numword> and a half|quarter <money unit>"
        # -> "$<n.5|n.25><K|M>" ("three and a half mil" -> "$3.5M"). Gated to a money unit so non-money
        # phrases ("three and a half years/hours") are untouched. Mirrors spice_format.py's money Pass 0.
        if b in NUMWORD and not b.isdigit() and i + 4 < n:
            s1, s2, s3, s4 = (bare(words[i + k]["word"]) for k in range(1, 5))
            _fmag = MAG.get(s4) or SLANG_MAG.get(s4)
            if s1 == "and" and s2 == "a" and s3 in ("half", "quarter") and _fmag:
                frac = "5" if s3 == "half" else "25"
                m = dict(w); m["word"] = f"${NUMWORD[b]}.{frac}{_fmag}{tail(words[i+4]['word'])}"; m["end"] = words[i + 4]["end"]
                res.append(m); i += 5; continue

        # number (digit or number-word, NOT 'a') + TIME unit -> "<digit> <abbrev>"
        if (b.isdigit() or (b in NUMWORD and b not in ("a", "an"))) and nb in UNIT:
            digit = b if b.isdigit() else NUMWORD[b]
            m = dict(w); m["word"] = f"{digit} {UNIT[nb]}{tail(nxt['word'])}"; m["end"] = nxt["end"]
            res.append(m); i += 2; continue

        # MULTIPLIER: "<number> times" -> "<digit>X"  ("two times" -> "2X", "10 times" -> "10X")  [reels lesson]
        if (b.isdigit() or (b in NUMWORD and b not in ("a", "an"))) and nb == "times":
            digit = b if b.isdigit() else NUMWORD[b]
            m = dict(w); m["word"] = f"{digit}X{tail(nxt['word'])}"; m["end"] = nxt["end"]
            res.append(m); i += 2; continue
        # lone "10x"/"3x" -> "10X"
        _mx = re.fullmatch(r"(\d+)x", b)
        if _mx:
            m = dict(w); m["word"] = f"{_mx.group(1)}X{tail(raw)}"; res.append(m); i += 1; continue
        # ORDINAL/RANK: "number <n>" -> "#<n>"  ("number one" -> "#1")  [reels lesson]
        if b == "number" and (nb.isdigit() or (nb in NUMWORD and nb not in ("a", "an"))):
            digit = nb if nb.isdigit() else NUMWORD[nb]
            m = dict(w); m["word"] = f"#{digit}{tail(nxt['word'])}"; m["end"] = nxt["end"]
            res.append(m); i += 2; continue

        fn = find_num(raw)
        # "<word-number> million|thousand|billion [dollars]" -> "$<n>K|M|B"
        # ("three million" -> "$3M", "five thousand dollars" -> "$5K")  [2026-06-14: was
        # only catching digit forms via fn; word forms were leaving "three million"
        # un-normalized → caption_lint spelled-number error.]
        if b in NUMWORD and b not in ("a", "an", "one") and (nb in MAG or nb in SLANG_MAG):
            digit = NUMWORD[b]
            end = nxt["end"]; consume = 2; tnode = nxt
            if nnb in DOLLAR_WORDS:
                end = nn["end"]; consume = 3; tnode = nn
            mag = MAG.get(nb) or SLANG_MAG.get(nb)
            m = dict(w); m["word"] = f"${digit}{mag}{tail(tnode['word'])}"; m["end"] = end
            res.append(m); i += consume; continue
        # "a|one million [dollars]" -> "$1M"   (idiomatic 'a million' = 1)
        if b in ("a", "an", "one") and (nb in MAG or nb in SLANG_MAG):
            end = nxt["end"]; consume = 2; tnode = nxt
            if nnb in DOLLAR_WORDS:
                end = nn["end"]; consume = 3; tnode = nn
            m = dict(w); m["word"] = "$1" + (MAG.get(nb) or SLANG_MAG.get(nb)) + tail(tnode["word"]); m["end"] = end
            res.append(m); i += consume; continue
        # "$<n>"/<n> + magnitude [+ dollars] -> "$<n>K|M|B"  (thousand/million/billion + slang grand/k/mil/m)
        _mag = MAG.get(nb) or SLANG_MAG.get(nb)
        if fn and _mag:
            prefix, _dol, numstr, _suf = fn
            end = nxt["end"]; consume = 2; tnode = nxt
            if nnb in DOLLAR_WORDS:
                end = nn["end"]; consume = 3; tnode = nn
            m = dict(w); m["word"] = f"{prefix}${numstr}{_mag}{tail(tnode['word'])}"; m["end"] = end
            res.append(m); i += consume; continue
        # "<n> dollars" -> "$<n>"
        if fn and nb in DOLLAR_WORDS:
            prefix, _dol, numstr, _suf = fn
            m = dict(w); m["word"] = f"{prefix}${numstr}{tail(nxt['word'])}"; m["end"] = nxt["end"]
            res.append(m); i += 2; continue
        # "<n> percent" -> "<n>%"
        if fn and nb in PERCENT_WORDS:
            prefix, _dol, numstr, _suf = fn
            m = dict(w); m["word"] = f"{prefix}{numstr}%{tail(nxt['word'])}"; m["end"] = nxt["end"]
            res.append(m); i += 2; continue
        # standalone $ amount >= $100,000 -> abbreviate in place
        if fn and fn[1] == "$":
            prefix, _dol, numstr, suf = fn
            ab = abbrev_money(numstr)
            if ab:
                m = dict(w); m["word"] = prefix + ab + suf
                res.append(m); i += 1; continue

        # "et cetera" -> "etc."
        if b == "et" and nb == "cetera":
            m = dict(w); m["word"] = "etc."; m["end"] = nxt["end"]; res.append(m); i += 2; continue
        if b == "etcetera":
            w = dict(w); w["word"] = "etc." + tail(raw)
        # proper-noun capitalization / acronym uppercasing / forced downcase
        if b in PROPER:
            w = dict(w); w["word"] = PROPER[b] + tail(raw)
        elif b in ACRONYM:
            w = dict(w); w["word"] = ACRONYM[b] + tail(raw)
        elif b in DOWNCASE and raw != raw.lower():
            w = dict(w); w["word"] = raw.lower()
        res.append(w); i += 1
    if isinstance(d, dict):
        d["words"] = res; out.write_text(json.dumps(d, indent=2))
    else:
        out.write_text(json.dumps(res, indent=2))
    print(f"spice_normalize: {len(words)} -> {len(res)} tokens -> {out.name}")

if __name__ == "__main__":
    main()
