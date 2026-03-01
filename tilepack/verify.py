"""Verify command: scan a TMS folder or archive and report tile statistics."""

import math
import random
import sqlite3
from pathlib import Path

import click

from tilepack.tms_utils import (
    PNG_SIGNATURE,
    collect_zoom_stats,
    detect_scheme,
)


def _fmt_bounds(bounds: tuple) -> str:
    """Format bounds as a readable string with lat/lon labels."""
    min_lon, min_lat, max_lon, max_lat = bounds
    return f"lon [{min_lon:.4f}, {max_lon:.4f}]  lat [{min_lat:.4f}, {max_lat:.4f}]"


def _print_zoom_table(zoom_counts: dict[int, int]) -> None:
    """Print zoom level table with tile counts."""
    minzoom = min(zoom_counts)
    maxzoom = max(zoom_counts)
    total = sum(zoom_counts.values())

    click.echo(f"Zoom range: {minzoom} – {maxzoom}")
    click.echo(f"{'Zoom':>6}  {'Tiles':>10}")
    click.echo(f"{'----':>6}  {'-----':>10}")
    for z in range(minzoom, maxzoom + 1):
        count = zoom_counts.get(z, 0)
        click.echo(f"{z:>6}  {count:>10,}")
    click.echo(f"{'Total':>6}  {total:>10,}")


def _check_tile_format(tile_data: bytes) -> str:
    """Check tile format from header bytes."""
    if tile_data[:8] == PNG_SIGNATURE:
        return "PNG"
    elif tile_data[:2] == b"\xff\xd8":
        return "JPEG"
    elif tile_data[:4] == b"RIFF" and tile_data[8:12] == b"WEBP":
        return "WebP"
    elif tile_data[:2] == b"\x1f\x8b":
        return "gzip (likely MVT)"
    elif tile_data[:2] in (b"\x78\x9c", b"\x78\x01", b"\x78\xda"):
        return "zlib (likely MVT)"
    else:
        return "unknown"


def verify_tms(root: Path) -> None:
    """Verify a TMS/XYZ tile folder."""
    click.echo("Format: TMS folder\n")

    stats = collect_zoom_stats(root)
    if not stats:
        click.echo("No tiles found.", err=True)
        raise SystemExit(1)

    zoom_counts = {z: s.count for z, s in stats.items()}
    _print_zoom_table(zoom_counts)

    # PNG header check on a random sample tile
    click.echo()
    z_pick = random.choice(list(stats.keys()))
    z_dir = root / str(z_pick)
    x_dirs = [d for d in z_dir.iterdir() if d.is_dir()]
    if x_dirs:
        x_dir = random.choice(x_dirs)
        tile_files = [f for f in x_dir.iterdir() if f.is_file() and f.suffix.lower() == ".png"]
        if tile_files:
            tile_path = random.choice(tile_files)
            tile_data = tile_path.read_bytes()
            fmt = _check_tile_format(tile_data)
            rel = tile_path.relative_to(root)
            click.echo(f"Format check: {fmt} (sampled {rel})")
        else:
            click.echo("Format check: no tile files to sample")
    else:
        click.echo("Format check: no tile directories to sample")

    # Scheme detection
    has_xml = (root / "tilemapresource.xml").exists()
    detected, tms_bounds, xyz_bounds = detect_scheme(stats, has_tilemapresource=has_xml)

    click.echo("\nY-axis scheme detection:")
    click.echo(f"  tilemapresource.xml present: {'yes' if has_xml else 'no'}")
    click.echo(f"  If TMS (y=0 at south):  {_fmt_bounds(tms_bounds)}")
    click.echo(f"  If XYZ (y=0 at north):  {_fmt_bounds(xyz_bounds)}")
    click.echo(f"  Detected scheme: {detected.upper()}")


def verify_mbtiles(path: Path) -> None:
    """Verify an MBTiles archive."""
    click.echo("Format: MBTiles\n")

    conn = sqlite3.connect(str(path))
    cursor = conn.cursor()

    # Read metadata
    metadata = {}
    try:
        rows = cursor.execute("SELECT name, value FROM metadata").fetchall()
        metadata = dict(rows)
    except sqlite3.OperationalError:
        click.echo("Warning: Could not read metadata table", err=True)

    # Get tile counts per zoom
    try:
        rows = cursor.execute(
            "SELECT zoom_level, COUNT(*) FROM tiles GROUP BY zoom_level ORDER BY zoom_level"
        ).fetchall()
        zoom_counts = dict(rows)
    except sqlite3.OperationalError:
        click.echo("Error: Could not read tiles table", err=True)
        conn.close()
        raise SystemExit(1)

    if not zoom_counts:
        click.echo("No tiles found.", err=True)
        conn.close()
        raise SystemExit(1)

    _print_zoom_table(zoom_counts)

    # Sample a random tile for format check
    click.echo()
    z_pick = random.choice(list(zoom_counts.keys()))
    row = cursor.execute(
        "SELECT zoom_level, tile_column, tile_row, tile_data FROM tiles "
        "WHERE zoom_level = ? LIMIT 1",
        (z_pick,),
    ).fetchone()
    if row:
        z, x, y, tile_data = row
        fmt = _check_tile_format(tile_data)
        click.echo(f"Format check: {fmt} (sampled {z}/{x}/{y})")
    else:
        click.echo("Format check: no tiles to sample")

    # Display bounds from metadata
    click.echo()
    if "bounds" in metadata:
        try:
            parts = [float(p) for p in metadata["bounds"].split(",")]
            if len(parts) == 4:
                click.echo(f"Bounds: {_fmt_bounds(tuple(parts))}")
            else:
                click.echo(f"Bounds: {metadata['bounds']}")
        except ValueError:
            click.echo(f"Bounds: {metadata['bounds']}")
    else:
        click.echo("Bounds: not specified in metadata")

    click.echo("Scheme: TMS (y=0 at south)")

    conn.close()


def verify_pmtiles(path: Path) -> None:
    """Verify a PMTiles archive."""
    from pmtiles.reader import MmapSource, Reader

    click.echo("Format: PMTiles\n")

    with open(path, "rb") as f:
        source = MmapSource(f)
        reader = Reader(source)
        header = reader.header()

        # Get stats from header
        minzoom = header.get("min_zoom", 0)
        maxzoom = header.get("max_zoom", 0)
        total_tiles = header.get("addressed_tiles_count", 0)

        if total_tiles == 0:
            click.echo("No tiles found.", err=True)
            raise SystemExit(1)

        click.echo(f"Zoom range: {minzoom} – {maxzoom}")
        click.echo(f"Total tiles: {total_tiles:,}")

        # Sample a tile for format check (try center of the archive)
        click.echo()
        center_z = header.get("center_zoom", minzoom)
        # Try to get any tile at center zoom level - sample at center coordinates
        center_lon = header.get("center_lon_e7", 0) / 1e7
        center_lat = header.get("center_lat_e7", 0) / 1e7

        # Convert center lat/lon to tile coordinates
        n = 2**center_z
        center_x = int((center_lon + 180.0) / 360.0 * n)
        lat_rad = math.radians(center_lat)
        center_y = int((1.0 - math.asinh(math.tan(lat_rad)) / math.pi) / 2.0 * n)

        sample_tile = reader.get(center_z, center_x, center_y)
        if sample_tile:
            fmt = _check_tile_format(sample_tile)
            click.echo(f"Format check: {fmt} (sampled {center_z}/{center_x}/{center_y})")
        else:
            # Try tile type from header
            tile_type = header.get("tile_type")
            if tile_type:
                fmt_name = tile_type.name if hasattr(tile_type, "name") else tile_type
                click.echo(f"Tile type: {fmt_name}")
            else:
                click.echo("Format check: could not sample tile")

        # Bounds from header (stored as E7 integers)
        click.echo()
        min_lon = header.get("min_lon_e7", 0) / 1e7
        min_lat = header.get("min_lat_e7", 0) / 1e7
        max_lon = header.get("max_lon_e7", 0) / 1e7
        max_lat = header.get("max_lat_e7", 0) / 1e7
        click.echo(f"Bounds: {_fmt_bounds((min_lon, min_lat, max_lon, max_lat))}")

        click.echo("Scheme: XYZ (y=0 at north)")


def run_verify(input_path: str) -> None:
    """Verify a TMS folder or MBTiles/PMTiles archive."""
    path = Path(input_path).resolve()
    click.echo(f"Scanning: {path}\n")

    # Detect format
    if path.is_dir():
        verify_tms(path)
    elif path.suffix.lower() == ".mbtiles":
        verify_mbtiles(path)
    elif path.suffix.lower() == ".pmtiles":
        verify_pmtiles(path)
    else:
        click.echo(
            "Error: Unsupported format. Expected a directory, .mbtiles, or .pmtiles file.",
            err=True,
        )
        raise SystemExit(1)
