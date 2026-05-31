#!/usr/bin/env python3
"""
presto_crop.py — Smart photo resizer for Pimoroni Presto (480×480)

Usage:
    python3 presto_crop.py photo.jpg
    python3 presto_crop.py *.jpg
    python3 presto_crop.py input_folder/
    python3 presto_crop.py photo.jpg --output my_folder
    python3 presto_crop.py photo.jpg --preview
    python3 presto_crop.py photo.jpg --bias top
    python3 presto_crop.py photo.jpg --bias center
    python3 presto_crop.py photo.jpg --padding
    python3 presto_crop.py photo.jpg --nudge -10,5   # shift crop left 10%, down 5%

Strategy (auto mode):
    1. Detect all faces.
    2. Compute a bounding box around the whole face group.
    3. If that box is wider/taller than 480px, scale the image down first.
    4. Crop to 480x480 centered on the face group.
    5. Apply --nudge offset after centering (clamped to image bounds).
    6. If no faces found, fall back to center crop.
    7. Always save as baseline JPEG (required by jpegdec on Presto).
"""

import sys
import os
import argparse
import glob
from pathlib import Path

try:
    from PIL import Image, ImageOps
    import cv2
    import numpy as np
except ImportError as e:
    print(f"Missing library: {e}")
    print("Install with: pip install Pillow opencv-python")
    sys.exit(1)


TARGET = 480
FACE_CASCADE = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")


def detect_faces(img_pil):
    """Return list of (x, y, w, h) face rectangles. Empty list if none found."""
    img_np = np.array(img_pil.convert("RGB"))
    gray = cv2.cvtColor(img_np, cv2.COLOR_RGB2GRAY)
    gray = cv2.equalizeHist(gray)

    faces = FACE_CASCADE.detectMultiScale(
        gray, scaleFactor=1.1, minNeighbors=5, minSize=(30, 30),
        flags=cv2.CASCADE_SCALE_IMAGE,
    )
    if len(faces) == 0:
        faces = FACE_CASCADE.detectMultiScale(
            gray, scaleFactor=1.05, minNeighbors=3, minSize=(20, 20),
        )
    return list(faces) if len(faces) > 0 else []


def face_bounding_box(faces):
    """
    Return (cx, cy, span):
        cx, cy  — center of the tightest rectangle around ALL faces
        span    — side length of that rectangle (longest side) x 1.4 padding
    """
    x_min = min(x for (x, y, w, h) in faces)
    y_min = min(y for (x, y, w, h) in faces)
    x_max = max(x + w for (x, y, w, h) in faces)
    y_max = max(y + h for (x, y, w, h) in faces)

    cx = (x_min + x_max) // 2
    cy = (y_min + y_max) // 2
    span = int(max(x_max - x_min, y_max - y_min) * 1.4)
    return cx, cy, span


def smart_crop(img, bias="auto", nudge=(0, 0), zoom=1.0, padding=False, padding_color=None):
    """
    Scale-then-crop img (PIL Image) to exactly TARGET x TARGET.

    nudge: (dx, dy) percentage of the image to shift the crop center after
           the initial focus point is set. Positive = right/down, negative = left/up.
           e.g. (-10, 0) shifts the crop 10% to the left.
           Clamped so the crop never goes outside the image bounds.
    """
    if padding:
        return letterbox(img, padding_color)

    w, h = img.size

    if bias == "auto":
        faces = detect_faces(img)
        if faces:
            cx, cy, span = face_bounding_box(faces)
            method = f"face ({len(faces)} detected)"

            # If the face group is larger than TARGET, scale down first
            if span > TARGET:
                scale = TARGET / span
                new_w = max(TARGET, int(w * scale))
                new_h = max(TARGET, int(h * scale))
                img = img.resize((new_w, new_h), Image.LANCZOS)
                cx = int(cx * scale)
                cy = int(cy * scale)
                w, h = img.size
                method = f"face ({len(faces)}, scaled {scale:.2f}x)"
        else:
            cx, cy = w // 2, h // 2
            method = "center (no faces)"

    elif bias == "top":
        cx, cy = w // 2, 0
        method = "top"
    elif bias == "bottom":
        cx, cy = w // 2, h
        method = "bottom"
    elif bias == "left":
        cx, cy = 0, h // 2
        method = "left"
    elif bias == "right":
        cx, cy = w, h // 2
        method = "right"
    else:  # center
        cx, cy = w // 2, h // 2
        method = "center"

    # --- Apply nudge (percentage of image dimensions) ---
    dx, dy = nudge
    if dx != 0 or dy != 0:
        cx += int(w * dx / 100)
        cy += int(h * dy / 100)
        method += f" nudge({dx:+d}%,{dy:+d}%)"

    # --- Compute square crop box centered on (cx, cy), clamped to bounds ---
    # zoom > 1.0 = zoom in (smaller crop window, magnified to TARGET)
    # zoom < 1.0 = zoom out (larger crop window, more context visible)
    # zoom = 1.0 = normal (crop the largest square that fits)
    base_side = min(w, h)
    side = max(TARGET, int(base_side / zoom))
    side = min(side, min(w, h))  # can't crop larger than the image
    left   = max(0, min(cx - side // 2, w - side))
    top    = max(0, min(cy - side // 2, h - side))
    right  = left + side
    bottom = top + side

    if zoom != 1.0:
        method += f" zoom({zoom:.2f}x)"

    cropped = img.crop((left, top, right, bottom))
    resized = cropped.resize((TARGET, TARGET), Image.LANCZOS)
    return resized, method


def letterbox(img, color=None):
    """Fit image inside TARGET x TARGET with colored bars (no crop)."""
    w, h = img.size
    scale = TARGET / max(w, h)
    new_w = int(w * scale)
    new_h = int(h * scale)
    resized = img.resize((new_w, new_h), Image.LANCZOS)

    if color is None:
        img_np = np.array(img.convert("RGB"))
        edges = np.concatenate([
            img_np[0, :, :], img_np[-1, :, :],
            img_np[:, 0, :], img_np[:, -1, :]
        ], axis=0)
        avg = (edges.mean(axis=0) * 0.5).astype(int)
        color = (int(avg[0]), int(avg[1]), int(avg[2]))

    canvas = Image.new("RGB", (TARGET, TARGET), color)
    canvas.paste(resized, ((TARGET - new_w) // 2, (TARGET - new_h) // 2))
    return canvas, "letterbox"


def process_image(input_path, output_path, bias="auto", nudge=(0, 0), zoom=1.0, padding=False,
                  padding_color=None, preview=False, quiet=False):
    try:
        img = Image.open(input_path).convert("RGB")
        original_size = img.size

        # Auto-rotate based on EXIF
        try:
            img = ImageOps.exif_transpose(img)
        except Exception:
            pass

        result, method = smart_crop(img, bias=bias, nudge=nudge, zoom=zoom, padding=padding,
                                    padding_color=padding_color)

        if preview:
            ow, oh = original_size
            ph = max(oh, TARGET)
            preview_img = Image.new("RGB", (ow + TARGET + 20, ph), (30, 30, 30))
            thumb = img.copy()
            thumb.thumbnail((ow, ph))
            preview_img.paste(thumb, (0, (ph - thumb.size[1]) // 2))
            preview_img.paste(result, (ow + 20, (ph - TARGET) // 2))
            preview_img.show(title=f"{Path(input_path).name} -> {method}")

        # progressive=False + optimize=False = baseline JPEG, required by jpegdec on Presto
        # (Facebook, Instagram, WhatsApp etc. all export progressive JPEGs which jpegdec cannot read)
        result.save(output_path, "JPEG", quality=92, progressive=False, optimize=False)

        if not quiet:
            ow, oh = original_size
            print(f"  ✓  {Path(input_path).name:40s}  {ow}x{oh} -> 480x480  [{method}]")
        return True

    except Exception as e:
        print(f"  ✗  {Path(input_path).name}: {e}")
        return False


def collect_inputs(args_input):
    extensions = {".jpg", ".jpeg", ".png", ".bmp", ".webp", ".tiff", ".tif"}
    paths = []
    for item in args_input:
        p = Path(item)
        if p.is_dir():
            for ext in extensions:
                paths.extend(p.glob(f"*{ext}"))
                paths.extend(p.glob(f"*{ext.upper()}"))
        elif p.exists():
            paths.append(p)
        else:
            expanded = [Path(g) for g in glob.glob(item)]
            paths.extend([g for g in expanded if g.suffix.lower() in extensions])
    return sorted(set(paths))


def parse_color(s):
    s = s.strip()
    if s.startswith("#"):
        s = s[1:]
        return (int(s[0:2], 16), int(s[2:4], 16), int(s[4:6], 16))
    parts = s.split(",")
    return (int(parts[0]), int(parts[1]), int(parts[2]))


def parse_nudge(s):
    """Parse 'dx,dy' into (int, int). Each value is a percentage, e.g. '-10,5'."""
    try:
        parts = s.split(",")
        if len(parts) != 2:
            raise ValueError
        return (int(parts[0]), int(parts[1]))
    except Exception:
        raise argparse.ArgumentTypeError(
            f"--nudge must be 'dx,dy' as percentages, e.g. '-10,0' or '5,-15'"
        )


def main():
    parser = argparse.ArgumentParser(
        description="Smart-crop photos to 480x480 for Pimoroni Presto",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python3 presto_crop.py photo.jpg
  python3 presto_crop.py *.jpg --output presto_photos/
  python3 presto_crop.py myfolder/ --output output/ --bias center
  python3 presto_crop.py photo.jpg --nudge='-10,0'   shift crop 10% left (use = for negatives)
  python3 presto_crop.py photo.jpg --nudge='0,-15'   shift crop 15% up
  python3 presto_crop.py photo.jpg --nudge 8,5       shift crop 8% right, 5% down
  python3 presto_crop.py photo.jpg --zoom 1.5        zoom in 50%% (tighter on subject)
  python3 presto_crop.py photo.jpg --zoom 0.8        zoom out 20%% (more context)
  python3 presto_crop.py photo.jpg --zoom 1.3 --nudge='-5,0'  zoom + nudge combined
  python3 presto_crop.py photo.jpg --padding --preview
  python3 presto_crop.py photo.jpg --padding --padding-color 0,0,0
        """
    )
    parser.add_argument("input", nargs="+", help="Image file(s), folder, or glob pattern")
    parser.add_argument("-o", "--output", default="presto_photos",
                        help="Output folder (default: presto_photos/)")
    parser.add_argument("--bias", choices=["auto", "center", "top", "bottom", "left", "right"],
                        default="auto",
                        help="Crop focus: auto=face detection, others=force direction")
    parser.add_argument("--nudge", metavar="dx,dy", type=parse_nudge, default=(0, 0),
                        help="Shift crop center by percentage after focus point set. "
                             "e.g. '-10,0' = 10%% left, '0,-15' = 15%% up, '8,5' = right+down")
    parser.add_argument("--zoom", metavar="FACTOR", type=float, default=1.0,
                        help="Zoom factor: >1.0 zooms in (tighter crop), <1.0 zooms out (more context). "
                             "e.g. 1.5 = 50%% closer, 0.8 = 20%% further out (default: 1.0)")
    parser.add_argument("--padding", action="store_true",
                        help="Letterbox instead of crop (adds color bars, nothing cut off)")
    parser.add_argument("--padding-color", metavar="COLOR",
                        help="Bar color: '#1a1a1a' or '26,26,26' (default: auto from image edges)")
    parser.add_argument("--preview", action="store_true",
                        help="Open a before/after preview window for each image")
    parser.add_argument("--prefix", default="",
                        help="Filename prefix for output files (e.g. 'presto_')")
    parser.add_argument("--quiet", "-q", action="store_true",
                        help="Suppress per-file output")

    args = parser.parse_args()

    out_dir = Path(args.output)
    out_dir.mkdir(parents=True, exist_ok=True)

    pad_color = None
    if args.padding_color:
        try:
            pad_color = parse_color(args.padding_color)
        except Exception:
            print(f"Warning: could not parse --padding-color '{args.padding_color}'. Using auto.")

    files = collect_inputs(args.input)
    if not files:
        print("No image files found.")
        sys.exit(1)

    nudge_str = f" nudge({args.nudge[0]:+d}%,{args.nudge[1]:+d}%)" if args.nudge != (0,0) else ""
    zoom_str = f"  zoom({args.zoom:.2f}x)" if args.zoom != 1.0 else ""
    print(f"\nPresto Photo Processor  ->  {out_dir}/")
    print(f"Mode: {'letterbox' if args.padding else 'smart crop'}  |  "
          f"Bias: {args.bias}{nudge_str}{zoom_str}  |  {len(files)} file(s)\n")

    ok = 0
    for f in files:
        out_name = args.prefix + f.stem + ".jpg"
        out_path = out_dir / out_name
        if process_image(f, out_path, bias=args.bias, nudge=args.nudge, zoom=args.zoom, padding=args.padding,
                         padding_color=pad_color, preview=args.preview, quiet=args.quiet):
            ok += 1

    print(f"\nDone: {ok}/{len(files)} converted  ->  {out_dir}/")


if __name__ == "__main__":
    main()
