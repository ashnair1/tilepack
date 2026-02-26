"""Serve command: expose an MBTiles or PMTiles archive as a TMS and WMTS endpoint."""

from __future__ import annotations

import sqlite3
from collections.abc import Callable
from pathlib import Path

import click
from fastapi import FastAPI, Query, Response

from tilepack.tms_utils import generate_tilemapresource_xml
from tilepack.wmts_utils import generate_wmts_capabilities_xml


def _add_wmts_routes(
    app: FastAPI,
    *,
    wmts_xml: str,
    layer_name: str,
    get_tile_tms: Callable[[int, int, int], bytes | None],
) -> None:
    """Add WMTS endpoints (capabilities, RESTful tiles, KVP) to a FastAPI app.

    ``get_tile_tms`` accepts (z, x, y_tms) and returns tile bytes or None.
    """

    @app.get("/WMTSCapabilities.xml")
    def wmts_capabilities():
        return Response(content=wmts_xml, media_type="application/xml")

    @app.get("/wmts/{layer}/{tilematrixset}/{z}/{row}/{col}.png")
    def wmts_tile_rest(layer: str, tilematrixset: str, z: int, row: int, col: int):
        # WMTS Row = XYZ y (row 0 at north). Convert to TMS y (y 0 at south).
        y_tms = (2**z - 1) - row
        data = get_tile_tms(z, col, y_tms)
        if data is None:
            return Response(status_code=404, content="Tile not found")
        return Response(content=data, media_type="image/png")

    @app.get("/wmts")
    def wmts_kvp(
        Service: str = Query("WMTS"),
        Request: str = Query("GetTile"),
        Layer: str = Query(""),
        TileMatrixSet: str = Query(""),
        TileMatrix: int = Query(0),
        TileRow: int = Query(0),
        TileCol: int = Query(0),
        Format: str = Query("image/png"),
    ):
        if Request == "GetCapabilities":
            return Response(content=wmts_xml, media_type="application/xml")

        # GetTile (default)
        z = TileMatrix
        y_tms = (2**z - 1) - TileRow
        data = get_tile_tms(z, TileCol, y_tms)
        if data is None:
            return Response(status_code=404, content="Tile not found")
        return Response(content=data, media_type="image/png")


def _build_mbtiles_app(archive_path: Path, *, host: str, port: int) -> FastAPI:
    app = FastAPI()
    db_path = str(archive_path)

    # Read metadata once at startup
    conn = sqlite3.connect(db_path)
    meta = dict(conn.execute("SELECT name, value FROM metadata").fetchall())
    conn.close()

    minzoom = int(meta.get("minzoom", "0"))
    maxzoom = int(meta.get("maxzoom", "20"))
    tile_format = meta.get("format", "png")

    bounds_str = meta.get("bounds", "-180,-85,180,85")
    bounds = tuple(float(v) for v in bounds_str.split(","))
    title = meta.get("name", "TMS Tiles")

    # TMS capability document
    xml = generate_tilemapresource_xml(
        minzoom=minzoom,
        maxzoom=maxzoom,
        bounds=bounds,
        tile_format=tile_format,
        title=title,
    )

    @app.get("/tilemapresource.xml")
    def tilemapresource():
        return Response(content=xml, media_type="application/xml")

    def _get_tile_tms(z: int, x: int, y: int) -> bytes | None:
        conn = sqlite3.connect(db_path)
        row = conn.execute(
            "SELECT tile_data FROM tiles WHERE zoom_level=? AND tile_column=? AND tile_row=?",
            (z, x, y),
        ).fetchone()
        conn.close()
        return row[0] if row else None

    @app.get("/{z}/{x}/{y}.png")
    def get_tile(z: int, x: int, y: int):
        data = _get_tile_tms(z, x, y)
        if data is None:
            return Response(status_code=404, content="Tile not found")
        return Response(content=data, media_type="image/png")

    # WMTS
    wmts_xml = generate_wmts_capabilities_xml(
        minzoom=minzoom,
        maxzoom=maxzoom,
        bounds=bounds,
        tile_format=tile_format,
        title=title,
        base_url=f"http://{host}:{port}",
    )
    _add_wmts_routes(app, wmts_xml=wmts_xml, layer_name=title, get_tile_tms=_get_tile_tms)

    return app


def _build_pmtiles_app(archive_path: Path, *, host: str, port: int) -> FastAPI:
    app = FastAPI()

    from pmtiles.reader import MmapSource
    from pmtiles.reader import Reader as PMTilesReader

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
    title = archive_path.stem

    # TMS capability document
    xml = generate_tilemapresource_xml(
        minzoom=minzoom,
        maxzoom=maxzoom,
        bounds=bounds,
        tile_format="png",
        title=title,
    )

    @app.get("/tilemapresource.xml")
    def tilemapresource():
        return Response(content=xml, media_type="application/xml")

    def _get_tile_tms(z: int, x: int, y_tms: int) -> bytes | None:
        # PMTiles stores in XYZ — flip TMS y to XYZ y
        y_xyz = (2**z - 1) - y_tms
        return reader.get(z, x, y_xyz)

    @app.get("/{z}/{x}/{y}.png")
    def get_tile(z: int, x: int, y: int):
        data = _get_tile_tms(z, x, y)
        if data is None:
            return Response(status_code=404, content="Tile not found")
        return Response(content=data, media_type="image/png")

    # WMTS
    wmts_xml = generate_wmts_capabilities_xml(
        minzoom=minzoom,
        maxzoom=maxzoom,
        bounds=bounds,
        tile_format="png",
        title=title,
        base_url=f"http://{host}:{port}",
    )
    _add_wmts_routes(app, wmts_xml=wmts_xml, layer_name=title, get_tile_tms=_get_tile_tms)

    return app


def run_serve(archive_file: str, host: str, port: int) -> None:
    archive_path = Path(archive_file).resolve()
    ext = archive_path.suffix.lower()

    if ext == ".mbtiles":
        app = _build_mbtiles_app(archive_path, host=host, port=port)
    elif ext == ".pmtiles":
        app = _build_pmtiles_app(archive_path, host=host, port=port)
    else:
        click.echo(f"Unknown archive format: {ext}", err=True)
        raise SystemExit(1)

    click.echo(f"Serving {archive_path.name} on http://{host}:{port}")
    click.echo("  TMS:")
    click.echo(f"    tilemapresource.xml → http://{host}:{port}/tilemapresource.xml")
    click.echo(f"    Tiles               → http://{host}:{port}/{{z}}/{{x}}/{{y}}.png")
    click.echo("  WMTS:")
    click.echo(f"    Capabilities        → http://{host}:{port}/WMTSCapabilities.xml")
    click.echo(
        f"    Tiles (REST)        → http://{host}:{port}/wmts/{{Layer}}/{{TileMatrixSet}}/{{z}}/{{row}}/{{col}}.png"
    )
    click.echo(
        f"    Tiles (KVP)         → http://{host}:{port}/wmts?Service=WMTS&Request=GetTile&...\n"
    )

    import uvicorn

    uvicorn.run(app, host=host, port=port, log_level="info")
