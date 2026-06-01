## Copyright (c) 2026 GrandBIRDLizard
## BSD 3-.Clause All right's reserved

# PYthonic PALLET FUNCTION INDEX.txt

=============================

Pythonic Pallet Generator  / palettegen.py
Function index + call flow + responsibility map

Purpose
-------
This document is the "what exists / what calls what / what each function is for"
reference for the current palettegen.py module.

This is meant for:
- maintenance
- refactor planning
- C-port planning
- embedding / sidecar architecture prep
- fast orientation after time away from the project

This is a source-structure map.

============================================================
0) HIGH-LEVEL ROLE OF  `palett_gen.py`
============================================================

`palette_gen.p`y is the PALETTE AUTHORITY.

It owns:
- image color extraction
- color dedupe
- structural dark/light selection
- accent selection
- semantic Base16 slot synthesis
- output serialization to:
  - Base16  INI text
  - GTK3 CSS palette layer
  - GTK2 colors.rc include
- optional CLI printing / file output

It should remain:
- mostly pure logic
- importable as a module
- script-capable via main()

`theme_build.py` should remain:
- assembler / scaffold / filesystem orchestration layer

In C-minded terms:
- `palette_gen.py` = library module
- `main() = thin CLI` wrapper
- `theme_build.py` = consumer / build orchestrator

============================================================
1) TYPE ALIAS / MODULE CONSTANT ROLE
============================================================

RGB = Tuple[int, int, int]

Role:
- semantic alias for an RGB color tuple

Meaning:
- every color helper should treat RGB as:
  - 3 ints
  - each in [0,255]

No runtime behavior.
Pure readability + type-hinting.

============================================================
2) BASIC COLOR HELPERS
============================================================

------------------------------------------------------------
2.1) clamp(v, lo, hi) -> float
------------------------------------------------------------

Role:
- scalar bounds enforcement helper

Inputs:
- v: float
- lo: float
- hi: float

Returns:
- float in [lo, hi]

Used by:
- `blend()`
- `shift_value()`
- `shift_saturation()`

Type:
- pure helper
- no I/O
- deterministic

Notes:
- tiny but foundational
- safe to keep static/private if porting to C

------------------------------------------------------------
2.2) `rgb_to_hex(rgb: RGB) -> str`
------------------------------------------------------------

Role:
- `RGB -> lowercase 6-char hex serializer`

Inputs:
- rgb: (R,G,B)

Returns:
- "rrggbb"

Used by:
- `base16_text()`
- `css_palettd_text()`
- `gtk2_text()`
- `print_debug_table() indirectly for display`

Type:
- pure helper
- serializer support

Notes:
- no leading '#'
- output layers add '#' when needed

------------------------------------------------------------
2.3) `hex_to_rgb(hex_str: str) -> RGB`
------------------------------------------------------------

Role:
- parse hex string to RGB tuple

Inputs:
- "rrggbb" or "#rrggbb"

Returns:
- (R,G,B)

Raises:
- ValueError if not exactly 6 hex digits after stripping '#'

Used by:
- utility / future-proofing
- not central to current main pipeline

Type:
- pure helper
- parser

Notes:
- good to keep even if currently underused
- useful later for config ingestion / overrides

------------------------------------------------------------
2.4) rel_luminance(rgb: RGB) -> float
------------------------------------------------------------

Role:
- perceptual-ish structural brightness metric
- WCAG relative luminance basis

Inputs:
- RGB

Returns:
- float in [0,1]

Used by:
- pick_dark_candidates()
- pick_light_candidates()
- pick_accent_candidates()
- dark_surface_score()
- synthesize_dark_ramp() ordering
- synthesize_light_ramp() ordering
- print_debug_table()

Type:
- pure helper
- critical scoring primitive

Importance:
- HIGH

Notes:
- one of the most important functions in the module
- if we port to C, preserve exact math for determinism

------------------------------------------------------------
2.5) hsv(rgb: RGB) -> Tuple[float, float, float]
------------------------------------------------------------

Role:
- RGB -> HSV conversion wrapper

Inputs:
- RGB

Returns:
- (h, s, v), all normalized to [0,1]

Used by:
- saturation()
- hue()
- brightness()
- shift_value()
- shift_saturation()

Type:
- pure helper
- conversion wrapper

Notes:
- central adapter around colorsys
- if porting to C, you’ll need your own RGB->HSV implementation

------------------------------------------------------------
2.6) saturation(rgb: RGB) -> float
------------------------------------------------------------

Role:
- convenience accessor for HSV saturation

Used by:
- pick_light_candidates() tie-break
- pick_accent_candidates()
- dark_surface_score()
- choose_primary_accent()
- synthesize_dark_ramp() neutral safety logic
- print_debug_table()

Type:
- pure helper
- semantic accessor

------------------------------------------------------------
2.7) hue(rgb: RGB) -> float
------------------------------------------------------------

Role:
- convenience accessor for HSV hue

Used by:
- unique_by_hue()
- hue family classification for accents
- print_debug_table()

Type:
- pure helper
- semantic accessor

------------------------------------------------------------
2.8) brightness(rgb: RGB) -> float
------------------------------------------------------------

Role:
- convenience accessor for HSV value channel

Used by:
- pick_accent_candidates() ranking

Type:
- pure helper
- semantic accessor

Notes:
- this is HSV V, not WCAG luminance

------------------------------------------------------------
2.9) color_distance(a: RGB, b: RGB) -> float
------------------------------------------------------------

Role:
- RGB-space similarity heuristic

Inputs:
- two RGB tuples

Returns:
- Euclidean RGB distance

Used by:
- collapse_similar_colors()

Type:
- pure helper
- dedupe metric

Importance:
- MEDIUM-HIGH

Notes:
- not perceptually perfect
- excellent v0.x tradeoff

------------------------------------------------------------
2.10) blend(a: RGB, b: RGB, t: float) -> RGB
------------------------------------------------------------

Role:
- linear RGB interpolation

Inputs:
- a: RGB
- b: RGB
- t: float

Returns:
- interpolated RGB

Used by:
- lighten()
- darken()
- neutral base02 repair in synthesize_dark_ramp()

Type:
- pure helper
- color transform primitive

Importance:
- HIGH

------------------------------------------------------------
2.11) lighten(rgb: RGB, amount: float) -> RGB
------------------------------------------------------------

Role:
- move color toward white by amount

Used by:
- synthesize_dark_ramp() fallback
- synthesize_light_ramp() fallback

Type:
- pure helper
- transform wrapper

------------------------------------------------------------
2.12) darken(rgb: RGB, amount: float) -> RGB
------------------------------------------------------------

Role:
- move color toward black by amount

Used by:
- synthesize_dark_ramp() fallback
- synthesize_light_ramp() fallback
- accent-derived dark seed

Type:
- pure helper
- transform wrapper

------------------------------------------------------------
2.13) shift_value(rgb: RGB, delta: float) -> RGB
------------------------------------------------------------

Role:
- modify HSV V channel

Used by:
- utility / future tuning
- not central in current primary pipeline

Type:
- pure helper
- HSV transform

Notes:
- keep it
- likely useful later for contrast repair or semantic tuning

------------------------------------------------------------
2.14) shift_saturation(rgb: RGB, factor: float) -> RGB
------------------------------------------------------------

Role:
- modify HSV saturation channel

Used by:
- synthesize_dark_ramp() fallback neutralization
- accent-derived dark seed control
- neutral surface discipline

Type:
- pure helper
- HSV transform

Importance:
- HIGH

Notes:
- one of the most important “make it usable” helpers

============================================================
3) EXTRACTION STAGE
============================================================

------------------------------------------------------------
3.1) extract_quantized_colors(
        img_path,
        quantize_colors=32,
        resize_to=192
     ) -> List[Tuple[int, RGB]]
------------------------------------------------------------

Role:
- dominant color extraction from source image

Inputs:
- img_path: str | Path
- quantize_colors: int
- resize_to: int

Returns:
- list of (count, rgb)
- sorted descending by count

Internal work:
- open image
- convert to RGB
- thumbnail resize with aspect preserved
- adaptive quantization
- convert back to RGB
- count palette pixels
- sort by frequency

Used by:
- generate_base16_palette()

Type:
- stage function
- image I/O
- deterministic for same Pillow/runtime behavior

Importance:
- VERY HIGH

Side effects:
- reads image from disk

Notes:
- first true pipeline stage
- if porting to C later, this is one of the harder replacements
- may remain Python-side longest if we do embedded or sidecar first

------------------------------------------------------------
3.2) collapse_similar_colors(
        counted_colors,
        min_distance=24.0,
        max_colors=24
     ) -> List[Tuple[int, RGB]]
------------------------------------------------------------

Role:
- near-duplicate suppression after quantization

Inputs:
- counted_colors: list of (count, rgb), already frequency ordered
- min_distance: float
- max_colors: int

Returns:
- filtered list of (count, rgb)

Algorithm class:
- greedy frequency-preserving dedupe

Used by:
- generate_base16_palette()

Type:
- stage function
- pure
- selection filter

Importance:
- HIGH

Notes:
- this is the “stop the palette from being 5 versions of same purple” stage

============================================================
4) SELECTION HELPERS
============================================================

------------------------------------------------------------
4.1) pick_dark_candidates(colors: List[RGB]) -> List[RGB]
------------------------------------------------------------

Role:
- filter plausible dark structural colors

Inputs:
- list of RGB

Returns:
- list of RGB where luminance <= dark threshold

Used by:
- generate_base16_palette()

Type:
- selection helper
- pure

Importance:
- HIGH

------------------------------------------------------------
4.2) pick_light_candidates(colors: List[RGB]) -> List[RGB]
------------------------------------------------------------

Role:
- filter plausible light/foreground colors

Inputs:
- list of RGB

Returns:
- sorted list of RGB where luminance >= light threshold

Sorting:
- by (rel_luminance, saturation), ascending

Used by:
- generate_base16_palette()

Type:
- selection helper
- pure

Importance:
- HIGH

------------------------------------------------------------
4.3) pick_accent_candidates(colors: List[RGB]) -> List[RGB]
------------------------------------------------------------

Role:
- filter usable accent colors

Inputs:
- list of RGB

Returns:
- sorted accent candidate list

Filter logic:
- minimum saturation
- exclude too-dark and too-bright extremes

Sorting:
- by (saturation, brightness), descending

Used by:
- generate_base16_palette()

Type:
- selection helper
- pure

Importance:
- VERY HIGH

Notes:
- this stage largely decides whether the theme feels “alive” or dead

------------------------------------------------------------
4.4) dark_surface_score(rgb: RGB, surface_style: str) -> float
------------------------------------------------------------

Role:
- score dark candidates for structural usability

Inputs:
- rgb
- surface_style: "neutral" | "tinted"

Returns:
- float score
- lower is better

Used by:
- ordered_dark_candidates()

Type:
- scoring heuristic
- pure

Importance:
- VERY HIGH

Notes:
- this is one of the key quality heuristics in the whole generator

------------------------------------------------------------
4.5) ordered_dark_candidates(
        darks: List[RGB],
        surface_style: str
     ) -> List[RGB]
------------------------------------------------------------

Role:
- sort dark candidates by best structural fit

Inputs:
- dark candidate list
- surface_style

Returns:
- sorted dark list

Used by:
- synthesize_dark_ramp()

Type:
- selection helper
- pure

Importance:
- HIGH

------------------------------------------------------------
4.6) unique_by_hue(colors: List[RGB]) -> List[RGB]
------------------------------------------------------------

Role:
- remove near-redundant accent hues

Inputs:
- ranked accent colors

Returns:
- hue-diversified accent list

Used by:
- synthesize_accent_slots()

Type:
- selection helper
- pure

Importance:
- HIGH

Notes:
- critical for semantic accent slots not collapsing into one hue family

------------------------------------------------------------
4.7) choose_primary_accent(accents: List[RGB]) -> RGB
------------------------------------------------------------

Role:
- choose the single “main” accent anchor

Inputs:
- accent candidate list

Returns:
- one RGB accent

Used by:
- generate_base16_palette()
- synthesize_dark_ramp() fallback path
- synthesize_accent_slots()

Type:
- scoring heuristic
- pure

Importance:
- VERY HIGH

Notes:
- this is the “if I had to keep one accent, which one?” function

============================================================
5) PALETTE SYNTHESIS STAGE
============================================================

------------------------------------------------------------
5.1) synthesize_dark_ramp(
        darks: List[RGB],
        accent: RGB,
        surface_style: str
     ) -> List[RGB]
------------------------------------------------------------

Role:
- build base00..base03

Inputs:
- dark candidates
- primary accent
- surface_style

Returns:
- [base00, base01, base02, base03]

Behavior:
- prefers 4 best darks if available
- orders final ramp by luminance
- repairs oversaturated base02 in neutral mode
- falls back to accent-derived seed if insufficient darks
- neutral mode further desaturates fallback surfaces

Used by:
- generate_base16_palette()

Type:
- synthesis stage
- pure

Importance:
- CRITICAL

Notes:
- probably the single most important theme-structure function

------------------------------------------------------------
5.2) synthesize_light_ramp(
        lights: List[RGB],
        dark_ramp: List[RGB]
     ) -> List[RGB]
------------------------------------------------------------

Role:
- build base04..base07

Inputs:
- light candidates
- completed dark ramp

Returns:
- [base04, base05, base06, base07]

Behavior:
- use real image-derived lights if enough exist
- otherwise synthesize from brightest light or dark fallback

Used by:
- generate_base16_palette()

Type:
- synthesis stage
- pure

Importance:
- CRITICAL

Notes:
- this controls readability / text feel more than people realize

------------------------------------------------------------
5.3) synthesize_accent_slots(
        accent_pool: List[RGB],
        primary_accent: RGB
     ) -> Dict[str, RGB]
------------------------------------------------------------

Role:
- build base08..base0F semantic accent map

Inputs:
- accent_pool
- primary_accent

Returns:
- dict:
  - base08
  - base09
  - base0A
  - base0B
  - base0C
  - base0D
  - base0E
  - base0F

Behavior:
- hue-diversify
- bucket by semantic families
- use image-derived families when possible
- fallback to built-in defaults when missing
- preserve primary-accent influence for high-value slots

Used by:
- generate_base16_palette()

Type:
- synthesis stage
- pure

Importance:
- CRITICAL

Notes:
- this is where it become a usable semantic theme map

============================================================
6) PRIMARY PUBLIC PIPELINE ENTRYPOINT
============================================================

------------------------------------------------------------
6.1) generate_base16_palette(
        img_path,
        quantize_colors=32,
        resize_to=192,
        dedupe_distance=24.0,
        surface_style="neutral"
     ) -> Dict[str, RGB]
------------------------------------------------------------

Role:
- master pipeline function
- canonical public API for palette generation

Inputs:
- img_path: source image path
- quantize_colors
- resize_to
- dedupe_distance
- surface_style

Returns:
- palette dict with keys:
  - base00 .. base0F

Pipeline order:
1. extract_quantized_colors()
2. collapse_similar_colors()
3. derive colors list
4. pick_dark_candidates()
5. pick_light_candidates()
6. pick_accent_candidates()
7. choose_primary_accent()
8. synthesize_dark_ramp()
9. synthesize_light_ramp()
10. synthesize_accent_slots()
11. assemble final dict

Used by:
- CLI main()
- theme_build.py (module import)

Type:
- public API
- orchestration function
- pure except for image read inside extraction path

Importance:
- HIGHEST

Notes:
- if another module imports only one function, this should be the one

============================================================
7) OUTPUT SERIALIZERS (MODULE-FRIENDLY)
============================================================

These are the functions that turned palette_gen.py from:
- script-first

into:
- module-first + script wrapper

This is the exact architectural shift you wanted.

------------------------------------------------------------
7.1) base16_text(
        palette: Dict[str, RGB],
        scheme_name="Generated-Palette",
        author="palette_gen.py"
     ) -> str
------------------------------------------------------------

Role:
- serialize palette into Base16-ish INI text

Inputs:
- palette dict
- scheme_name
- author

Returns:
- string text blob

Output style:
- [dark]
- [colors]
- scheme metadata
- base00..base0F = rrggbb

Used by:
- CLI main()
- theme_build.py

Type:
- serializer
- pure

Importance:
- HIGH (for integration)

Notes:
- no disk writes
- exactly what a reusable module should do

------------------------------------------------------------
7.2) css_palette_text(palette: Dict[str, RGB]) -> str
------------------------------------------------------------

Role:
- serialize palette into GTK3/GTK3.20+ CSS palette layer

Inputs:
- palette dict

Returns:
- string text blob for:
  - gtk-3.0/widgets/00-palette.css

Output includes:
- raw @define-color base00..base0F
- semantic aliases:
  - accent_color
  - warning_color
  - success_color
  - window_bg_color
  - theme_fg_color
  - etc.

Used by:
- CLI main()
- theme_build.py

Type:
- serializer
- pure

Importance:
- VERY HIGH for GTK integration

Notes:
- this is the bridge between abstract palette and actual GTK consumption

------------------------------------------------------------
7.3) gtk2_text(palette: Dict[str, RGB]) -> str
------------------------------------------------------------

Role:
- serialize palette into GTK2-compatible colors.rc include

Inputs:
- palette dict

Returns:
- string text blob for:
  - gtk-2.0/colors.rc

Output includes:
- color["baseXX"] assignments
- gtk-color-scheme block

Used by:
- CLI main()
- theme_build.py

Type:
- serializer
- pure

Importance:
- MEDIUM-HIGH (legacy support, still useful)

Notes:
- intentionally simple
- keeps old GTK2 consumers alive without overengineering

============================================================
8) DEBUG / FILE HELPERS
============================================================

------------------------------------------------------------
8.1) print_debug_table(palette: Dict[str, RGB]) -> None
------------------------------------------------------------

Role:
- print palette metrics for inspection

Inputs:
- palette dict

Outputs to stdout:
- baseXX
- hex
- luminance
- saturation
- hue

Used by:
- CLI main() when --debug

Type:
- debug utility
- side-effecting (stdout)

Importance:
- HIGH for tuning / development
- not core runtime logic

Notes:
- extremely useful for learning and for later C parity tests

------------------------------------------------------------
8.2) write_text_file(path, text) -> None
------------------------------------------------------------

Role:
- safe-ish file write helper for CLI output paths

Inputs:
- path
- text

Behavior:
- creates parent dirs if needed
- appends newline if missing
- writes UTF-8 text

Used by:
- CLI main()

Type:
- I/O helper
- side-effecting (filesystem)

Importance:
- LOW-MEDIUM

Notes:
- not part of palette math
- purely convenience glue

============================================================
9) CLI LAYER
============================================================

------------------------------------------------------------
9.1) parse_args() -> argparse.Namespace
------------------------------------------------------------

Role:
- CLI argument schema definition

Inputs:
- command line

Returns:
- parsed namespace

Defines:
- image
- name / author
- quantize
- resize
- dedupe-distance
- surface-style
- format
- output
- base16-output
- css-output
- gtk2-output
- debug

Used by:
- main()

Type:
- CLI glue
- side-effecting via argparse parse/exit behavior

Importance:
- LOW for library use
- HIGH for script usability

------------------------------------------------------------
9.2) main() -> int
------------------------------------------------------------

Role:
- CLI wrapper around module pipeline + serializers

Behavior:
1. parse args
2. call generate_base16_palette()
3. serialize:
   - base16_out
   - css_out
   - gtk2_out
4. choose output mode:
   - print or write files
5. optional debug print
6. return 0

Used by:
- __main__ guard only

Type:
- CLI entrypoint
- orchestrator

Importance:
- HIGH for standalone script
- should remain THIN

Notes:
- this is exactly how you want Python structured:
  - reusable functions first
  - main() only glues CLI behavior

============================================================
10) __main__ GUARD
============================================================

if __name__ == "__main__":
    raise SystemExit(main())

Role:
- script execution entrypoint
- keeps import side clean

Meaning:
- importing palette_gen does NOT run CLI behavior
- executing palette_gen.py directly DOES run CLI behavior

Importance:
- CRITICAL for module hygiene

============================================================
11) PUBLIC API VS INTERNAL API
============================================================

Best mental split for future work:

PUBLIC / STABLE (safe to import from other modules)
---------------------------------------------------
- generate_base16_palette()
- base16_text()
- css_palette_text()
- gtk2_text()

OPTIONALLY PUBLIC / DEV-USEFUL
-----------------------------
- rel_luminance()
- saturation()
- hue()
- brightness()
- print_debug_table()

INTERNAL / IMPLEMENTATION DETAIL
--------------------------------
- clamp()
- rgb_to_hex()
- hex_to_rgb()
- hsv()
- color_distance()
- blend()
- lighten()
- darken()
- shift_value()
- shift_saturation()
- extract_quantized_colors()
- collapse_similar_colors()
- pick_dark_candidates()
- pick_light_candidates()
- pick_accent_candidates()
- dark_surface_score()
- ordered_dark_candidates()
- unique_by_hue()
- choose_primary_accent()
- synthesize_dark_ramp()
- synthesize_light_ramp()
- synthesize_accent_slots()
- write_text_file()
- parse_args()
- main()

Recommendation:
- treat only the 4 serializer/generator functions as stable external API
- everything else is fair game to refactor

============================================================
12) RECOMMENDED C-MINDED MODULE GROUPING (MENTAL MODEL)
============================================================

If you were conceptually splitting this like .c/.h responsibility groups:

1. color_math
   - clamp
   - rgb_to_hex
   - hex_to_rgb
   - rel_luminance
   - hsv
   - saturation
   - hue
   - brightness
   - color_distance
   - blend
   - lighten
   - darken
   - shift_value
   - shift_saturation

2. extract
   - extract_quantized_colors
   - collapse_similar_colors

3. select
   - pick_dark_candidates
   - pick_light_candidates
   - pick_accent_candidates
   - dark_surface_score
   - ordered_dark_candidates
   - unique_by_hue
   - choose_primary_accent

4. synth
   - synthesize_dark_ramp
   - synthesize_light_ramp
   - synthesize_accent_slots
   - generate_base16_palette

5. serialize
   - base16_text
   - css_palette_text
   - gtk2_text

6. cli
   - print_debug_table
   - write_text_file
   - parse_args
   - main

This is probably how you should think about it before any serious C-port.

============================================================
13) CURRENT CALL FLOW (ACTUAL PRACTICAL FLOW)
============================================================

Standalone CLI flow:
--------------------

main()
  -> parse_args()
  -> generate_base16_palette()
       -> extract_quantized_colors()
       -> collapse_similar_colors()
       -> pick_dark_candidates()
       -> pick_light_candidates()
       -> pick_accent_candidates()
       -> choose_primary_accent()
       -> synthesize_dark_ramp()
            -> ordered_dark_candidates()
                 -> dark_surface_score()
            -> blend() / lighten() / darken() / shift_saturation() as needed
       -> synthesize_light_ramp()
            -> lighten() / darken() as needed
       -> synthesize_accent_slots()
            -> unique_by_hue()
            -> hue() / saturation() / brightness() and family logic
  -> base16_text()
       -> rgb_to_hex()
  -> css_palette_text()
       -> rgb_to_hex()
  -> gtk2_text()
       -> rgb_to_hex()
  -> optional print_debug_table()
       -> rgb_to_hex()
       -> rel_luminance()
       -> saturation()
       -> hue()

Imported module flow (theme_build.py):
-------------------------------------

theme_build.py
  -> from palette_gen import ...
  -> generate_base16_palette()
  -> base16_text()
  -> css_palette_text()
  -> gtk2_text()

This is the architecture you want.

============================================================
14) MOST IMPORTANT FUNCTIONS TO PROTECT DURING REFACTOR
============================================================

If you touch nothing else, preserve behavior of these first:

Tier 1 (do not casually break)
------------------------------
- generate_base16_palette()
- synthesize_dark_ramp()
- synthesize_light_ramp()
- synthesize_accent_slots()
- choose_primary_accent()
- dark_surface_score()
- rel_luminance()
- shift_saturation()

Tier 2 (important but easier to change)
---------------------------------------
- extract_quantized_colors()
- collapse_similar_colors()
- pick_accent_candidates()
- unique_by_hue()
- css_palette_text()

Tier 3 (easy to change / mostly glue)
-------------------------------------
- write_text_file()
- parse_args()
- main()
- print_debug_table()

============================================================
15) BEST NEXT REFACTOR RULES
============================================================

If you keep evolving this file, follow these rules:

1. Do NOT let serializer functions print directly
- always return strings

2. Do NOT let generate_base16_palette write files
- keep it pure-ish and reusable

3. Keep main() thin
- parse args
- call public API
- serialize
- print/write

4. Keep theme_build.py ignorant of palette internals
- it should only know:
  - generate_base16_palette
  - base16_text
  - css_palette_text
  - gtk2_text

5. If adding more outputs:
- add new serializer function
- do NOT jam filesystem logic into palette math

This is the exact right Python architecture for C/embedded path later if we wanna try stuff.

============================================================
16) ONE-LINE ROLE SUMMARY PER FUNCTION
============================================================

clamp
- bound a scalar to a valid numeric range

rgb_to_hex
- RGB tuple to hex string

hex_to_rgb
- hex string to RGB tuple

rel_luminance
- WCAG-style structural brightness metric

hsv
- RGB to HSV conversion wrapper

saturation
- HSV saturation accessor

hue
- HSV hue accessor

brightness
- HSV value accessor

color_distance
- RGB Euclidean distance for dedupe

blend
- linear RGB interpolation

lighten
- blend toward white

darken
- blend toward black

shift_value
- adjust HSV value channel

shift_saturation
- scale HSV saturation channel

extract_quantized_colors
- image -> dominant quantized color counts

collapse_similar_colors
- frequency-preserving near-duplicate filter

pick_dark_candidates
- select plausible dark structural colors

pick_light_candidates
- select plausible light/foreground colors

pick_accent_candidates
- select vivid usable accents

dark_surface_score
- rank dark colors for UI structural use

ordered_dark_candidates
- sort darks by structural suitability

unique_by_hue
- remove redundant accent hues

choose_primary_accent
- pick best single accent anchor

synthesize_dark_ramp
- create base00..base03

synthesize_light_ramp
- create base04..base07

synthesize_accent_slots
- create base08..base0F semantic accents

generate_base16_palette
- orchestrate full palette generation pipeline

base16_text
- serialize palette as Base16-ish INI text

css_palette_text
- serialize palette as GTK3 CSS color layer

gtk2_text
- serialize palette as GTK2 colors.rc include

print_debug_table
- print palette metrics for inspection

write_text_file
- write text to disk with newline/parent creation

parse_args
- define CLI arguments

main
- thin CLI wrapper around module API

============================================================
17) FINAL PROJECT RULE
============================================================

palette_gen.py should continue to be:

- palette logic first
- reusable module first
- CLI second

Make:

- embedding easier
- sidecar easier
- testing easier
- C parity testing easier
- later rewrite easier
- future split into multiple Python modules easier

============================================================
END written by GrandBIRDLizard 
============================================================
