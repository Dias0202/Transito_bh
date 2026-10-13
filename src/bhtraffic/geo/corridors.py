"""Corridor and bounding-box definitions (stdlib only: used by the collector)."""
from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path

from bhtraffic.config import corridors_file

LatLon = tuple[float, float]


@dataclass(frozen=True)
class Corridor:
    id: str
    name: str
    area: str
    regional: str
    path: tuple[LatLon, ...]  # origin, vias..., destination (inbound)

    def directions(self) -> dict[str, tuple[LatLon, ...]]:
        return {"inbound": self.path, "outbound": tuple(reversed(self.path))}


@dataclass(frozen=True)
class BBox:
    id: str
    west: float
    south: float
    east: float
    north: float


def load(path: Path | None = None) -> tuple[list[Corridor], list[BBox]]:
    with open(path or corridors_file(), "rb") as f:
        cfg = tomllib.load(f)
    points = {k: (float(v[0]), float(v[1])) for k, v in cfg["points"].items()}
    corridors = [
        Corridor(
            id=c["id"],
            name=c["name"],
            area=c["area"],
            regional=c["regional"],
            path=tuple(points[p] for p in c["path"]),
        )
        for c in cfg["corridor"]
    ]
    bboxes = [BBox(b["id"], *map(float, b["bbox"])) for b in cfg.get("bbox", [])]
    return corridors, bboxes
