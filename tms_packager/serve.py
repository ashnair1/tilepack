"""Serve command: expose an MBTiles or PMTiles archive as a TMS endpoint."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import click
from fastapi import FastAPI, Response

from tms_packager.tms_utils import generate_tilemapresource_xml


def _build_mbtiles_app(archive_path: Path) -> FastAPI:
    app = FastAPI()
    db_path = str(archive_path)

    # Read metadata once at startup
    conn = sqlite3.connect(db_path)
    meta = dict(conn.execute("SELECT name, value FROM metadata").fetchall())
    conn.close()

    minzoom = int(meta.get("minzoom", "0"))
    maxzoom = int(meta.get("maxzoom", "20"))
    tile_format = meta.get("format", "png")

    # Parse bounds
    bounds_str = meta.get("bounds", "-180,-85,180,85")
    bounds = tuple(float(v) for v in bounds_str.split(","))

    xml = generate_tilemapresource_xml(
        minzoom=minzoom,
        maxzoom=maxzoom,
        bounds=bounds,
        tile_format=tile_format,
        title=meta.get("name", "TMS Tiles"),
    )

    @app.get("/tilemapresource.xml")
    def tilemapresource():
        return Response(content=xml, media_type="application/xml")

    @app.get("/{z}/{x}/{y}.png")
    def get_tile(z: int, x: int, y: int):
        # MBTiles stores in TMS scheme — same as incoming request, no flip needed
        conn = sqlite3.connect(db_path)
        row = conn.execute(
            "SELECT tile_data FROM tiles WHERE zoom_level=? AND tile_column=? AND tile_row=?",
            (z, x, y),
        ).fetchone()
        conn.close()

        if row is None:
            return Response(status_code=404, content="Tile not found")

        return Response(content=row[0], media_type="image/png")

    return app


def _build_pmtiles_app(archive_path: Path) -> FastAPI:
    app = FastAPI()

    from pmtiles.reader import MmapSource, Reader as PMTilesReader
    from pmtiles.tile import zxy_to_tileid

    source = MmapSource(open(archive_path, "rb"))
    reader = PMTilesReader(source)
    header = reader.header()

    minzoom = header.get("min_zoom", 0)
    maxzoom = header.get("max_zoom", 20)
    bounds = (
        header.get("min_lon_e7", -1800000000) / 1e7,
        header.get("min_lat_e7", -850000000) / 1e7,
        header.get("max_lon_e7", 1800000000) / 1e7,
        header.get("max_lat_e7", 850000000) / 1e7,
    )

    xml = generate_tilemapresource_xml(
        minzoom=minzoom,
        maxzoom=maxzoom,
        bounds=bounds,
        tile_format="png",
        title=archive_path.stem,
    )

    @app.get("/tilemapresource.xml")
    def tilemapresource():
        return Response(content=xml, media_type="application/xml")

    @app.get("/{z}/{x}/{y}.png")
    def get_tile(z: int, x: int, y: int):
        # PMTiles stores in XYZ, incoming request is TMS — flip Y
        y_xyz = (2**z - 1) - y
        tile_data = reader.get(z, x, y_xyz)

        if tile_data is None:
            return Response(status_code=404, content="Tile not found")

        return Response(content=tile_data, media_type="image/png")

    return app


def run_serve(archive_file: str, host: str, port: int) -> None:
    archive_path = Path(archive_file).resolve()
    ext = archive_path.suffix.lower()

    if ext == ".mbtiles":
        app = _build_mbtiles_app(archive_path)
    elif ext == ".pmtiles":
        app = _build_pmtiles_app(archive_path)
    else:
        click.echo(f"Unknown archive format: {ext}", err=True)
        raise SystemExit(1)

    click.echo(f"Serving {archive_path.name} as TMS on http://{host}:{port}")
    click.echo(f"  tilemapresource.xml → http://{host}:{port}/tilemapresource.xml")
    click.echo(f"  Tiles               → http://{host}:{port}/{{z}}/{{x}}/{{y}}.png\n")

    import uvicorn

    uvicorn.run(app, host=host, port=port, log_level="info")
