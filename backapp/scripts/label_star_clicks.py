"""Click-to-label stars on lock crops. Tkinter, no extra GUI package.

Run from anywhere:
  python backapp/scripts/label_star_clicks.py

Click the star. Coordinates are stored in PNG pixels and Bayer-crop pixels.
"""

from __future__ import annotations

import argparse
import json
import sys
import tkinter as tk
from pathlib import Path

from PIL import Image, ImageDraw, ImageTk

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DIR = ROOT / "savedimgs" / "test_lock_crops"
LABELS_NAME = "labels.json"
BAYER_PER_PNG = 2.0


def _load_manifest(folder: Path) -> dict:
    path = folder / "manifest.json"
    if path.is_file():
        return json.loads(path.read_text(encoding="utf-8"))
    return {}


def _pngs(folder: Path) -> list[Path]:
    return sorted(folder.glob("frame_*_crop.png"))


def _load_labels(path: Path) -> dict:
    if not path.is_file():
        return {"frames": {}}
    raw = json.loads(path.read_text(encoding="utf-8"))
    if "frames" not in raw:
        raw["frames"] = {}
    return raw


class LabelApp:
    def __init__(self, folder: Path, zoom: int) -> None:
        self.folder = folder
        self.zoom = max(1, int(zoom))
        self.paths = _pngs(folder)
        if not self.paths:
            raise SystemExit(f"no frame_*_crop.png in {folder}")
        self.manifest = _load_manifest(folder)
        self.by_stem = {
            f["stem"]: f for f in self.manifest.get("frames") or [] if f.get("stem")
        }
        self.labels_path = folder / LABELS_NAME
        self.store = _load_labels(self.labels_path)
        self.index = self._first_unlabeled()
        self.photo = None
        self.base_w = 0
        self.base_h = 0

        self.root = tk.Tk()
        self.root.title("star click labels")
        self.status = tk.StringVar()
        tk.Label(self.root, textvariable=self.status, font=("Segoe UI", 11)).pack(
            anchor="w", padx=8, pady=(8, 4)
        )
        hint = (
            "click star  ·  ← → prev/next  ·  Backspace clear  ·  Space skip  ·  auto-saved"
        )
        tk.Label(self.root, text=hint, fg="#555").pack(anchor="w", padx=8)
        self.canvas = tk.Canvas(self.root, highlightthickness=1, highlightbackground="#333")
        self.canvas.pack(padx=8, pady=8)
        self.canvas.bind("<Button-1>", self.on_click)
        self.root.bind("<Left>", lambda e: self.step(-1))
        self.root.bind("<Right>", lambda e: self.step(1))
        self.root.bind("<BackSpace>", lambda e: self.clear_current())
        self.root.bind("<space>", lambda e: self.step(1))
        self.root.bind("q", lambda e: self.root.destroy())
        self.root.protocol("WM_DELETE_WINDOW", self.root.destroy)
        self.show()

    def _first_unlabeled(self) -> int:
        labeled = self.store["frames"]
        for i, path in enumerate(self.paths):
            if path.stem.replace("_crop", "") not in labeled:
                return i
        return 0

    def stem(self) -> str:
        return self.paths[self.index].stem.replace("_crop", "")

    def save(self) -> None:
        self.store["folder"] = str(self.folder)
        self.store["n_images"] = len(self.paths)
        self.store["n_labeled"] = sum(
            1 for v in self.store["frames"].values() if v.get("u_png") is not None
        )
        self.labels_path.write_text(json.dumps(self.store, indent=2), encoding="utf-8")

    def step(self, delta: int) -> None:
        self.index = (self.index + delta) % len(self.paths)
        self.show()

    def clear_current(self) -> None:
        self.store["frames"].pop(self.stem(), None)
        self.save()
        self.show()

    def on_click(self, event) -> None:
        if self.base_w < 1 or self.base_h < 1:
            return
        u_png = (event.x + 0.5) / self.zoom
        v_png = (event.y + 0.5) / self.zoom
        u_png = min(max(u_png, 0.0), self.base_w - 1e-6)
        v_png = min(max(v_png, 0.0), self.base_h - 1e-6)
        meta = self.by_stem.get(self.stem()) or {}
        self.store["frames"][self.stem()] = {
            "png": self.paths[self.index].name,
            "u_png": u_png,
            "v_png": v_png,
            "u_bayer": u_png * BAYER_PER_PNG,
            "v_bayer": v_png * BAYER_PER_PNG,
            "lock_u_bayer": meta.get("lock_u"),
            "lock_v_bayer": meta.get("lock_v"),
        }
        self.save()
        nxt = self.index + 1
        if nxt < len(self.paths):
            self.index = nxt
        self.show()

    def _compose(self) -> Image.Image:
        src = Image.open(self.paths[self.index]).convert("RGB")
        self.base_w, self.base_h = src.size
        vis = src.resize(
            (self.base_w * self.zoom, self.base_h * self.zoom), Image.Resampling.NEAREST
        )
        draw = ImageDraw.Draw(vis)
        meta = self.by_stem.get(self.stem()) or {}
        lu = meta.get("lock_u")
        lv = meta.get("lock_v")
        if lu is not None and lv is not None:
            self._cross(
                draw,
                float(lu) / BAYER_PER_PNG * self.zoom,
                float(lv) / BAYER_PER_PNG * self.zoom,
                10,
                (255, 140, 0),
            )
        lab = self.store["frames"].get(self.stem())
        if lab and lab.get("u_png") is not None:
            self._cross(
                draw,
                float(lab["u_png"]) * self.zoom,
                float(lab["v_png"]) * self.zoom,
                12,
                (255, 255, 0),
            )
        return vis

    @staticmethod
    def _cross(draw: ImageDraw.ImageDraw, x: float, y: float, arm: int, color) -> None:
        x, y = int(round(x)), int(round(y))
        draw.line((x - arm, y, x + arm, y), fill=color, width=1)
        draw.line((x, y - arm, x, y + arm), fill=color, width=1)
        r = 4
        draw.ellipse((x - r, y - r, x + r, y + r), outline=color)

    def show(self) -> None:
        vis = self._compose()
        self.photo = ImageTk.PhotoImage(vis)
        self.canvas.config(width=vis.size[0], height=vis.size[1])
        self.canvas.delete("all")
        self.canvas.create_image(0, 0, anchor="nw", image=self.photo)
        nlab = sum(1 for v in self.store["frames"].values() if v.get("u_png") is not None)
        marked = "labeled" if self.stem() in self.store["frames"] else "unlabeled"
        self.status.set(
            f"{self.stem()}   {self.index + 1}/{len(self.paths)}   "
            f"{nlab} labeled   {marked}   orange=lock  yellow=click"
        )
        self.root.title(f"star click labels — {self.stem()}")

    def run(self) -> None:
        self.root.mainloop()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--folder", type=Path, default=DEFAULT_DIR)
    ap.add_argument("--zoom", type=int, default=6)
    args = ap.parse_args()
    LabelApp(args.folder.resolve(), args.zoom).run()


if __name__ == "__main__":
    main()
