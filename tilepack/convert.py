"""Convert command: TMS folder → MBTiles or PMTiles."""

from __future__ import annotations

import sqlite3
import time
from pathlib import Path

import click

from tilepack.tms_utils import collect_zoom_stats, compute_bounds, iter_tiles


def run_convert(input_root: str, output_file: str) -> None:
    root = Path(input_root).resolve()
    out = Path(output_file).resolve()
    ext = out.suffix.lower()

    if ext == ".mbtiles":
        _convert_mbtiles(root, out)
    elif ext == ".pmtiles":
        _convert_pmtiles(root, out)
    else:
        click.echo(f"Unknown output format: {ext} (expected .mbtiles or .pmtiles)", err=True)
        raise SystemExit(1)


def _convert_mbtiles(root: Path, out: Path) -> None:
    click.echo("Converting TMS folder → MBTiles")
    click.echo(f"  Input:  {root}")
    click.echo(f"  Output: {out}\n")

    t0 = time.perf_counter()

    # Collect stats for metadata
    stats = collect_zoom_stats(root)
    if not stats:
        click.echo("No tiles found.", err=True)
        raise SystemExit(1)

    minzoom = min(stats)
    maxzoom = max(stats)
    bounds = compute_bounds(stats)

    # Create MBTiles database
    if out.exists():
        out.unlink()

    conn = sqlite3.connect(str(out))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("CREATE TABLE metadata (name TEXT, value TEXT)")
    conn.execute(
        "CREATE TABLE tiles ("
        "  zoom_level INTEGER,"
        "  tile_column INTEGER,"
        "  tile_row INTEGER,"
        "  tile_data BLOB"
        ")"
    )
    conn.execute("CREATE UNIQUE INDEX tile_index ON tiles (zoom_level, tile_column, tile_row)")

    # Populate metadata
    bounds_str = f"{bounds[0]:.6f},{bounds[1]:.6f},{bounds[2]:.6f},{bounds[3]:.6f}"
    center_lon = (bounds[0] + bounds[2]) / 2
    center_lat = (bounds[1] + bounds[3]) / 2
    center_zoom = (minzoom + maxzoom) // 2

    meta = {
        "name": root.name,
        "format": "png",
        "bounds": bounds_str,
        "center": f"{center_lon:.6f},{center_lat:.6f},{center_zoom}",
        "minzoom": str(minzoom),
        "maxzoom": str(maxzoom),
        "type": "overlay",
        "version": "1",
        "description": f"Converted from TMS folder: {root.name}",
    }
    conn.executemany("INSERT INTO metadata VALUES (?, ?)", meta.items())

    # Insert tiles in batches
    batch_size = 1000
    batch = []
    inserted = 0

    for z, x, y, tile_path in iter_tiles(root):
        tile_data = tile_path.read_bytes()
        # No Y-flip: MBTiles uses TMS scheme (same as input)
        batch.append((z, x, y, tile_data))

        if len(batch) >= batch_size:
            conn.executemany("INSERT INTO tiles VALUES (?, ?, ?, ?)", batch)
            conn.commit()
            inserted += len(batch)
            batch.clear()

    if batch:
        conn.executemany("INSERT INTO tiles VALUES (?, ?, ?, ?)", batch)
        conn.commit()
        inserted += len(batch)

    conn.close()
    elapsed = time.perf_counter() - t0
    size_mb = out.stat().st_size / (1024 * 1024)

    click.echo("Done.")
    click.echo(f"  Tiles inserted: {inserted:,}")
    click.echo(f"  File size:      {size_mb:.1f} MB")
    click.echo(f"  Duration:       {elapsed:.1f}s")


def _convert_pmtiles(root: Path, out: Path) -> None:
    click.echo("Converting TMS folder → PMTiles")
    click.echo(f"  Input:  {root}")
    click.echo(f"  Output: {out}\n")

    t0 = time.perf_counter()

    from pmtiles.tile import Compression, TileType, zxy_to_tileid

    stats = collect_zoom_stats(root)
    if not stats:
        click.echo("No tiles found.", err=True)
        raise SystemExit(1)

    minzoom = min(stats)
    maxzoom = max(stats)
    bounds = compute_bounds(stats)
    total = sum(s.count for s in stats.values())

    # Build entries: list of (tileid, tile_data)
    # PMTiles uses XYZ internally, so we must flip Y
    def tile_entries():
        for z, x, y_tms, tile_path in iter_tiles(root):
            y_xyz = (2**z - 1) - y_tms
            tile_id = zxy_to_tileid(z, x, y_xyz)
            yield tile_id, tile_path.read_bytes()

    # Sort by tile_id (required by PMTiles writer)
    click.echo("Reading and sorting tiles...")
    entries = sorted(tile_entries(), key=lambda e: e[0])

    # Write PMTiles using the low-level writer
    from pmtiles.writer import Writer as PMTilesWriter

    if out.exists():
        out.unlink()

    with open(out, "wb") as f:
        writer = PMTilesWriter(f)

        for tile_id, tile_data in entries:
            writer.write_tile(tile_id, tile_data)

        writer.finalize(
            header={
                "tile_type": TileType.PNG,
                "min_zoom": minzoom,
                "max_zoom": maxzoom,
                "min_lon_e7": int(bounds[0] * 1e7),
                "min_lat_e7": int(bounds[1] * 1e7),
                "max_lon_e7": int(bounds[2] * 1e7),
                "max_lat_e7": int(bounds[3] * 1e7),
                "tile_compression": Compression.NONE,
            },
            metadata={
                "name": root.name,
                "format": "png",
                "bounds": f"{bounds[0]:.6f},{bounds[1]:.6f},{bounds[2]:.6f},{bounds[3]:.6f}",
                "minzoom": str(minzoom),
                "maxzoom": str(maxzoom),
            },
        )

    elapsed = time.perf_counter() - t0
    size_mb = out.stat().st_size / (1024 * 1024)

    click.echo("Done.")
    click.echo(f"  Tiles written:  {total:,}")
    click.echo(f"  File size:      {size_mb:.1f} MB")
    click.echo(f"  Duration:       {elapsed:.1f}s")
