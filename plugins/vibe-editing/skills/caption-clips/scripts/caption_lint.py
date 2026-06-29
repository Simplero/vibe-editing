#!/usr/bin/env python3
"""caption_lint.py — self-audit gate that enforces the LOCKED the reference editor/Creator caption rules
(references/caption_style_corpus.md) on a generated spice .ass BEFORE burn, so we one-shot it.

Parses the on-screen text + tags out of the text-layer .ass and flags every rule violation.
Run it inside generate_spice (or standalone) right after the .ass is written; non-zero exit = fix needed.

Usage: python3 caption_lint.py <captions.ass> [--strict]
"""
import sys, re, argparse, json
from pathlib import Path

# words that must never appear spelled-out (money/number formatting rule)
SPELLED = re.compile(r"\b(thousand|million|billion|percent|dollars?)\b", re.I)
# Note 2026-06-16: dropped "grand" from this list — caused false positives on "grand opening",
# "grand slam", "grand piano", etc. spice_normalize.py still converts "<digit> grand" → "$<n>K"
# pre-burn, so a remaining "grand" in captions is almost certainly a non-money use. Leaving
# "grand" in this regex caused r3 GiveAwayBest to FAIL caption_lint on the burned phrase
# "say grand opening" — a legitimate phrase, not a money error.
GRAND_AS_MONEY = re.compile(r"\b\d+\s*grand\b", re.I)  # ONLY flag "grand" when preceded by a number
# proper-noun allowlist is unknowable here; we only flag a capital that is NOT sentence/I/$ context
IFORM = re.compile(r"^(I|I'm|I'd|I've|I'll|I)$")
# the locked guest (second-speaker) caption color, RRGGBB. generate_spice writes it as the
# ASS BGR token \1c&H0000CBFE&. This is the "yellow" that must appear on any 2-speaker clip.
GUEST_HEX = "FECB00"
# matches a primary-color override block, e.g. \1c&H0000CBFE&
_C1 = re.compile(r"\\1c(&H[0-9A-Fa-f]+&)")


def _ass_color_to_rgb(tok):
    """ASS color token (&HAABBGGRR& or &HBBGGRR&) -> RRGGBB upper, or None if unparseable."""
    h = re.sub(r"[^0-9A-Fa-f]", "", tok)   # drop &, H
    if len(h) == 8:                         # AABBGGRR -> drop alpha
        h = h[2:]
    if len(h) != 6:
        return None
    bb, gg, rr = h[0:2], h[2:4], h[4:6]
    return (rr + gg + bb).upper()


def _text_layer_path(path):
    """Prefer the *_text.ass crisp layer if present — premiere mode writes the per-word
    \\1c colors there (the main .ass also carries black shadow layers we don't want to read)."""
    cand = Path(path).with_name(Path(path).stem + "_text.ass")
    return str(cand) if cand.exists() else str(path)


def guest_cue_count(ass_path, guest_hex=GUEST_HEX):
    """Count rendered cues whose text has >=1 word set to the GUEST color (default FECB00).

    Returns (n_guest_cues, n_total_cues). This is the SINGLE source of truth for "does the
    rendered ASS contain any guest/yellow color?" — used both by --expect-guest below and,
    by import, by the caption-app worker's output invariant gate (worker/caption_invariant.py).
    """
    gh = guest_hex.upper().lstrip("#")
    cues = cues_from_ass(_text_layer_path(ass_path))
    n = 0
    for _body, _plain, blocks in cues:
        colors = {_ass_color_to_rgb(c) for b in blocks for c in _C1.findall(b)}
        if gh in colors:
            n += 1
    return n, len(cues)


def cues_from_ass(path):
    """Return [(text_with_tags, plain_text, [override_blocks])] for each text-layer Dialogue."""
    out = []
    for ln in Path(path).read_text(errors="ignore").splitlines():
        if not ln.startswith("Dialogue:"):
            continue
        # field 10 = text (after 9 commas)
        body = ln.split(",", 9)[-1]
        plain = re.sub(r"\{[^}]*\}", "", body).strip()
        if not plain:
            continue
        blocks = re.findall(r"\{([^}]*)\}", body)
        out.append((body, plain, blocks))
    return out


def lint(path, strict=False, expect_guest=False, guest_hex=GUEST_HEX):
    text_ass = _text_layer_path(path)
    cues = cues_from_ass(text_ass)
    issues = []
    def add(sev, rule, detail): issues.append((sev, rule, detail))

    seen_texts = set()
    for body, plain, blocks in cues:
        raw = plain.split()
        # count LOGICAL words the way the chunker does: a number/$ token + a short unit
        # ("2 yrs", "$55 M", "10 min") is ONE logical word, not two.
        words, k = [], 0
        while k < len(raw):
            cur = raw[k]
            if k + 1 < len(raw) and re.search(r"[\d$%]", cur) and re.fullmatch(r"[A-Za-z]{1,3}\.?", raw[k+1]):
                cur = cur + " " + raw[k+1]; k += 1
            words.append(cur); k += 1
        # 1) chunk size <=3 words / <=18 chars (single line)
        if len(words) > 3:
            add("warn", "chunk>3w", f">3 words: {plain!r}")
        if len(plain) > 18:
            add("warn", "chunk>18c", f">18 chars: {plain!r}")
        if "\\N" in body or "\n" in plain:
            add("warn", "multiline", f"line break: {plain!r}")
        # 2) spelled-out money/number
        if SPELLED.search(plain):
            add("err", "spelled-number", f"spell-out money/number (use $/K/M/%): {plain!r}")
        # 3) banned sentence punctuation (. and , dropped; ? ! .. - kept)
        if re.search(r"[.,](?=\s|$)", plain.replace("..", "")) and not re.search(r"\d[.,]\d", plain):
            add("warn", "punct", f"stray .,/period or comma: {plain!r}")
        # 4) size axis is ON (2026-06-11): per-word size bumps are allowed (The reference editor enlarges key words),
        # but only within the locked tiers (base 100 / emph 125 / strong 150 / peak 180). Flag anything
        # bigger than the peak (~185) — that's the oversized look Operator rejected (the old 250).
        for b in blocks:
            for m in re.findall(r"\\fsc[xy]([0-9]+)", b):
                if int(m) > 185:
                    add("err", "oversize", f"\\fscx/y={m} exceeds peak 180 (rejected-250 territory): {plain!r}")
        # 4a) SIZE UNIFORM PER CUE (Operator 2026-06-11): a size bump goes on a single-word caption OR the
        # WHOLE line — NEVER one word inside a multi-word line (looks broken; the reference editor never did it).
        word_sizes = [int(re.search(r"\\fscx([0-9]+)", b).group(1)) if re.search(r"\\fscx([0-9]+)", b)
                      else 100 for b in blocks if "\\fn" in b]
        if len(word_sizes) > 1 and len(set(word_sizes)) > 1:
            add("err", "size-nonuniform", f"mixed sizes {sorted(set(word_sizes))} in a multi-word line "
                f"(size must be uniform per cue): {plain!r}")
        # 4b) ONE VOICE PER CUE — never mix white (Speaker) + yellow (guest) on one line.
        # Each word token carries a \1c color; >1 distinct color in a cue = a speaker straddle
        # (the chunker must break at every voice change). The reference editor's cues are always monochrome.
        cue_colors = {c for b in blocks for c in re.findall(r"\\1c(&H[0-9A-Fa-f]+&)", b)}
        if len(cue_colors) > 1:
            add("err", "mixed-voice", f"cue mixes {len(cue_colors)} voice colors (Speaker+guest on one line): {plain!r}")
        # 5) stray ALL-CAPS or mid-word capitals (lowercase except I-forms / proper nouns)
        for w in words:
            bare = re.sub(r"[^A-Za-z']", "", w)
            if not bare:
                continue
            if bare[0].isupper() and not IFORM.match(bare) and not w.startswith("$"):
                # could be a legit proper noun — advisory only
                add("info", "capital", f"capitalized word (ok if proper noun): {w!r} in {plain!r}")
        seen_texts.add(plain.lower())

    # 6) --expect-guest — the ABSENCE check (mirror of the mixed-voice rule above, which only
    # catches TOO MANY colors). On a clip KNOWN to be 2-speaker, there must be >=1 guest-colored
    # cue; zero means it shipped all one color (the all-white Q&A bug). This is the same check the
    # caption-app worker gate runs on the render output — reusable here for standalone linting.
    if expect_guest:
        gh = guest_hex.upper().lstrip("#")
        n_guest, n_tot = guest_cue_count(text_ass, gh)
        if n_guest == 0:
            add("err", "no-guest-color",
                f"--expect-guest: ZERO cues colored guest ({gh}) across {n_tot} cues — a 2-speaker "
                f"clip rendered all one color (no yellow / second speaker)")
        else:
            print(f"caption_lint: --expect-guest OK — {n_guest}/{n_tot} cues guest-colored ({gh})")

    # report
    errs = [i for i in issues if i[0] == "err"]
    warns = [i for i in issues if i[0] == "warn"]
    infos = [i for i in issues if i[0] == "info"]
    print(f"caption_lint: {len(cues)} cues | {len(errs)} errors, {len(warns)} warnings, {len(infos)} advisories  [{text_ass}]")
    for sev in ("err", "warn") + (("info",) if strict else ()):
        for s, rule, detail in issues:
            if s == sev:
                print(f"  [{sev.upper():4}] {rule}: {detail}")
    return 1 if errs or (strict and warns) else 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("ass")
    ap.add_argument("--strict", action="store_true", help="treat warnings as failures")
    ap.add_argument("--expect-guest", action="store_true",
                    help="fail if the rendered ASS has ZERO guest-colored cues (use on clips "
                         "known to be 2-speaker — catches the all-white Q&A bug)")
    ap.add_argument("--guest-hex", default=GUEST_HEX,
                    help=f"guest color RRGGBB to require with --expect-guest (default {GUEST_HEX})")
    a = ap.parse_args()
    sys.exit(lint(a.ass, a.strict, expect_guest=a.expect_guest, guest_hex=a.guest_hex))
