"""Copyright (c) 2026, GrandBIRDLizard.
BSD 3-Clause, All rights reserved.

Redistribution and use in source and binary forms, with or without
modification, are permitted provided that the following conditions are met:

1. Redistributions of source code must retain the above copyright notice,
   this list of conditions and the following disclaimer.

2. Redistributions in binary form must reproduce the above copyright notice,
   this list of conditions and the following disclaimer in the documentation
   and/or other materials provided with the distribution.

3. Neither the name of Your Name nor the names of its contributors may be used
   to endorse or promote products derived from this software without specific
   prior written permission.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE
FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,
OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE."""

#!/usr/bin/env python3
from __future__ import annotations

import argparse
import colorsys
import math
from pathlib import Path
from typing import Dict, List, Tuple

from PIL import Image

RGB = Tuple[int, int, int]


# Basic color helpers

def clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


def rgb_to_hex(rgb: RGB) -> str:
    return f"{rgb[0]:02x}{rgb[1]:02x}{rgb[2]:02x}"


def hex_to_rgb(hex_str: str) -> RGB:
    hex_str = hex_str.strip().lstrip("#")
    if len(hex_str) != 6:
        raise ValueError(f"invalid hex color: {hex_str}")
    return tuple(int(hex_str[i:i+2], 16) for i in (0, 2, 4))  # type: ignore


def rel_luminance(rgb: RGB) -> float:
    """WCAG relative luminance."""
    def channel(c: int) -> float:
        x = c / 255.0
        return x / 12.92 if x <= 0.04045 else ((x + 0.055) / 1.055) ** 2.4

    r, g, b = (channel(c) for c in rgb)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def hsv(rgb: RGB) -> Tuple[float, float, float]:
    r, g, b = (c / 255.0 for c in rgb)
    return colorsys.rgb_to_hsv(r, g, b)  # hue [0..1], sat [0..1], val [0..1]


def saturation(rgb: RGB) -> float:
    return hsv(rgb)[1]


def hue(rgb: RGB) -> float:
    return hsv(rgb)[0]


def brightness(rgb: RGB) -> float:
    return hsv(rgb)[2]


def color_distance(a: RGB, b: RGB) -> float:
    """Euclidean distance in RGB space (good enough for this utility)."""
    return math.sqrt(
        (a[0] - b[0]) ** 2 +
        (a[1] - b[1]) ** 2 +
        (a[2] - b[2]) ** 2
    )


def blend(a: RGB, b: RGB, t: float) -> RGB:
    t = clamp(t, 0.0, 1.0)
    return (
        int(round(a[0] + (b[0] - a[0]) * t)),
        int(round(a[1] + (b[1] - a[1]) * t)),
        int(round(a[2] + (b[2] - a[2]) * t)),
    )


def lighten(rgb: RGB, amount: float) -> RGB:
    return blend(rgb, (255, 255, 255), amount)


def darken(rgb: RGB, amount: float) -> RGB:
    return blend(rgb, (0, 0, 0), amount)


def shift_value(rgb: RGB, delta: float) -> RGB:
    """Adjust HSV value channel."""
    h, s, v = hsv(rgb)
    v = clamp(v + delta, 0.0, 1.0)
    r, g, b = colorsys.hsv_to_rgb(h, s, v)
    return (int(r * 255), int(g * 255), int(b * 255))


def shift_saturation(rgb: RGB, factor: float) -> RGB:
    """Scale HSV saturation."""
    h, s, v = hsv(rgb)
    s = clamp(s * factor, 0.0, 1.0)
    r, g, b = colorsys.hsv_to_rgb(h, s, v)
    return (int(r * 255), int(g * 255), int(b * 255))


# Extraction

def extract_quantized_colors(
    img_path: str | Path,
    quantize_colors: int = 32,
    resize_to: int = 192,
) -> List[Tuple[int, RGB]]:
    """
    Extract clustered colors from an image using adaptive quantization.
    Returns list of (count, rgb), sorted by frequency desc.
    """
    img = Image.open(img_path).convert("RGB")

    # Keep aspect ratio, reduce workload
    img.thumbnail((resize_to, resize_to), Image.Resampling.LANCZOS)

    # Adaptive quantization -> much better than raw getcolors on full RGB
    quantized = img.convert("P", palette=Image.Palette.ADAPTIVE, colors=quantize_colors).convert("RGB")

    max_colors = quantized.width * quantized.height
    colors = quantized.getcolors(max_colors)
    if not colors:
        return []

    colors.sort(key=lambda x: x[0], reverse=True)
    return colors


def collapse_similar_colors(
    counted_colors: List[Tuple[int, RGB]],
    min_distance: float = 24.0,
    max_colors: int = 24,
) -> List[Tuple[int, RGB]]:
    """
    Merge near-duplicate colors while preserving frequency ordering.
    """
    kept: List[Tuple[int, RGB]] = []

    for count, rgb in counted_colors:
        too_close = False
        for _, existing in kept:
            if color_distance(rgb, existing) < min_distance:
                too_close = True
                break
        if not too_close:
            kept.append((count, rgb))
        if len(kept) >= max_colors:
            break

    return kept


# Selection helpers

def pick_dark_candidates(colors: List[RGB]) -> List[RGB]:
    """
    Gather dark candidates only; ordering is handled later by surface-style scoring.
    """
    return [c for c in colors if rel_luminance(c) <= 0.22]


def pick_light_candidates(colors: List[RGB]) -> List[RGB]:
    return sorted(
        [c for c in colors if rel_luminance(c) >= 0.28],
        key=lambda c: (rel_luminance(c), saturation(c))
    )

def pick_accent_candidates(colors: List[RGB]) -> List[RGB]:
    """
    Prefer saturated, visible, non-extreme colors.
    """
    candidates = [
        c for c in colors
        if saturation(c) >= 0.20 and 0.06 <= rel_luminance(c) <= 0.80
    ]
    # Rank by saturation, then frequency is already implicit in earlier ordering
    return sorted(candidates, key=lambda c: (saturation(c), brightness(c)), reverse=True)

def dark_surface_score(rgb: RGB, surface_style: str) -> float:
    """
    Lower is better.
    We want dark structural colors first, with saturation discipline.
    """
    lum = rel_luminance(rgb)
    sat = saturation(rgb)

    # Strongly prefer darker colors for all dark structural slots
    lum_term = lum * 10.0

    if surface_style == "neutral":
        # Strongly penalize saturation so structural surfaces stay sane
        sat_term = sat * 4.5
    elif surface_style == "tinted":
        # Allow some color identity, but still avoid turning surfaces into accents
        sat_term = sat * 2.0
    else:
        sat_term = sat * 4.5

    return lum_term + sat_term


def ordered_dark_candidates(colors: List[RGB], surface_style: str) -> List[RGB]:
    """
    Order dark candidates for structural slots based on surface policy.
    """
    return sorted(colors, key=lambda c: (dark_surface_score(c, surface_style), rel_luminance(c)))

def unique_by_hue(colors: List[RGB], min_hue_distance: float = 0.08) -> List[RGB]:
    """
    Keep colors with distinct hues so accent slots don't all become near-identical purples.
    """
    kept: List[RGB] = []

    for c in colors:
        h = hue(c)
        too_close = False
        for existing in kept:
            eh = hue(existing)
            diff = abs(h - eh)
            diff = min(diff, 1.0 - diff)  # hue wraparound
            if diff < min_hue_distance:
                too_close = True
                break
        if not too_close:
            kept.append(c)

    return kept


def choose_primary_accent(accent_candidates: List[RGB]) -> RGB:
    """
    Wallpaper-driven accent selection.
    Prefer saturated, visible accents in a comfortable UI luminance range.
    """
    if not accent_candidates:
        return (189, 147, 249)  # safe fallback if extraction is poor

    best = accent_candidates[0]
    best_score = -9999.0

    for c in accent_candidates:
        sat = saturation(c)
        lum = rel_luminance(c)

        # Prefer medium/medium-light accents that are vivid but not washed out
        lum_center = 0.35
        lum_penalty = abs(lum - lum_center)

        score = (
            sat * 3.0
            - lum_penalty * 2.0
        )

        if score > best_score:
            best_score = score
            best = c

    return best


# Palette synthesis

def synthesize_dark_ramp(darks: List[RGB], accent: RGB, surface_style: str) -> List[RGB]:
    """
    Produce base00..base03 with structural discipline.
    neutral = safer UI surfaces
    tinted  = allow more personality in surfaces
    """
    ordered = ordered_dark_candidates(darks, surface_style)

    if len(ordered) >= 4:
        chosen = ordered[:4]

        # Ensure final ramp is ordered by luminance ascending
        chosen = sorted(chosen, key=rel_luminance)

        # In neutral mode, if base02 is too saturated, pull it toward base01/base03
        if surface_style == "neutral":
            b0, b1, b2, b3 = chosen
            if saturation(b2) > 0.35:
                # create a more controlled surface color between b1 and b3
                blended = blend(b1, b3, 0.45)
                # if still too colorful, desaturate via blend toward gray-ish b3
                if saturation(blended) > 0.28:
                    blended = blend(blended, b3, 0.35)
                chosen[2] = blended

        return chosen

    if ordered:
        seed = ordered[0]
    else:
        # fallback: derive dark seed from accent but keep it sane
        seed = shift_saturation(darken(accent, 0.72), 0.35 if surface_style == "neutral" else 0.55)

    base00 = darken(seed, 0.08)
    base01 = lighten(base00, 0.05)
    base02 = lighten(base01, 0.06)
    base03 = lighten(base02, 0.09)

    if surface_style == "neutral":
        # keep the structural ramp from getting too colorful
        base01 = shift_saturation(base01, 0.70)
        base02 = shift_saturation(base02, 0.60)
        base03 = shift_saturation(base03, 0.55)

    return [base00, base01, base02, base03]


def synthesize_light_ramp(lights: List[RGB], dark_ramp: List[RGB]) -> List[RGB]:
    """
    Produce base04..base07
    """
    if len(lights) >= 4:
        ramp = sorted(lights[:4], key=rel_luminance)
        return ramp

    if lights:
        brightest = lights[-1]
        # ensure enough contrast
        base07 = brightest
    else:
        # fallback from dark ramp
        base07 = lighten(dark_ramp[0], 0.85)

    base06 = darken(base07, 0.08)
    base05 = darken(base06, 0.10)
    base04 = darken(base05, 0.22)

    return [base04, base05, base06, base07]


def synthesize_accent_slots(accent_pool: List[RGB], primary_accent: RGB) -> Dict[str, RGB]:
    """
    Fill base08..base0F semantically.
    """
    # Prefer distinct hues if possible
    hue_distinct = unique_by_hue(accent_pool)

    # Sensible semantic defaults if image doesn't provide enough variety
    default_red = (255, 117, 127)
    default_orange = (255, 184, 108)
    default_yellow = (241, 250, 140)
    default_green = (158, 206, 106)
    default_cyan = (115, 218, 202)

    # Try to pick by hue zones if available
    reds = [c for c in hue_distinct if hue(c) < 0.04 or hue(c) > 0.96]
    oranges = [c for c in hue_distinct if 0.04 <= hue(c) < 0.11]
    yellows = [c for c in hue_distinct if 0.11 <= hue(c) < 0.18]
    greens = [c for c in hue_distinct if 0.18 <= hue(c) < 0.45]
    cyans = [c for c in hue_distinct if 0.45 <= hue(c) < 0.58]

    # Secondary accent: another purple/blue if possible, else derive from primary
    purples_blues = [
        c for c in hue_distinct
        if 0.58 <= hue(c) <= 0.92 and color_distance(c, primary_accent) >= 18
    ]

    base0D = purples_blues[0] if purples_blues else shift_value(shift_saturation(primary_accent, 1.05), -0.08)
    base0E = primary_accent
    base0F = lighten(primary_accent, 0.10)

    return {
        "base08": reds[0] if reds else default_red,
        "base09": oranges[0] if oranges else default_orange,
        "base0A": yellows[0] if yellows else default_yellow,
        "base0B": greens[0] if greens else default_green,
        "base0C": cyans[0] if cyans else default_cyan,
        "base0D": base0D,
        "base0E": base0E,
        "base0F": base0F,
    }


def generate_base16_palette(
    img_path: str | Path,
    quantize_colors: int = 32,
    resize_to: int = 192,
    dedupe_distance: float = 24.0,
    surface_style: str = "neutral",
) -> Dict[str, RGB]:
    """
    Generate a Base16-ish palette suitable for theming.
    """
    counted = extract_quantized_colors(img_path, quantize_colors=quantize_colors, resize_to=resize_to)
    counted = collapse_similar_colors(counted, min_distance=dedupe_distance, max_colors=24)

    colors = [rgb for _, rgb in counted]
    if not colors:
        raise RuntimeError("no colors extracted from image")

    darks = pick_dark_candidates(colors)
    lights = pick_light_candidates(colors)
    accents = pick_accent_candidates(colors)

    primary_accent = choose_primary_accent(accents)

    dark_ramp = synthesize_dark_ramp(darks, primary_accent, surface_style=surface_style)
    light_ramp = synthesize_light_ramp(lights, dark_ramp)
    accent_slots = synthesize_accent_slots(accents, primary_accent)

    palette: Dict[str, RGB] = {
        "base00": dark_ramp[0],
        "base01": dark_ramp[1],
        "base02": dark_ramp[2],
        "base03": dark_ramp[3],
        "base04": light_ramp[0],
        "base05": light_ramp[1],
        "base06": light_ramp[2],
        "base07": light_ramp[3],
        **accent_slots,
    }

    return palette


# Output serializers (for theme_build module)

def base16_text(
    palette: Dict[str, RGB],
    scheme_name: str = "Generated-Palette",
    author: str = "palette_gen.py",
) -> str:
    """
    Return Base16-style INI text instead of printing directly.
    This is the reusable/module form used by theme_build.py.
    """
    lines = []
    lines.append("[dark]")
    lines.append("[colors]")
    lines.append(f"scheme_name = {scheme_name}")
    lines.append(f"scheme_author = {author}")
    lines.append("")

    for key in [f"base{n:02X}" for n in range(16)]:
        lines.append(f"{key} = {rgb_to_hex(palette[key])}")

    return "\n".join(lines)


def css_palette_text(palette: Dict[str, RGB]) -> str:
    """
    Return GTK3/GTK3.20+ palette layer for widgets/00-palette.css
    This is the generated color authority consumed by your widget modules.
    """
    def hx(key: str) -> str:
        return f"#{rgb_to_hex(palette[key])}"

    lines = []
    lines.append("/* Auto-generated by palette_gen.py */")
    lines.append("/* Dorakura-Kyoto GTK3 palette layer */")
    lines.append("")

    for key in [f"base{n:02X}" for n in range(16)]:
        lines.append(f"@define-color {key} {hx(key)};")

    lines.append("")

    lines.extend([
        f"@define-color accent_color {hx('base0E')};",
        f"@define-color accent_alt {hx('base0D')};",
        f"@define-color accent_bright {hx('base0F')};",
        f"@define-color destructive_color {hx('base08')};",
        f"@define-color warning_color {hx('base09')};",
        f"@define-color success_color {hx('base0B')};",
        f"@define-color info_color {hx('base0C')};",
        "",
        f"@define-color window_bg_color {hx('base00')};",
        f"@define-color view_bg_color {hx('base01')};",
        f"@define-color card_bg_color {hx('base02')};",
        f"@define-color border_color {hx('base03')};",
        "",
        f"@define-color muted_fg_color {hx('base04')};",
        f"@define-color window_fg_color {hx('base05')};",
        f"@define-color view_fg_color {hx('base06')};",
        f"@define-color heading_fg_color {hx('base07')};",
        "",
        f"@define-color theme_bg_color {hx('base00')};",
        f"@define-color theme_base_color {hx('base01')};",
        f"@define-color theme_fg_color {hx('base05')};",
        f"@define-color theme_text_color {hx('base06')};",
        f"@define-color theme_selected_bg_color {hx('base0E')};",
        f"@define-color theme_selected_fg_color {hx('base00')};",
        f"@define-color theme_unfocused_selected_bg_color {hx('base0D')};",
        f"@define-color theme_unfocused_selected_fg_color {hx('base00')};",
        "",
        f"@define-color insensitive_bg_color {hx('base01')};",
        f"@define-color insensitive_fg_color {hx('base04')};",
        f"@define-color insensitive_base_color {hx('base01')};",
        "",
        f"@define-color theme_tooltip_bg_color {hx('base01')};",
        f"@define-color theme_tooltip_fg_color {hx('base07')};",
        "",
        f"@define-color wm_bg_a {hx('base00')};",
        f"@define-color wm_bg_b {hx('base01')};",
        f"@define-color wm_border_focused {hx('base0E')};",
        f"@define-color wm_border_unfocused {hx('base03')};",
    ])

    return "\n".join(lines)


def gtk2_text(palette: Dict[str, RGB]) -> str:
    """
    Return GTK2-compatible colors include (colors.rc).
    theme_build.py writes this into gtk-2.0/colors.rc
    """
    def hx(key: str) -> str:
        return f"#{rgb_to_hex(palette[key])}"

    lines = []
    lines.append("# Auto-generated by palette_gen.py")
    lines.append("# Dorakura-Kyoto GTK2 colors include")
    lines.append("")

    for key in [f"base{n:02X}" for n in range(16)]:
        lines.append(f'color["{key}"] = "{hx(key)}"')

    lines.append("")

    scheme_pairs = [
        ("fg_color", hx("base05")),
        ("bg_color", hx("base00")),
        ("base_color", hx("base01")),
        ("text_color", hx("base06")),
        ("selected_bg_color", hx("base0E")),
        ("selected_fg_color", hx("base00")),
        ("tooltip_bg_color", hx("base01")),
        ("tooltip_fg_color", hx("base07")),
        ("link_color", hx("base0D")),
        ("visited_link_color", hx("base0F")),
        ("error_color", hx("base08")),
        ("warning_color", hx("base09")),
        ("success_color", hx("base0B")),
    ]

    scheme = "\\n".join(f"{k}:{v}" for k, v in scheme_pairs)
    lines.append(f'gtk-color-scheme = "{scheme}"')

    return "\n".join(lines)





# Output

def print_debug_table(palette: Dict[str, RGB]) -> None:
    print("\n# Debug")
    for key in [f"base{n:02X}" for n in range(16)]:
        rgb = palette[key]
        print(
            f"{key}  #{rgb_to_hex(rgb)}  "
            f"lum={rel_luminance(rgb):.3f}  "
            f"sat={saturation(rgb):.3f}  "
            f"hue={hue(rgb):.3f}"
        )


def write_text_file(path: str | Path, text: str) -> None:
    path = Path(path)
    if path.parent != Path("."):
        path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text + ("\n" if not text.endswith("\n") else ""), encoding="utf-8")


# 
# CLI

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate a Base16-style theme palette from an image."
    )
    parser.add_argument("image", help="Path to source image")
    parser.add_argument("-n", "--name", default="Dorakura-Auto", help="Scheme name")
    parser.add_argument("-a", "--author", default="palette_gen.py", help="Scheme author")
    parser.add_argument("-q", "--quantize", type=int, default=32, help="Quantization color count (default: 32)")
    parser.add_argument("-r", "--resize", type=int, default=192, help="Thumbnail max size (default: 192)")
    parser.add_argument(
        "--dedupe-distance",
        type=float,
        default=24.0,
        help="Minimum RGB distance between kept colors (default: 24.0)"
    )
    parser.add_argument(
        "--surface-style",
        choices=["neutral", "tinted"],
        default="neutral",
        help="How aggressively dark surfaces may keep color tint (default: neutral)"
    )
    parser.add_argument(
        "--format",
        choices=["base16", "css", "gtk2", "all"],
        default="base16",
        help="Output format (default: base16)"
    )
    parser.add_argument(
        "--output",
        help="Single output file for the selected format (ignored for --format all)"
    )
    parser.add_argument(
        "--base16-output",
        help="Write Base16/INI output to this path"
    )
    parser.add_argument(
        "--css-output",
        help="Write GTK3 CSS palette output to this path"
    )
    parser.add_argument(
        "--gtk2-output",
        help="Write GTK2 colors.rc output to this path"
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Print luminance/saturation/hue debug table"
    )
    return parser.parse_args()
    


def main() -> int:
    args = parse_args()

    palette = generate_base16_palette(
        img_path=args.image,
        quantize_colors=args.quantize,
        resize_to=args.resize,
        dedupe_distance=args.dedupe_distance,
        surface_style=args.surface_style,
    )

    base16_out = base16_text(palette, scheme_name=args.name, author=args.author)
    css_out = css_palette_text(palette)
    gtk2_out = gtk2_text(palette)

    if args.format == "base16":
        if args.output:
            write_text_file(args.output, base16_out)
        else:
            print(base16_out)

    elif args.format == "css":
        if args.output:
            write_text_file(args.output, css_out)
        else:
            print(css_out)

    elif args.format == "gtk2":
        if args.output:
            write_text_file(args.output, gtk2_out)
        else:
            print(gtk2_out)

    elif args.format == "all":
        wrote_any = False

        if args.base16_output:
            write_text_file(args.base16_output, base16_out)
            wrote_any = True

        if args.css_output:
            write_text_file(args.css_output, css_out)
            wrote_any = True

        if args.gtk2_output:
            write_text_file(args.gtk2_output, gtk2_out)
            wrote_any = True

        # If no file outputs were given, print all sections to stdout
        if not wrote_any:
            print("### BASE16 ###")
            print(base16_out)
            print()
            print("### GTK3 CSS ###")
            print(css_out)
            print()
            print("### GTK2 RC ###")
            print(gtk2_out)

    if args.debug:
        print_debug_table(palette)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
