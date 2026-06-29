# Speaker Q&A Visual Guide (extracted from PDF)

Source: `presets/qa-visual-guide.pdf`. Keep this in sync if the source updates.

## Camera Angles

### Split-screen (50/50)
- Speaker on **top**, Guest on **bottom**
- Same proportions (both 1080×960 when output is 1080×1920)
- **Add drop shadow to Speaker's angle** — visual signal that distinguishes the two halves

### Guest Main Angle
- Guest full-screen vertical (1080×1920)
- Used when guest is speaking and their reaction matters

### Speaker Main Angle
- Speaker full-screen vertical
- Used when Speaker is delivering the payoff or a key diagnostic

### Guest Wide Angle
- Room/stage wide showing guest from further back
- Transition shot or reaction beat

### Speaker Wide Angle
- Room/stage wide showing Speaker
- Transition shot or audience POV

## Colorgrade

**Preset files missing** — visual guide shows before/after but no LUT/preset file ships.

- **Guest:** cool, blue tones
- **Speaker:** bright, saturated

Fallback until LUTs are built: ffmpeg `eq=contrast=1.08:saturation=1.08:gamma=0.97` (from `shortform`). Apply different saturation/hue per speaker if manually tuning.

## Subtitle settings

### Guest Q&A Subtitles
- **Font:** Montserrat
- **Default style:** `Medium Italic`
- **Highlight style:** `Black Italic`
- **Font size:** 80
- **Text box width:** 150 (avoids UI cutoff)
- **Color:** `#FED90F` or `#FECB00` (yellow)
- **Alignment zone:** center-middle (Premiere zone indicator)

### Speaker Q&A Subtitles
- **Font:** Montserrat
- **Default style:** `Medium` (no italic)
- **Highlight style:** `Black` (no italic)
- **Font size:** 80
- **Text box width:** 150
- **Color:** `#FFFFFF` (white)

### General subtitle notes

- **Lowercase** everything except proper nouns and `I`, `I'm`, `I'd`, `I've`, `I'll`
- **Single-line default** (rare multi-line exceptions, and parenthetical explainers underneath)
- **Money: `$` prefix always** — `$1`, `$2.5K`, `$600K`, `$3M`
- **Symbols, not words** — use `$` not "dollars", `%` not "percentages"
- **Money abbreviations:**
  - Below $100,000: either form fine — `$1`, `$190`, `$1,600` or `$1.6K`; `$10,000` or `$10K`; `$75,000` or `$75K`
  - Above $100,000: abbreviate — `$250K`, `$1.2M`, `$20M`, `$3B`
- **No dead gaps** between subtitle chunks
- **Spell-check** before shipping

All of this increases visual clarity, improves immediate understanding, and removes friction between what Speaker is saying and what the subtitles show.

## Title Card Visual Settings

- **Font:** SF Pro
- **Font weight:** `Black`
- **Text:** all caps
- **Text size:** 160px
- **Leading / line height:** `-40`
- **Tracking:** `-30`
- **Text color:**
  - Default: white `#FFFFFF`
  - One or two highlight words: yellow `#FECB00`
  - Tip: on white backgrounds, add a subtle black stroke to yellow words
  - Stroke on dark backgrounds: black, 2px, center alignment
- **Text background:**
  - Color: dark grey `#1A1A1A`
  - Opacity: 100%
  - Size: 60
  - Corner radius: 50

## Presets (Premiere Pro)

See `presets/` folder. XML-format Adobe Premiere Pro preset files — drop into Premiere directly:

- `shorts-font.prtextstyle` — Montserrat body style (for the solo Speaker shortform pipeline)
- `qa-title-hook-font.prtextstyle` — SF Pro Black title card
- `text-down-small-animation.prfpset` — default caption entry animation
- `qa-title-hook-animation.prfpset` — title card entry (drop shadow + position)
