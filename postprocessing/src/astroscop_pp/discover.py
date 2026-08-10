"""Discover and pair Bayer .npy frames with JSON sidecars."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

_BAYER_RE = re.compile(r"^(?P<stem>.+)_bayer\.npy$", re.IGNORECASE)


@dataclass(frozen=True)
class FramePair:
    """One science frame: Bayer array path + metadata path + loaded meta."""

    npy_path: Path
    meta_path: Path
    meta: dict[str, Any]
    sequence: int
    stem: str


@dataclass(frozen=True)
class DiscoverResult:
    """Paired frames plus orphan .npy paths skipped for missing sidecars."""

    frames: list[FramePair]
    skipped: list[str] = field(default_factory=list)


def _load_meta(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError(f"metadata is not an object: {path}")
    return data


def _sequence_from(meta: dict[str, Any], stem: str) -> int:
    seq = meta.get("sequence")
    if seq is not None:
        return int(seq)
    m = re.search(r"(\d+)$", stem)
    if m:
        return int(m.group(1))
    raise ValueError(f"cannot determine sequence for stem {stem!r}")


def discover_frames(input_dir: Path, *, recursive: bool = True) -> DiscoverResult:
    """
    Find ``*_bayer.npy`` files with matching ``*_meta.json`` sidecars.

    When ``recursive`` is true, search one level of subdirectories as well
    (e.g. ``sat1/bigs/``). Deeper nesting is ignored.

    Orphan ``.npy`` files without a sidecar are listed in ``skipped`` and
    omitted from ``frames``.
    """
    root = Path(input_dir)
    if not root.is_dir():
        raise FileNotFoundError(f"input directory not found: {root}")

    search_dirs = [root]
    if recursive:
        search_dirs.extend(sorted(p for p in root.iterdir() if p.is_dir()))

    pairs: list[FramePair] = []
    skipped: list[str] = []
    seen: set[Path] = set()

    for directory in search_dirs:
        for npy_path in sorted(directory.glob("*_bayer.npy")):
            resolved = npy_path.resolve()
            if resolved in seen:
                continue
            match = _BAYER_RE.match(npy_path.name)
            if not match:
                continue
            stem = match.group("stem")
            meta_path = npy_path.with_name(f"{stem}_meta.json")
            if not meta_path.is_file():
                skipped.append(
                    f"missing metadata sidecar for {npy_path}: expected {meta_path.name}"
                )
                continue
            meta = _load_meta(meta_path)
            sequence = _sequence_from(meta, stem)
            pairs.append(
                FramePair(
                    npy_path=npy_path,
                    meta_path=meta_path,
                    meta=meta,
                    sequence=sequence,
                    stem=stem,
                )
            )
            seen.add(resolved)

    pairs.sort(key=lambda p: (p.sequence, str(p.npy_path)))
    return DiscoverResult(frames=pairs, skipped=skipped)
