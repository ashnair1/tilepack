"""Shared utilities for TMS tile iteration, bounds computation, and XML generation."""

from __future__ import annotations

import math
import re
from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path

PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
EXT_RE = re.compile(r"\.(png|jpg|jpeg|webp)$", re.IGNORECASE)


@dataclass
class ZoomStats:
    min_x: int = field(default=10**18)
    max_x: int = field(default=-(10**18))
    min_y: int = field(default=10**18)
    max_y: int = field(default=-(10**18))
    count: int = 0

    def update(self, x: int, y: int) -> None:
        self.min_x = min(self.min_x, x)
        self.max_x = max(self.max_x, x)
        self.min_y = min(self.min_y, y)
        self.max_y = max(self.max_y, y)
        self.count += 1


def iter_tiles(root: Path) -> Iterable[tuple[int, int, int, Path]]:
    """Yield (z, x, y, filepath) for tiles matching root/z/x/y.ext."""
    for z_dir in sorted(root.iterdir()):
        if not z_dir.is_dir():
            continue
        try:
            z = int(z_dir.name)
        except ValueError:
            continue

        for x_dir in sorted(z_dir.iterdir()):
            if not x_dir.is_dir():
                continue
            try:
                x = int(x_dir.name)
            except ValueError:
                continue

            for f in x_dir.iterdir():
                if not f.is_file() or not EXT_RE.search(f.name):
                    continue
                try:
                    y = int(f.stem)
                except ValueError:
                    continue
                yield z, x, y, f


def collect_zoom_stats(root: Path) -> dict[int, ZoomStats]:
    """Scan a TMS folder and return per-zoom statistics."""
    stats: dict[int, ZoomStats] = defaultdict(ZoomStats)
    for z, x, y, _ in iter_tiles(root):
        stats[z].update(x, y)
    return dict(stats)


def _tile2lon(x: float, z: int) -> float:
    return x / (2**z) * 360.0 - 180.0


def _tile2lat_xyz(y_xyz: float, z: int) -> float:
    """Convert XYZ y coordinate to latitude. In XYZ, y=0 is at the north pole."""
    n = math.pi - (2.0 * math.pi * y_xyz) / (2**z)
    return math.degrees(math.atan(math.sinh(n)))


def _compute_bounds_as_scheme(
    zoom_stats: dict[int, ZoomStats], scheme: str
) -> tuple[float, float, float, float]:
    """Compute bounds assuming the Y values follow the given scheme ('tms' or 'xyz').

    Returns (min_lon, min_lat, max_lon, max_lat).
    """
    min_lon, min_lat = 180.0, 90.0
    max_lon, max_lat = -180.0, -90.0

    for z, st in zoom_stats.items():
        lon_left = _tile2lon(st.min_x, z)
        lon_right = _tile2lon(st.max_x + 1, z)

        if scheme == "tms":
            # TMS: y=0 at bottom (south). Convert to XYZ for the lat formula.
            y_xyz_top = (2**z - 1) - (st.max_y + 1)  # top edge
            y_xyz_bottom = (2**z - 1) - st.min_y  # bottom edge
        else:
            # XYZ: y values are already XYZ
            y_xyz_top = st.min_y  # top edge (smaller y = further north)
            y_xyz_bottom = st.max_y + 1  # bottom edge

        lat_top = _tile2lat_xyz(max(y_xyz_top, 0), z)
        lat_bottom = _tile2lat_xyz(min(y_xyz_bottom, 2**z), z)

        min_lon = min(min_lon, lon_left)
        max_lon = max(max_lon, lon_right)
        min_lat = min(min_lat, lat_bottom, lat_top)
        max_lat = max(max_lat, lat_bottom, lat_top)

    return min_lon, min_lat, max_lon, max_lat


def compute_bounds(
    zoom_stats: dict[int, ZoomStats],
    scheme: str = "tms",
) -> tuple[float, float, float, float]:
    """Compute a union bounding box in EPSG:4326 from tile ranges.

    ``scheme`` indicates how to interpret Y values: ``"tms"`` (y=0 at south)
    or ``"xyz"`` (y=0 at north).  Returns (min_lon, min_lat, max_lon, max_lat).
    """
    return _compute_bounds_as_scheme(zoom_stats, scheme)


def detect_scheme(
    zoom_stats: dict[int, ZoomStats],
    has_tilemapresource: bool = False,
) -> tuple[str, tuple[float, float, float, float], tuple[float, float, float, float]]:
    """Detect whether tile Y coordinates follow TMS or XYZ convention.

    Uses two signals:
    1. Presence of tilemapresource.xml in the folder (strong TMS indicator).
    2. Y-coordinate position relative to the midpoint of the tile grid.
       - TMS: y=0 at south, so northern-hemisphere data has y > 2^(z-1).
       - XYZ: y=0 at north, so northern-hemisphere data has y < 2^(z-1).
       Interpreting with the wrong scheme mirrors latitude across the equator.

    Returns (detected_scheme, tms_bounds, xyz_bounds).
    """
    tms_bounds = _compute_bounds_as_scheme(zoom_stats, "tms")
    xyz_bounds = _compute_bounds_as_scheme(zoom_stats, "xyz")

    # If tilemapresource.xml exists, it's definitively TMS
    if has_tilemapresource:
        return "tms", tms_bounds, xyz_bounds

    # Heuristic: check if y values sit above or below the midpoint of the grid.
    # Use the highest zoom level for best precision.
    z = max(zoom_stats)
    st = zoom_stats[z]
    midpoint = 2 ** (z - 1)  # half of 2^z
    y_center = (st.min_y + st.max_y) / 2

    # If y_center > midpoint, the data is in the northern hemisphere under TMS
    # (and southern under XYZ). If y_center < midpoint, it's the reverse.
    # For datasets on the equator (y_center ≈ midpoint), both schemes give
    # nearly identical results, so the choice doesn't matter much.
    #
    # We can't know "ground truth" without external info, but we can report
    # which interpretation places the data where, and make a best guess:
    # For y_center > midpoint: likely TMS (data in northern hemisphere)
    # For y_center < midpoint: likely XYZ (data in northern hemisphere)
    # This works because most populated landmass is in the northern hemisphere.
    if y_center > midpoint:
        return "tms", tms_bounds, xyz_bounds
    elif y_center < midpoint:
        return "xyz", tms_bounds, xyz_bounds
    else:
        # Equatorial — default to TMS
        return "tms", tms_bounds, xyz_bounds


def generate_tilemapresource_xml(
    minzoom: int,
    maxzoom: int,
    bounds: tuple[float, float, float, float],
    tile_format: str = "png",
    title: str = "TMS Tiles",
    tile_size: int = 256,
    srs: str = "EPSG:3857",
) -> str:
    """Generate a TMS tilemapresource.xml string."""
    min_lon, min_lat, max_lon, max_lat = bounds
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

    tile_sets = []
    for z in range(minzoom, maxzoom + 1):
        res = initial_resolution / (2**z)
        tile_sets.append(f'    <TileSet href="{z}" units-per-pixel="{res:.14f}" order="{z}"/>')

    mime = "image/jpeg" if tile_format in ("jpg", "jpeg") else f"image/{tile_format}"

    return f"""<?xml version="1.0" encoding="UTF-8"?>
<TileMap version="1.0.0" tilemapservice="1.0.0">
  <Title>{title}</Title>
  <Abstract/>
  <SRS>{srs}</SRS>
  <BoundingBox minx="{bb_minx:.10f}" miny="{bb_miny:.10f}" maxx="{bb_maxx:.10f}" maxy="{bb_maxy:.10f}"/>
  <Origin x="{origin_x}" y="{origin_y}"/>
  <TileFormat width="{tile_size}" height="{tile_size}" mime-type="{mime}" extension="{tile_format}"/>
  <TileSets profile="{tilesets_profile}">
{chr(10).join(tile_sets)}
  </TileSets>
</TileMap>
"""
