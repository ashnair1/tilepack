"""Verify command: scan a TMS folder and report tile statistics."""

import random
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
    return (
        f"lon [{min_lon:.4f}, {max_lon:.4f}]  "
        f"lat [{min_lat:.4f}, {max_lat:.4f}]"
    )


def run_verify(input_root: str) -> None:
    root = Path(input_root).resolve()
    click.echo(f"Scanning: {root}\n")

    stats = collect_zoom_stats(root)
    if not stats:
        click.echo("No tiles found.", err=True)
        raise SystemExit(1)

    minzoom = min(stats)
    maxzoom = max(stats)
    total = sum(s.count for s in stats.values())

    click.echo(f"Zoom range: {minzoom} – {maxzoom}")
    click.echo(f"{'Zoom':>6}  {'Tiles':>10}")
    click.echo(f"{'----':>6}  {'-----':>10}")
    for z in range(minzoom, maxzoom + 1):
        s = stats.get(z)
        click.echo(f"{z:>6}  {s.count if s else 0:>10,}")
    click.echo(f"{'Total':>6}  {total:>10,}")

    # PNG header check on a random sample tile
    click.echo()
    # Pick a random zoom, then a random x dir, then a random tile file
    z_pick = random.choice(list(stats.keys()))
    z_dir = root / str(z_pick)
    x_dirs = [d for d in z_dir.iterdir() if d.is_dir()]
    if x_dirs:
        x_dir = random.choice(x_dirs)
        tile_files = [f for f in x_dir.iterdir() if f.is_file() and f.suffix.lower() == ".png"]
        if tile_files:
            tile_path = random.choice(tile_files)
            header = tile_path.read_bytes()[:8]
            is_png = header == PNG_SIGNATURE
            rel = tile_path.relative_to(root)
            click.echo(f"Format check: {'PNG ✓' if is_png else 'NOT PNG ✗'} (sampled {rel})")
        else:
            click.echo("Format check: no tile files to sample")
    else:
        click.echo("Format check: no tile directories to sample")

    # Scheme detection
    has_xml = (root / "tilemapresource.xml").exists()
    detected, tms_bounds, xyz_bounds = detect_scheme(stats, has_tilemapresource=has_xml)

    click.echo(f"\nY-axis scheme detection:")
    click.echo(f"  tilemapresource.xml present: {'yes' if has_xml else 'no'}")
    click.echo(f"  If TMS (y=0 at south):  {_fmt_bounds(tms_bounds)}")
    click.echo(f"  If XYZ (y=0 at north):  {_fmt_bounds(xyz_bounds)}")
    click.echo(f"  Detected scheme: {detected.upper()}")
