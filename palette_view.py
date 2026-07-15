#!/usr/bin/env python3
import sys
import re
import argparse
from pathlib import Path
from PIL import Image, ImageDraw

def extract_hex_colors(text: str) -> list[str]:
   
    hex_pattern = re.compile(r'(?:#|0x)?([0-9a-fA-F]{6})\b')
    return [f"#{m.lower()}" for m in hex_pattern.findall(text)]

def generate_palette_image(colors: list[str], block_size: int = 80) -> Image.Image:
    
    if not colors:
        raise ValueError("No valid hex colors found to generate a palette.")
        
    width = len(colors) * block_size
    height = block_size
    
    img = Image.new("RGB", (width, height), "#000000")
    draw = ImageDraw.Draw(img)
    
    for i, color in enumerate(colors):
        x0 = i * block_size
        y0 = 0
        x1 = x0 + block_size
        y1 = height
        draw.rectangle([x0, y0, x1, y1], fill=color)
        
    return img

def main():
    parser = argparse.ArgumentParser(
        description="Generate a visual image from a base-16 hex color palette text file or pipe."
    )
    parser.add_argument(
        "input_file", 
        nargs="?", 
        type=str, 
        help="Path to the palette text file (omitted if piping via stdin)"
    )
    parser.add_argument(
        "-o", "--output", 
        type=str, 
        default="palette.png", 
        help="Output image path (default: palette.png)"
    )
    parser.add_argument(
        "-s", "--size", 
        type=int, 
        default=100, 
        help="Size of each color block square in pixels (default: 100)"
    )
    
    args = parser.parse_args()
    
    if args.input_file:
        input_path = Path(args.input_file)
        if not input_path.is_file():
            print(f"Error: File not found: {args.input_file}", file=sys.stderr)
            sys.exit(1)
        raw_text = input_path.read_text()
    else:
        if sys.stdin.isatty():
            parser.print_help()
            sys.exit(0)
        raw_text = sys.stdin.read()

    try:
        colors = extract_hex_colors(raw_text)
        print(f"Loaded {len(colors)} colors from source.", file=sys.stderr)
        
        palette_img = generate_palette_image(colors, block_size=args.size)
        palette_img.save(args.output)
        print(f"Palette image saved successfully to {args.output}", file=sys.stderr)
        
    except Exception as e:
        print(f"Runtime Error: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
