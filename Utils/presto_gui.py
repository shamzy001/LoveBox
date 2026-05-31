#!/usr/bin/env python3
"""
presto_gui.py — Tkinter UI for presto_crop.py

Run from the same folder as presto_crop.py:
    python3 presto_gui.py
    python3 presto_gui.py photo.jpg
"""

import sys
from pathlib import Path

try:
    import tkinter as tk
    from tkinter import ttk, filedialog, messagebox
except ImportError:
    print("tkinter not found. Install with: sudo apt install python3-tk")
    sys.exit(1)

try:
    from PIL import Image, ImageOps, ImageTk
    import cv2
    import numpy as np
except ImportError as e:
    print(f"Missing library: {e}\nInstall with: pip install Pillow opencv-python")
    sys.exit(1)

script_dir = Path(__file__).parent
sys.path.insert(0, str(script_dir))
try:
    from presto_crop import smart_crop, detect_faces, TARGET
except ImportError:
    print("presto_crop.py not found — place presto_gui.py in the same folder.")
    sys.exit(1)


PREVIEW_SIZE = 480
PANEL_WIDTH  = 300
BG           = "#1e1e1e"
BG2          = "#2a2a2a"
BG3          = "#383838"
ACCENT       = "#4a9eff"
TEXT         = "#e8e8e8"
TEXT_DIM     = "#888888"
GREEN        = "#4caf50"
RED          = "#f44336"
FONT         = ("Segoe UI", 9)
FONT_BOLD    = ("Segoe UI", 9, "bold")
FONT_TITLE   = ("Segoe UI", 11, "bold")
FONT_SMALL   = ("Segoe UI", 8)


def make_spinbox(parent, var, from_, to, increment, width=7, command=None):
    """A dark-themed Spinbox that calls command on any change."""
    sb = tk.Spinbox(
        parent,
        textvariable=var,
        from_=from_, to=to,
        increment=increment,
        width=width,
        bg=BG3, fg=TEXT,
        insertbackground=TEXT,
        buttonbackground=BG3,
        relief="flat",
        font=FONT,
        command=command,
    )
    if command:
        var.trace_add("write", lambda *_: command())
    return sb


class PrestoGUI:
    def __init__(self, root, initial_file=None):
        self.root = root
        self.root.title("Presto Photo Processor")
        self.root.configure(bg=BG)
        self.root.resizable(False, False)

        self.source_img  = None
        self.source_path = None
        self.result_img  = None
        self.preview_tk  = None
        self._update_job = None
        self._trace_ids  = []

        self._build_ui()
        self._set_controls_state(False)

        if initial_file:
            self._load_file(initial_file)

    # ------------------------------------------------------------------ #
    #  UI BUILD                                                            #
    # ------------------------------------------------------------------ #

    def _build_ui(self):
        # Top bar
        top = tk.Frame(self.root, bg=BG, pady=6, padx=10)
        top.pack(fill="x")
        tk.Label(top, text="🖼  Presto Photo Processor",
                 bg=BG, fg=TEXT, font=FONT_TITLE).pack(side="left")
        tk.Button(top, text="Open Photo…", command=self._open_file,
                  bg=ACCENT, fg="white", font=FONT_BOLD,
                  relief="flat", padx=10, pady=4, cursor="hand2").pack(side="right")

        ttk.Separator(self.root, orient="horizontal").pack(fill="x")

        main = tk.Frame(self.root, bg=BG)
        main.pack(fill="both", expand=True)

        # Left: preview
        left = tk.Frame(main, bg=BG, padx=10, pady=10)
        left.pack(side="left", fill="both")
        tk.Label(left, text="PREVIEW  (480 × 480)",
                 bg=BG, fg=TEXT_DIM, font=FONT_SMALL).pack(anchor="w")
        self.canvas = tk.Canvas(left, width=PREVIEW_SIZE, height=PREVIEW_SIZE,
                                bg="#111", highlightthickness=1,
                                highlightbackground="#444")
        self.canvas.pack()
        self.status_lbl = tk.Label(left, text="No file loaded",
                                   bg=BG, fg=TEXT_DIM, font=FONT_SMALL)
        self.status_lbl.pack(anchor="w", pady=(4, 0))

        # Right: controls
        right = tk.Frame(main, bg=BG2, width=PANEL_WIDTH, padx=14, pady=10)
        right.pack(side="right", fill="y")
        right.pack_propagate(False)
        self._build_controls(right)

    def _section(self, parent, text):
        tk.Label(parent, text=text, bg=BG2, fg=ACCENT,
                 font=FONT_BOLD).pack(anchor="w", pady=(10, 0))
        ttk.Separator(parent, orient="horizontal").pack(fill="x", pady=(2, 6))

    def _build_controls(self, p):

        # ── MODE ──────────────────────────────────────────────────────
        self._section(p, "MODE")
        self.mode_var = tk.StringVar(value="crop")
        mf = tk.Frame(p, bg=BG2)
        mf.pack(fill="x", pady=2)
        for val, label in [("crop", "Smart Crop"), ("letterbox", "Letterbox")]:
            tk.Radiobutton(mf, text=label, variable=self.mode_var, value=val,
                           bg=BG2, fg=TEXT, selectcolor=BG3,
                           activebackground=BG2, font=FONT,
                           command=self._schedule_update).pack(side="left", padx=(0, 14))

        # ── CROP BIAS ─────────────────────────────────────────────────
        self._section(p, "CROP BIAS")
        self.bias_var = tk.StringVar(value="auto")
        bias_frame = tk.Frame(p, bg=BG2)
        bias_frame.pack(fill="x", pady=2)
        tk.Label(bias_frame, text="Focus:", bg=BG2, fg=TEXT,
                 font=FONT).pack(side="left", padx=(0, 6))
        bias_menu = ttk.Combobox(
            bias_frame, textvariable=self.bias_var,
            values=["auto", "center", "top", "bottom", "left", "right"],
            state="readonly", width=10, font=FONT,
        )
        bias_menu.pack(side="left")
        bias_menu.bind("<<ComboboxSelected>>", lambda _: self._schedule_update())

        self.face_lbl = tk.Label(p, text="", bg=BG2, fg=TEXT_DIM, font=FONT_SMALL)
        self.face_lbl.pack(anchor="w", pady=(2, 0))

        # ── ZOOM ──────────────────────────────────────────────────────
        self._section(p, "ZOOM")

        self.zoom_var = tk.DoubleVar(value=1.0)
        zf = tk.Frame(p, bg=BG2)
        zf.pack(fill="x", pady=2)
        tk.Label(zf, text="Zoom factor:", bg=BG2, fg=TEXT,
                 font=FONT).pack(side="left", padx=(0, 8))
        zoom_sb = make_spinbox(zf, self.zoom_var, 0.1, 8.0, 0.05,
                               width=6, command=self._schedule_update)
        zoom_sb.pack(side="left")
        tk.Label(zf, text="×", bg=BG2, fg=TEXT_DIM, font=FONT).pack(side="left", padx=(2, 0))
        self._controls_zoom = [zoom_sb]

        # Zoom presets
        pf = tk.Frame(p, bg=BG2)
        pf.pack(fill="x", pady=(4, 0))
        tk.Label(pf, text="Presets:", bg=BG2, fg=TEXT_DIM,
                 font=FONT_SMALL).pack(side="left", padx=(0, 4))
        for z in [0.5, 0.75, 1.0, 1.5, 2.0, 3.0]:
            tk.Button(pf, text=f"{z}×",
                      command=lambda v=z: self._set_zoom(v),
                      bg=BG3, fg=TEXT, font=FONT_SMALL,
                      relief="flat", padx=5, pady=2,
                      cursor="hand2").pack(side="left", padx=1)

        # ── NUDGE ─────────────────────────────────────────────────────
        self._section(p, "NUDGE  (% of image)")

        self.nudge_x = tk.IntVar(value=0)
        self.nudge_y = tk.IntVar(value=0)

        nxf = tk.Frame(p, bg=BG2)
        nxf.pack(fill="x", pady=3)
        tk.Label(nxf, text="← Left / Right →", bg=BG2, fg=TEXT,
                 font=FONT, width=17, anchor="w").pack(side="left")
        nx_sb = make_spinbox(nxf, self.nudge_x, -50, 50, 1,
                             width=5, command=self._schedule_update)
        nx_sb.pack(side="left")
        tk.Label(nxf, text="%", bg=BG2, fg=TEXT_DIM, font=FONT).pack(side="left", padx=(2, 0))

        nyf = tk.Frame(p, bg=BG2)
        nyf.pack(fill="x", pady=3)
        tk.Label(nyf, text="↑ Up / Down ↓", bg=BG2, fg=TEXT,
                 font=FONT, width=17, anchor="w").pack(side="left")
        ny_sb = make_spinbox(nyf, self.nudge_y, -50, 50, 1,
                             width=5, command=self._schedule_update)
        ny_sb.pack(side="left")
        tk.Label(nyf, text="%", bg=BG2, fg=TEXT_DIM, font=FONT).pack(side="left", padx=(2, 0))

        self._controls_nudge = [nx_sb, ny_sb]

        rf = tk.Frame(p, bg=BG2)
        rf.pack(fill="x", pady=(6, 0))
        tk.Button(rf, text="Reset Nudge", command=self._reset_nudge,
                  bg=BG3, fg=TEXT, font=FONT_SMALL,
                  relief="flat", padx=8, pady=3,
                  cursor="hand2").pack(side="left")
        tk.Button(rf, text="Reset All", command=self._reset_all,
                  bg=BG3, fg=TEXT, font=FONT_SMALL,
                  relief="flat", padx=8, pady=3,
                  cursor="hand2").pack(side="left", padx=(6, 0))

        # ── SAVE ──────────────────────────────────────────────────────
        ttk.Separator(p, orient="horizontal").pack(fill="x", pady=(16, 8))
        self.save_btn = tk.Button(
            p, text="💾  Save to Presto Photos…",
            command=self._save,
            bg=GREEN, fg="white", font=FONT_BOLD,
            relief="flat", pady=8, cursor="hand2")
        self.save_btn.pack(fill="x")
        self.save_lbl = tk.Label(p, text="", bg=BG2, fg=GREEN,
                                 font=FONT_SMALL, wraplength=PANEL_WIDTH - 20)
        self.save_lbl.pack(anchor="w", pady=(4, 0))

        self._all_controls = (
            self._controls_zoom + self._controls_nudge + [self.save_btn]
        )

    # ------------------------------------------------------------------ #
    #  CONTROL CALLBACKS                                                   #
    # ------------------------------------------------------------------ #

    def _set_zoom(self, val):
        self.zoom_var.set(round(val, 2))
        self._schedule_update()

    def _reset_nudge(self):
        self.nudge_x.set(0)
        self.nudge_y.set(0)
        self._schedule_update()

    def _reset_all(self):
        self.zoom_var.set(1.0)
        self.nudge_x.set(0)
        self.nudge_y.set(0)
        self.bias_var.set("auto")
        self.mode_var.set("crop")
        self._schedule_update()

    # ------------------------------------------------------------------ #
    #  FILE HANDLING                                                       #
    # ------------------------------------------------------------------ #

    def _open_file(self):
        path = filedialog.askopenfilename(
            title="Open Photo",
            filetypes=[
                ("Images", "*.jpg *.jpeg *.png *.bmp *.webp *.tiff *.tif"),
                ("All files", "*.*"),
            ]
        )
        if path:
            self._load_file(path)

    def _load_file(self, path):
        try:
            img = Image.open(path).convert("RGB")
            try:
                img = ImageOps.exif_transpose(img)
            except Exception:
                pass
            self.source_img  = img
            self.source_path = Path(path)
            self.save_lbl.config(text="")

            n = len(detect_faces(img))
            if n > 0:
                self.face_lbl.config(
                    text=f"  ✓ {n} face{'s' if n > 1 else ''} detected", fg=GREEN)
            else:
                self.face_lbl.config(
                    text="  No faces detected — using bias/center", fg=TEXT_DIM)

            self._set_controls_state(True)
            self._update_preview()
        except Exception as e:
            messagebox.showerror("Error", f"Could not open image:\n{e}")

    # ------------------------------------------------------------------ #
    #  PREVIEW                                                             #
    # ------------------------------------------------------------------ #

    def _schedule_update(self, *_):
        if self._update_job:
            self.root.after_cancel(self._update_job)
        self._update_job = self.root.after(120, self._update_preview)

    def _update_preview(self):
        self._update_job = None
        if self.source_img is None:
            return
        try:
            zoom = float(self.zoom_var.get())
            zoom = max(0.1, min(8.0, zoom))
        except (ValueError, tk.TclError):
            return
        try:
            nx = int(self.nudge_x.get())
            ny = int(self.nudge_y.get())
        except (ValueError, tk.TclError):
            return

        bias    = self.bias_var.get()
        padding = self.mode_var.get() == "letterbox"

        try:
            result, method = smart_crop(
                self.source_img.copy(),
                bias=bias, nudge=(nx, ny), zoom=zoom, padding=padding
            )
            self.result_img = result
            tk_img = ImageTk.PhotoImage(result)
            self.preview_tk = tk_img
            self.canvas.delete("all")
            self.canvas.create_image(0, 0, anchor="nw", image=tk_img)
            w, h = self.source_img.size
            self.status_lbl.config(
                text=f"{self.source_path.name}  •  {w}×{h} → 480×480  [{method}]",
                fg=TEXT_DIM)
        except Exception as e:
            self.status_lbl.config(text=f"Error: {e}", fg=RED)

    # ------------------------------------------------------------------ #
    #  SAVE                                                                #
    # ------------------------------------------------------------------ #

    def _save(self):
        if self.result_img is None:
            return
        initial_dir = self.source_path.parent / "presto_photos"
        initial_dir.mkdir(parents=True, exist_ok=True)
        out_path = filedialog.asksaveasfilename(
            title="Save Presto Photo",
            initialdir=str(initial_dir),
            initialfile=self.source_path.stem + ".jpg",
            defaultextension=".jpg",
            filetypes=[("JPEG", "*.jpg *.jpeg"), ("All files", "*.*")],
        )
        if not out_path:
            return
        try:
            self.result_img.save(
                out_path, "JPEG", quality=92,
                progressive=False, optimize=False
            )
            self.save_lbl.config(text=f"✓ Saved: {Path(out_path).name}", fg=GREEN)
        except Exception as e:
            messagebox.showerror("Save failed", str(e))

    # ------------------------------------------------------------------ #
    #  HELPERS                                                             #
    # ------------------------------------------------------------------ #

    def _set_controls_state(self, enabled):
        state = "normal" if enabled else "disabled"
        for w in self._all_controls:
            w.config(state=state)


def main():
    initial = sys.argv[1] if len(sys.argv) > 1 else None
    root = tk.Tk()
    root.configure(bg=BG)
    style = ttk.Style()
    style.theme_use("default")
    style.configure("TSeparator", background="#444")
    style.configure("TCombobox",
                    fieldbackground=BG3, background=BG3,
                    foreground=TEXT, selectbackground=ACCENT)
    app = PrestoGUI(root, initial_file=initial)
    root.update_idletasks()
    w = root.winfo_width()
    h = root.winfo_height()
    x = (root.winfo_screenwidth()  - w) // 2
    y = (root.winfo_screenheight() - h) // 2
    root.geometry(f"+{x}+{y}")
    root.mainloop()


if __name__ == "__main__":
    main()
