# Caption fonts

The bundled default is **Montserrat** — SIL Open Font License, free to use and
redistribute. FFmpeg reads fonts here via `fontsdir=`; no system install needed.

## What ships
- `fonts/Montserrat-{Regular,SemiBold,ExtraBold}.ttf`
- `fonts/free_font/Montserrat-{Regular,Medium,SemiBold,Bold,ExtraBold,Black}.otf` (+ `MontserratBlack.otf`)

## Use your own font
1. Drop your `.ttf`/`.otf` into `fonts/` (and `fonts/free_font/` for the OTF weights).
2. Point the styles at them — edit the `family`/`file` fields in `scripts/spice_tabs.py`
   and any preset JSON under `presets/`.
3. **Filename ≠ family name.** Check the internal family with:
   `fc-query -f '%{family[0]} — %{style[0]}\n' fonts/free_font/Montserrat-Bold.otf`
4. You own your font license when you redistribute.

> The original used a commercial font; it was removed for licensing. Montserrat is a
> close, free substitute — swap in your brand font any time.
