# Your brand assets — drop them here

This is your staging folder. Put your brand pieces in the subfolders below, then let Claude
Code wire them into the pipeline (it knows where each one goes).

| Folder | What to drop in |
|---|---|
| `logos/` | your logo (transparent PNG) — for end-cards / overlays |
| `fonts/` | your own font files (or use the big free library that already ships) |
| `music/` | your royalty-free tracks |
| `caption-style/` | a screenshot/clip of the caption look you want (color, emphasis, animation, position) |
| `animations/` | intro / outro / transition style references (optional) |

## Then wire it up — paste this into Claude Code:
```
I've put my brand assets in the brand/ folder:
- logo in brand/logos/, my font in brand/fonts/, music in brand/music/
- the caption look I want is shown in brand/caption-style/
Wire all of it into the Vibe Editing pipeline — set the caption font + colors to match,
use my logo on the end-card, point music at brand/music/ — then show me what you changed
and make one test clip so I can see it.
```

That's it — Claude reads your assets and sets the config. Tweak by telling it what to change,
then re-run. This is the same way our team sets up a new brand (font + caption animation + logo).
