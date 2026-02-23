# TMS Packager

Convert TMS tile folders into single-file archives (MBTiles / PMTiles) and serve them as TMS endpoints over HTTP.

## Problem

TMS tile folders contain thousands of small files in deeply nested directories. This makes them slow to copy, hard to manage, and fragile to transfer. TMS Packager solves this by packing tiles into a single archive file while still exposing a standard TMS HTTP endpoint that clients like CesiumForUnreal can consume unchanged.

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
tms_packager verify ./path/to/tiles
```

### Convert to archive

Format is inferred from the output file extension.

```bash
tms_packager convert ./path/to/tiles output.mbtiles
tms_packager convert ./path/to/tiles output.pmtiles
```

### Serve as TMS endpoint

Starts a local HTTP server exposing `tilemapresource.xml` and `/{z}/{x}/{y}.png`.

```bash
tms_packager serve output.mbtiles --port 8000
tms_packager serve output.pmtiles --port 8000
```

### Validate correctness

Randomly samples tiles from the original folder, fetches them from the running server, and checks for byte-exact matches.

```bash
# Start the server in one terminal, then in another:
tms_packager selftest ./path/to/tiles --base-url http://127.0.0.1:8000 --samples 200
```

## Format Comparison

| Metric | TMS Folder | MBTiles | PMTiles |
|--------|-----------|---------|---------|
| File count | N tiles + dirs | 1 | 1 |
| Cloud-servable (no server) | No | No | Yes |

## Architecture

- **MBTiles** — SQLite database. Same TMS Y-axis as input, no coordinate flipping needed. Requires a tile server.
- **PMTiles** — Cloud-optimised archive with Hilbert-curve indexing. Uses XYZ Y-axis internally, so coordinates are flipped during conversion and serving. Can be served directly from cloud storage (S3, Azure Blob) via HTTP range requests.
