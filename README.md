# tilepack

[![CI](https://github.com/ashnair1/tilepack/actions/workflows/ci.yml/badge.svg)](https://github.com/ashnair1/tilepack/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/tilepack)](https://pypi.org/project/tilepack/)
[![Python](https://img.shields.io/pypi/pyversions/tilepack)](https://pypi.org/project/tilepack/)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

Pack raster tile folders (TMS or XYZ) into single-file archives (MBTiles / PMTiles) and serve them as TMS and WMTS endpoints over HTTP.

## Why

Raster tile folders contain thousands of small PNG files in deeply nested `z/x/y` directories. This makes them slow to copy, hard to manage, and fragile to transfer. Tilepack solves this by packing tiles into a single archive file while still exposing standard TMS and WMTS HTTP endpoints that clients like QGIS and CesiumForUnreal can consume directly.

## Install

Requires Python 3.11+.

```bash
pip install tilepack
```

For development:

```bash
git clone https://github.com/ashnair1/tilepack.git
cd tilepack
uv sync --group dev
```

## Usage

### Verify tiles

Scan a tile folder or archive and report zoom levels, tile counts, format, and bounds.

```bash
tilepack verify ./path/to/tiles      # TMS/XYZ folder
tilepack verify output.mbtiles       # MBTiles archive
tilepack verify output.pmtiles       # PMTiles archive
```

### Convert to archive

The output format is inferred from the file extension. The input tile scheme (TMS or XYZ) is auto-detected, or can be specified explicitly.

```bash
# Auto-detect input scheme
tilepack convert ./path/to/tiles output.mbtiles
tilepack convert ./path/to/tiles output.pmtiles

# Specify input scheme explicitly
tilepack convert ./path/to/tiles output.mbtiles --scheme xyz
```

### Serve as TMS + WMTS endpoint

Start a local HTTP server exposing both TMS and OGC WMTS 1.0.0 endpoints from an archive file.

```bash
tilepack serve output.mbtiles --port 8000
tilepack serve output.pmtiles --port 8000
```

**TMS endpoints:**
- `http://localhost:8000/tilemapresource.xml`
- `http://localhost:8000/{z}/{x}/{y}.png`

**WMTS endpoints:**
- `http://localhost:8000/WMTSCapabilities.xml` — GetCapabilities
- `http://localhost:8000/wmts/{Layer}/{TileMatrixSet}/{z}/{row}/{col}.png` — RESTful tiles
- `http://localhost:8000/wmts?Service=WMTS&Request=GetTile&...` — KVP tiles

To load in QGIS: **Layer > Add WMS/WMTS Layer > New**, set URL to `http://localhost:8000/WMTSCapabilities.xml`, then Connect and Add.

### Validate correctness

Randomly sample tiles from the original folder, fetch them from the running server, and verify byte-exact matches.

```bash
# Start the server in one terminal, then in another:
tilepack selftest ./path/to/tiles --base-url http://127.0.0.1:8000 --samples 200
```

## MBTiles vs PMTiles

| | MBTiles | PMTiles |
|---|---------|---------|
| Format | SQLite database | Cloud-optimised archive (Hilbert-curve index) |
| File count | 1 | 1 |
| Needs a tile server | Yes | No (supports HTTP range requests) |
| Best for | Local / on-prem serving | Cloud storage (S3, Azure Blob, GCS) |

**Use MBTiles** for local or on-prem serving (e.g. feeding CesiumForUnreal on the same machine or network). It's a SQLite file with fast tile lookups and no coordinate flipping at read time.

**Use PMTiles** if you plan to host tiles in cloud storage. PMTiles can be served directly from a bucket via HTTP range requests with no tile server needed. However, TMS clients like CesiumForUnreal cannot consume PMTiles directly — they still need a server translating to TMS endpoints.

**Either format** works identically when served through `tilepack serve` — clients see the same TMS and WMTS endpoints regardless of the backing archive.

## License

MIT
