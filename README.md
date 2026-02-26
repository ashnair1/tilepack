# tilepack

Convert TMS tile folders into single-file archives (MBTiles / PMTiles) and serve them as TMS and WMTS endpoints over HTTP.

## Problem

TMS tile folders contain thousands of small files in deeply nested directories. This makes them slow to copy, hard to manage, and fragile to transfer. Tilepack solves this by packing tiles into a single archive file while still exposing standard TMS and WMTS HTTP endpoints that clients like CesiumForUnreal and QGIS can consume.

## Setup

Requires Python 3.11+ (uses the `tms` conda environment).

```bash
conda activate tms
pip install -e .
```

## Usage

### Verify a TMS folder

Scan a tile folder and report zoom levels, tile counts, format, and detected Y-axis scheme (TMS vs XYZ).

```bash
tilepack verify ./path/to/tiles
```

### Convert to archive

Format is inferred from the output file extension.

```bash
tilepack convert ./path/to/tiles output.mbtiles
tilepack convert ./path/to/tiles output.pmtiles
```

### Serve as TMS + WMTS endpoint

Starts a local HTTP server exposing both TMS and OGC WMTS 1.0.0 endpoints.

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

To load in QGIS: **Layer → Add WMS/WMTS Layer → New**, set URL to `http://localhost:8000/WMTSCapabilities.xml`, then Connect and Add.

### Validate correctness

Randomly samples tiles from the original folder, fetches them from the running server, and checks for byte-exact matches.

```bash
# Start the server in one terminal, then in another:
tilepack selftest ./path/to/tiles --base-url http://127.0.0.1:8000 --samples 200
```

## Format Comparison

| Metric | TMS Folder | MBTiles | PMTiles |
|--------|-----------|---------|---------|
| File count | N tiles + dirs | 1 | 1 |
| Cloud-servable (no server) | No | No | Yes |

## Which format should I use?

**Use MBTiles** if you are serving tiles locally or on-prem (e.g. feeding CesiumForUnreal on the same machine or network). It's simpler — just a SQLite file, no coordinate flipping, and slightly faster tile lookups. This is the recommended default.

**Use PMTiles** if you plan to host tiles in cloud storage (S3, Azure Blob, GCS). PMTiles can be served directly from a storage bucket via HTTP range requests with no tile server process needed. However, TMS clients like CesiumForUnreal cannot consume PMTiles directly — they still need a server translating it to TMS endpoints. PMTiles is most useful when paired with a PMTiles-aware frontend (e.g. MapLibre, Leaflet with the pmtiles plugin).

**Either format** works identically when served through `tilepack serve` — clients see the same TMS and WMTS endpoints regardless of the backing archive.

## Architecture

- **MBTiles** — SQLite database. Same TMS Y-axis as input, no coordinate flipping needed. Requires a tile server.
- **PMTiles** — Cloud-optimised archive with Hilbert-curve indexing. Uses XYZ Y-axis internally, so coordinates are flipped during conversion and serving. Can be served directly from cloud storage (S3, Azure Blob) via HTTP range requests.
