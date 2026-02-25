#!/usr/bin/env python3
"""
Generate a TileMapService (TMS) tilemapresource.xml for an existing TMS tile directory.

Assumes tile path pattern:
  root/{z}/{x}/{y}.{ext}

Supports ext: png, jpg, jpeg, webp

Writes:
  root/tilemapresource.xml
  root/tilemap.json (optional summary)
"""

from __future__ import annotations

import argparse
import json
import math
import os
import re
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, Optional, Tuple


EXT_RE = re.compile(r"\.(png|jpg|jpeg|webp)$", re.IGNORECASE)


@dataclass
class ZoomStats:
    min_x: int = 10**18
    max_x: int = -10**18
    min_y: int = 10**18
    max_y: int = -10**18
    count: int = 0

    def update(self, x: int, y: int) -> None:
        self.min_x = min(self.min_x, x)
        self.max_x = max(self.max_x, x)
        self.min_y = min(self.min_y, y)
        self.max_y = max(self.max_y, y)
        self.count += 1


def iter_tiles(root: Path) -> Iterable[Tuple[int, int, int, Path]]:
    """
    Yields (z, x, y, filepath) for tiles matching root/z/x/y.ext
    """
    # Traverse only 3 levels deep for speed (z/x/y.ext)
    for z_dir in root.iterdir():
        if not z_dir.is_dir():
            continue
        try:
            z = int(z_dir.name)
        except ValueError:
            continue

        for x_dir in z_dir.iterdir():
            if not x_dir.is_dir():
                continue
            try:
                x = int(x_dir.name)
            except ValueError:
                continue

            for f in x_dir.iterdir():
                if not f.is_file():
                    continue
                if not EXT_RE.search(f.name):
                    continue
                stem = f.stem
                try:
                    y = int(stem)
                except ValueError:
                    continue
                yield z, x, y, f


def tms_global_bounds_from_tile_ranges(
    zoom_stats: Dict[int, ZoomStats]
) -> Tuple[float, float, float, float]:
    """
    Compute a union bounding box in EPSG:4326 using the min/max x/y at each zoom.
    Assumes WebMercator tile scheme with TMS y indexing (origin bottom-left).
    Returns (min_lon, min_lat, max_lon, max_lat).
    """
    def tile2lon(x: float, z: int) -> float:
        return x / (2**z) * 360.0 - 180.0

    def tile2lat(y_tms: float, z: int) -> float:
        # Convert TMS y (origin bottom) to "Google/XYZ y" (origin top) for the mercator formula:
        # y_xyz = (2^z - 1) - y_tms
        y_xyz = (2**z - 1) - y_tms
        n = math.pi - (2.0 * math.pi * y_xyz) / (2**z)
        return math.degrees(math.atan(math.sinh(n)))

    min_lon = 180.0
    min_lat = 90.0
    max_lon = -180.0
    max_lat = -90.0

    for z, st in zoom_stats.items():
        # left edge = x_min
        # right edge = x_max + 1 (tile spans [x, x+1])
        lon_left = tile2lon(st.min_x, z)
        lon_right = tile2lon(st.max_x + 1, z)

        # For TMS y:
        # bottom edge = y_min
        # top edge = y_max + 1
        lat_bottom = tile2lat(st.min_y, z)
        lat_top = tile2lat(st.max_y + 1, z)

        min_lon = min(min_lon, lon_left)
        max_lon = max(max_lon, lon_right)
        min_lat = min(min_lat, lat_bottom, lat_top)
        max_lat = max(max_lat, lat_bottom, lat_top)

    return min_lon, min_lat, max_lon, max_lat


def generate_tilemapresource_xml(
    base_url: str,
    ext: str,
    minzoom: int,
    maxzoom: int,
    bbox4326: Tuple[float, float, float, float],
    title: str = "TMS Tiles",
    description: str = "Generated tilemapresource.xml",
    srs: str = "EPSG:3857",
    tile_size: int = 256,
) -> str:
    """
    Creates a TileMapService tilemapresource.xml string.
    This is the de-facto format consumed by many TMS clients.
    """
    min_lon, min_lat, max_lon, max_lat = bbox4326
    R = 6378137.0

    if srs == "EPSG:4326":
        bb_minx, bb_miny = min_lon, min_lat
        bb_maxx, bb_maxy = max_lon, max_lat
        origin_x, origin_y = -180.0, -90.0
        tilesets_profile = "global-geodetic"
        initial_resolution = 360.0 / tile_size
    else:  # EPSG:3857
        bb_minx = min_lon * math.pi * R / 180.0
        bb_miny = math.log(math.tan(math.pi / 4 + math.radians(min_lat) / 2)) * R
        bb_maxx = max_lon * math.pi * R / 180.0
        bb_maxy = math.log(math.tan(math.pi / 4 + math.radians(max_lat) / 2)) * R
        origin_x, origin_y = -20037508.342789244, -20037508.342789244
        tilesets_profile = "global-mercator"
        initial_resolution = (2 * math.pi * R) / tile_size

    # Compute resolutions per zoom
    tile_sets = []
    for z in range(minzoom, maxzoom + 1):
        res = initial_resolution / (2**z)
        tile_sets.append(
            f'    <TileSet href="{base_url}/{z}" units-per-pixel="{res:.14f}" order="{z}"/>'
        )

    xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<TileMap version="1.0.0" tilemapservice="1.0.0">
  <Title>{title}</Title>
  <Abstract>{description}</Abstract>
  <SRS>{srs}</SRS>
  <BoundingBox minx="{bb_minx:.10f}" miny="{bb_miny:.10f}" maxx="{bb_maxx:.10f}" maxy="{bb_maxy:.10f}"/>
  <Origin x="{origin_x}" y="{origin_y}"/>
  <TileFormat width="{tile_size}" height="{tile_size}" mime-type="image/{'jpeg' if ext in ('jpg','jpeg') else ext.lower()}" extension="{ext.lower()}"/>
  <TileSets profile="{tilesets_profile}">
{os.linesep.join(tile_sets)}
  </TileSets>
</TileMap>
"""
    return xml


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", required=True, help="Root directory containing z/x/y.ext tiles")
    ap.add_argument("--base-url", required=True, help="Public base URL where the root is served, e.g. http://localhost:8000/tiles")
    ap.add_argument("--ext", default=None, help="Force extension (png/jpg/webp). If omitted, inferred from first tile.")
    ap.add_argument("--title", default="TMS Tiles")
    ap.add_argument("--description", default="Generated tilemapresource.xml")
    ap.add_argument("--out", default="tilemapresource.xml", help="Output filename inside root (default tilemapresource.xml)")
    ap.add_argument("--write-summary-json", action="store_true")
    ap.add_argument(
        "--srs",
        default="EPSG:3857",
        choices=["EPSG:3857", "EPSG:4326"],
        help="Spatial reference system for the output XML (default: EPSG:3857)",
    )
    args = ap.parse_args()

    root = Path(args.root).resolve()
    if not root.exists() or not root.is_dir():
        raise SystemExit(f"Root not found or not a directory: {root}")

    zoom_stats: Dict[int, ZoomStats] = defaultdict(ZoomStats)
    inferred_ext: Optional[str] = None

    tile_count = 0
    for z, x, y, f in iter_tiles(root):
        tile_count += 1
        zoom_stats[z].update(x, y)
        if inferred_ext is None:
            inferred_ext = f.suffix.lstrip(".").lower()

    if tile_count == 0:
        raise SystemExit("No tiles found under root/{z}/{x}/{y}.(png|jpg|jpeg|webp)")

    minzoom = min(zoom_stats.keys())
    maxzoom = max(zoom_stats.keys())

    ext = (args.ext or inferred_ext or "png").lower()
    bbox = tms_global_bounds_from_tile_ranges(zoom_stats)

    xml = generate_tilemapresource_xml(
        base_url=args.base_url.rstrip("/"),
        ext=ext,
        minzoom=minzoom,
        maxzoom=maxzoom,
        bbox4326=bbox,
        title=args.title,
        description=args.description,
        srs=args.srs,
    )

    out_path = root / args.out
    out_path.write_text(xml, encoding="utf-8")
    print(f"Wrote: {out_path}")

    if args.write_summary_json:
        summary = {
            "root": str(root),
            "base_url": args.base_url.rstrip("/"),
            "ext": ext,
            "minzoom": minzoom,
            "maxzoom": maxzoom,
            "bbox_epsg4326": {"min_lon": bbox[0], "min_lat": bbox[1], "max_lon": bbox[2], "max_lat": bbox[3]},
            "zooms": {
                str(z): {
                    "min_x": st.min_x, "max_x": st.max_x,
                    "min_y": st.min_y, "max_y": st.max_y,
                    "count": st.count
                }
                for z, st in sorted(zoom_stats.items())
            },
        }
        (root / "tilemap.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
        print(f"Wrote: {root / 'tilemap.json'}")


if __name__ == "__main__":
    main()