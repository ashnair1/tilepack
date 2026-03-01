# tilepack

Pack raster tile folders (TMS or XYZ) into single-file archives (MBTiles / PMTiles) and serve them as TMS and WMTS endpoints over HTTP.

## Why

Raster tile folders contain thousands of small PNG files in deeply nested `z/x/y` directories. This makes them slow to copy, hard to manage, and fragile to transfer. Tilepack solves this by packing tiles into a single archive file while still exposing standard TMS and WMTS HTTP endpoints that clients like QGIS and CesiumForUnreal can consume directly.

## Installation

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

## Quick Start

```bash
# Verify a tile folder
tilepack verify ./path/to/tiles

# Convert to archive
tilepack convert ./path/to/tiles output.mbtiles

# Serve as TMS + WMTS endpoint
tilepack serve output.mbtiles --port 8000
```

## MBTiles vs PMTiles

| | MBTiles | PMTiles |
|---|---------|---------|
| Format | SQLite database | Cloud-optimised archive (Hilbert-curve index) |
| File count | 1 | 1 |
| Needs a tile server | Yes | No (supports HTTP range requests) |
| Best for | Local / on-prem serving | Cloud storage (S3, Azure Blob, GCS) |

**Use MBTiles** for local or on-prem serving (e.g. feeding CesiumForUnreal on the same machine or network).

**Use PMTiles** if you plan to host tiles in cloud storage. PMTiles can be served directly from a bucket via HTTP range requests with no tile server needed.

**Either format** works identically when served through `tilepack serve`.
