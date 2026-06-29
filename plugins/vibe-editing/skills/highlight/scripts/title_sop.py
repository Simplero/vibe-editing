"""
Title SOP — the subscriber-optimized titler, shared by highlight_post.py.

A highlights channel grows on SUBSCRIBER CONVERSION (subs_per_1k_views), NOT raw CTR — and the
two are DECOUPLED: the highest-CTR title styles ("Why...", vague curiosity, reaction/personality)
tend to be the WORST subscriber converters, while "You/..." declaratives, quoted questions,
contrarian takes, and "Watch this if you're [struggle]" convert best even at lower CTR. So these
prompts optimize for the SUBSCRIBE, not the click.

Full doctrine: references/title_rules.md

Two entry points:
  - build_title1_system() / build_ab_system() : system prompts for an LLM titler (needs an API key).
  - local_title()                              : deterministic, key-free fallback that picks the
                                                 strongest line from the transcript.
"""
import re

# Ranked, subs-first pattern guidance shared by both prompts.
_PATTERNS = """USE THESE PATTERNS, BEST FIRST (ranked by real subscriber conversion):
1. "Watch this if you're [specific struggle]"   e.g. Watch this if you're working hard, but not making progress
2. "You / Your [blunt truth or command]"         e.g. You need to upsell.  ·  You're Stuck Because You Can't Keep Customers
3. A quoted question a viewer would also ask     e.g. "Should I start a new business or keep my current one?"  (KEEP the quotation marks)
4. "Helping a [business chunked up one level] [the specific tension]"   e.g. Helping a Lead-Gen Company Create a Reverse Affiliate Offer
   (chunk the niche up: Glamping Resort -> Resort Business; name the TENSION, not just "scale")
5. "How to [specific outcome]"
AVOID leading with "Why..." or vague curiosity: best CTR, WORST subscribers. Use it only if explicitly told this upload is a reach play."""

_HARD_RULES = """HARD RULES:
- Steal the moment: use the strongest near-verbatim line, or the real number, from THIS transcript.
- <= 70 characters. ONE idea. Fully self-contained (a stranger understands it cold, no context bleed).
- Quoted-question titles MUST keep their quotation marks.
- No clickbait teasers ("..." endings, "you won't believe"). No em-dashes (use periods). No formula labels (HELPING, WHY) in the output.
- NEVER mention mom, mother, or family."""


def build_title1_system(examples: str = "") -> str:
    """System prompt for the ONE published title."""
    ex = f"\nSTYLE REFERENCE — real titles from this channel:\n{examples}\n" if examples else ""
    return f"""You write ONE YouTube title for a clip on a business Q&A / hotline / podcast \
highlights channel.

GOAL: SUBSCRIBERS, not clicks. This channel grows on subscriber conversion. The highest-CTR
title styles are the worst subscriber converters, so write the title that pulls the RIGHT
viewer (who then subscribes), not the title that wins the most clicks.

{_PATTERNS}
{ex}
{_HARD_RULES}
- Output the title only, on one line."""


def build_ab_system(examples: str = "") -> str:
    """System prompt for the 2 A/B alternates."""
    ex = f"\nSTYLE REFERENCE — real titles from this channel:\n{examples}\n" if examples else ""
    return f"""Write 2 alternate YouTube titles (an A/B test) for a clip on a business \
highlights channel. They must take DIFFERENT angles from the existing scheduled title and from each other.

GOAL: SUBSCRIBERS, not clicks. (The highest-CTR styles convert the fewest subscribers — write
for the right viewer who subscribes.)

Use two of these angles, re-ranked for subscriber conversion, genuinely different from the existing title:
- SUB PLAY: a "You/Your" blunt truth or command, OR a quoted question a viewer would ask (keep the quotes).
- SPECIFIC-VIEWER PAIN: "Watch this if you're [struggle]" or "You're [struggling with X]".
- REACH (at most one): a contrarian bold claim OR the single most surprising real number in the transcript. Never a vague tease.
{ex}
{_HARD_RULES}

OUTPUT:
TITLE 2: <title>
TITLE 3: <title>"""


# ----------------------------------------------------------------- key-free local titler
_FILLER = {"so", "now", "okay", "yeah", "right", "well", "and", "but", "the", "a"}


def local_title(transcript: str, max_len: int = 70) -> str:
    """Deterministic fallback when no LLM key is set: pick the strongest line from the transcript.

    Preference order, all subs-first:
      1. A clean quoted-style question a viewer would also ask  -> keep it as a "quoted question".
      2. A blunt "You/Your ..." sentence.
      3. The first substantive sentence (numbers preferred), trimmed to length.
    """
    text = re.sub(r"\s+", " ", (transcript or "")).strip()
    if not text:
        return "Untitled clip"
    sents = [s.strip() for s in re.split(r"(?<=[.?!])\s+", text) if s.strip()]

    def short(s):
        s = s.strip(" .,-")
        return s if len(s) <= max_len else s[:max_len - 1].rstrip() + "…"

    # 1. question a viewer would ask (short, starts like a question)
    for s in sents:
        if s.endswith("?") and 12 <= len(s) <= max_len and re.match(
                r"(?i)^(how|what|should|why|can|do|is|when|where|i )\b", s):
            return f'"{short(s)}"'
    # 2. "You/Your" declarative
    for s in sents:
        if re.match(r"(?i)^(you|your|you're|you’re)\b", s) and 10 <= len(s):
            return short(s)
    # 3. first substantive sentence, numbers preferred
    numbered = [s for s in sents if re.search(r"[\$£€]|\b\d", s)]
    for s in (numbered or sents):
        words = s.split()
        if len(words) >= 4 and words[0].lower() not in _FILLER:
            return short(s)
    return short(sents[0])
