# Pythonic Palette Generator
Copyright (c) 2026, GrandBIRDLizard.
BSD 3-Clause, All rights reserved.

A minimal, modular Python toolkit for generating cohesive GTK theme palettes from wallpaper images. Extract dominant colors, synthesize semantic slots, and emit theme artifacts, all in pure Python. Suitable for integration into larger workflows.

**Licensed under BSD 3-Clause.** See [LICENCE](./LICENCE) for details.


![Logo](/static/PPGv1.png)

---

## Quick Start

### Install Dependencies

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install pillow

# Test palette extraction (prints to stdout)
python3 palette_gen.py /path/to/wallpaper.png --debug

# Build a complete GTK theme
python3 theme_build.py /path/to/wallpaper.png
```

---

Core Philosophy: Simplicity Enables Integration

This project is intentionally small and dependency-minimal because:

    No Subprocesses: theme_build.py imports palette_gen.py using the same Python interpreter, same process. Functions return dicts and strings, not subprocess output to parse.

    Pure Color Math: All palette generation uses standard library (colorsys, math) plus Pillow for image processing. No exotic color science libraries.

    Modular Functions: Every palette operation—extraction, deduplication, accent selection, ramp synthesis, are standalone, testable function with clear inputs and outputs.

    Multiple Output Formats: The same palette engine emits Base16 INI, GTK3 CSS, and GTK2 RC files. Swap serializers without regenerating.

    Library-Friendly: Want to use palette extraction in a larger tool? Import generate_base16_palette() or individual helpers like extract_quantized_colors(), collapse_similar_colors(), and choose_primary_accent().


## Architecture

 *Two-Module Design*

| Module | Role |
| :--- | :--- |
| `palette_gen.py` | **Palette engine**: Extracts colors from images, synthesizes semantic slots (Base16-style), emits multiple formats. Pure functions. |
| `theme_build.py` | **Theme assembler**: Imports palette_gen as a module, scaffolds GTK2/GTK3 tree, writes consumer files and widget stubs. |

**Clean Separation:**
- palette_gen.py = palette authority (does one thing well)
- theme_build.py = consumer orchestration (builds on palette_gen)
- Filesystem I/O = isolated in helpers; core logic is pure
- No circular imports or tight coupling

Feature Highlights
Palette Extraction

    Adaptive Image Quantization: Thumbnail + PIL adaptive palette for fast, high-quality color sampling (default: 32 colors from 192×192 resize)
    Smart Deduplication: Merge near-identical colors in RGB space (default: 24 RGB distance threshold)
    Wallpaper-Driven Generation: Extract dominant, saturated accent colors; build dark/light ramps from actual image colors

Semantic Slot Synthesis

Generate a Base16-compatible palette with semantic meaning:

    base00–base03: Dark structural colors (surfaces, backgrounds)
    base04–base07: Light structural colors (text, borders)
    base08–base0F: Semantic accents (red, orange, yellow, green, cyan, blue, purple, pink)

Surface Style Policies

    --surface-style neutral (default): Keeps dark surfaces desaturated for safe UI (recommended)
    --surface-style tinted: Allows more color personality in surfaces for stylized themes

Output Formats

All formats from one palette:

    Base16 INI (color.ini): Portable palette interchange format
    GTK3 CSS (00-palette.css): CSS custom properties + semantic color aliases
    GTK2 RC (colors.rc): Legacy GTK2 color includes

---

## Usage Patterns

### Pattern 1: Direct Palette Testing

>
Use this first a couple times so you get used to the output and behavior of the extraction and output process.
>

```python
python3 palette_gen.py /path/to/wallpaper.png \
  --surface-style neutral \
  --debug
```

>
Output: Base16 palette with debug table (luminance, saturation, hue per slot).
>

### Pattern 2: Build a Complete Theme

```python
python3 theme_build.py /path/to/wallpaper.png \
  --surface-style neutral
```

Creates:

```
~/.local/share/themes/Dorakura-Kyoto/
├── index.theme                          # Metadata
├── color.ini                            # Base16 snapshot
├── gtk-2.0/
│   ├── gtkrc                           # GTK2 entry
│   └── colors.rc                       # Generated colors
└── gtk-3.0/
    ├── gtk.css                         # GTK3 entry
    ├── gtk-dark.css                    # Dark variant
    └── widgets/
        ├── 00-palette.css              # Generated palette
        ├── 20-buttons.css              # Widget stubs (not overwritten)
        ├── 30-entries.css
        └── [... 6 more widget modules ...]
```
---

**Widget stubs are created only if not present .your edits are safe.**

### Pattern 3: Refresh Palette Only


```python
python3 theme_build.py /path/to/new-wallpaper.png \
  --theme-root ~/.local/share/themes/Dorakura-Kyoto \
  --surface-style neutral
```

>
Regenerates color.ini, gtk-2.0/colors.rc, and gtk-3.0/widgets/00-palette.css without touching widget code.
>


---


### Pattern 4: Library integration

```python
from palette_gen import (
    extract_quantized_colors,
    collapse_similar_colors,
    generate_base16_palette,
    css_palette_text,
)

# Your tool
palette = generate_base16_palette(
    img_path="wallpaper.png",
    quantize_colors=32,
    resize_to=192,
    dedupe_distance=24.0,
    surface_style="neutral",
)

# Emit CSS
css = css_palette_text(palette)
with open("theme.css", "w") as f:
    f.write(css)
```
---

## command referance

**palette_gen.py**

### Usage: palette_gen.py IMAGE [OPTIONS]
```
Options:
  -n, --name TEXT              Scheme name (default: Auto)
  -a, --author TEXT            Author string (default: palette_gen.py)
  -q, --quantize INT           Colors for initial quantization (default: 32)
  -r, --resize INT             Thumbnail max size (default: 192)
  --dedupe-distance FLOAT      Min RGB distance between kept colors (default: 24.0)
  --surface-style {neutral,tinted}  Dark surface policy (default: neutral)
  --format {base16,css,gtk2,all}  Output format (default: base16)
  --output PATH                Single output file (for single format)
  --base16-output PATH         Path for Base16 output
  --css-output PATH            Path for GTK3 CSS output
  --gtk2-output PATH           Path for GTK2 RC output
  --debug                      Print luminance/saturation/hue debug table
```

**theme_build.py**

### Usage: theme_build.py IMAGE [OPTIONS]
```
Options:
  --theme-root PATH             Target theme directory (default: ~/.local/share/themes/Dorakura-Kyoto)
  --theme-name TEXT             Display name for index.theme (default: Theme-Auto)
  --scheme-name TEXT            Palette scheme name (default: Theme-Auto)
  --author TEXT                 Palette author (default: theme_build.py)
  -q, --quantize INT            Quantization colors (default: 32)
  -r, --resize INT              Thumbnail max size (default: 192)
  --dedupe-distance FLOAT       Min RGB distance (default: 24.0)
  --surface-style {neutral,tinted}  Dark surface policy (default: neutral)
  --force-consumers             Overwrite index.theme / gtkrc / gtk.css / gtk-dark.css
  --force-widgets               Overwrite widget stubs (dangerous; use only if you know what you're doing)
```

---

## Why I believe this is maintainable.


No Hidden Dependencies:

    Only pillow for image I/O
    Core math uses Python stdlib (colorsys, math)
    Color helpers are transparent, not black-box formulas

Pure Functions:

    palette_gen.py has no global state
    Input → output; no side effects except for I/O helpers
    Easy to test, mock, and reason about

Single Responsibility:

    palette_gen.py: Extract + synthesize palettes
    theme_build.py: Orchestrate theme tree + call palette_gen
    Each module does one thing well

Direct Integration:

    Import functions, not binaries
    Dict/string outputs, not subprocess calls
    No version-lock on CLI output formats

Explicit Fallbacks:

    Missing image colors? Use sensible defaults
    Too few extracted colors? Fallback ramp synthesis
    Clear, documented fallback paths

Minimal I/O Assumptions:

    Doesn't assume theme location
    Doesn't require system packages (beyond Python + Pillow)
    Works in sandboxed/containerized environments
 

---

## Use Cases:

**For Theme Designers:**

Generate wallpaper-synchronized GTK themes with one command. Refresh instantly when you change your wallpaper.

**For System Tools:**

Embed palette generation into desktop environment installers, customization GUIs, or config managers. Import palette_gen directly. **No CLI overhead.**

**For Color Research:**

Extract dominant colors, analyze luminance/saturation/hue distributions, and study palettes algorithmically.


**For Other Theme Systems:**

Adapt the palette engine to KDE, GNOME Shell, icon themes, or custom UIs. The color math is toolkit-agnostic.

---

## Development & Contributintg

**Project Structure**
```
Pythonic-Palette-Generator/
├── palette_gen.py          # Core palette engine (~720 LOC)
├── theme_build.py          # Theme assembler (~550 LOC)
├── README.md               # This file
├── README-quickstart.txt   # Detailed CLI guide
├── LICENCE                 # BSD 3-Clause
└── Docs/                   # Future documentation
```


**Code Style:**

- Type hints for all public functions
- Docstrings for complex logic
- Liberal comments for color math rationale
- Clear variable names (no c1, c2 without context)
 
**Future Roadmap:**

- Unit tests for palette functions
- CLI progress feedback for large images
- Alternative color extraction methods (e.g., k-means)
- Wiki with theme tuning guides

---

## Licencse

### BSD 3clause. (see LICENCE)

You may use, modify, and redistribute this software freely, provided you retain the copyright notice and license terms.

---

## Examples:


**Example 1: Purple Monochrome Theme:**

```python3 palette_gen.py purple-sunset.jpg --surface-style neutral --debug```


**Output:**
```
base00  #1a0a2e  lum=0.015  sat=0.820  hue=0.805
base01  #2d1b4e  lum=0.035  sat=0.750  hue=0.805
base02  #4a2f7a  lum=0.065  sat=0.680  hue=0.800
base03  #6b4fa0  lum=0.100  sat=0.650  hue=0.800
...
base0E  #d85aff  lum=0.450  sat=0.850  hue=0.815  <- Primary accent (vibrant purple)
```

---

**Example 2: Custom Theme Location:**


```pyton
python3 theme_build.py landscape.png \
  --theme-root ~/.themes/MyTheme \
  --theme-name "My Custom Theme" \
  --surface-style tinted
```

---

**Example 3: Library Use in Another Project:**

```python
from pathlib import Path
import json
from palette_gen import generate_base16_palette, rgb_to_hex

# Generate palette
palette = generate_base16_palette("wallpaper.png", surface_style="neutral")

# Export as JSON for web/Electron apps
palette_json = {
    name: rgb_to_hex(rgb)
    for name, rgb in palette.items()
}

print(json.dumps(palette_json, indent=2))


**Output:**

{
  "base00": "1a1a2e",
  "base01": "2d2d44",
  "base0E": "b8b8ff",
  ...
}
```

---

# FAQ

Q: Can I use this with non-GTK themes?
A: Yes. The palette engine is toolkit-agnostic. Export to JSON, YAML, or your format.

Q: What if my wallpaper is mostly one color?
A: Fallback ramp synthesis creates usable dark/light gradients from that dominant color.

Q: Does this require system theme installation?
A: No. Generated files go to `~/.local/share/themes/` by default. No sudo needed.

Q: Can I modify generated widget CSS?
A: Yes. Widget stubs (buttons, entries, etc.) are created only if missing. Your edits are safe on re-run.

Q: How do I integrate this into a larger tool?
A: from palette_gen import generate_base16_palette and call functions directly. No CLI needed.
Support & Feedback

For issues, feature requests, or questions, open a GitHub issue


