# Usage

## Verify tiles

Scan a tile folder or archive and report zoom levels, tile counts, format, and bounds.

```bash
tilepack verify ./path/to/tiles      # TMS/XYZ folder
tilepack verify output.mbtiles       # MBTiles archive
tilepack verify output.pmtiles       # PMTiles archive
```

Example output:

```
Scanning: /path/to/tiles

Format: MBTiles

Zoom range: 10 – 13
  Zoom       Tiles
  ----       -----
    10           4
    11           9
    12          25
    13          90
 Total         128

Format check: PNG (sampled 12/2681/2329)
Bounds: lon [55.5469, 56.2500]  lat [23.8858, 24.5271]
Scheme: TMS (y=0 at south)
```

## Convert to archive

The output format is inferred from the file extension. The input tile scheme (TMS or XYZ) is auto-detected, or can be specified explicitly.

```bash
# Auto-detect input scheme
tilepack convert ./path/to/tiles output.mbtiles
tilepack convert ./path/to/tiles output.pmtiles

# Specify input scheme explicitly
tilepack convert ./path/to/tiles output.mbtiles --scheme xyz
```

## Serve as TMS + WMTS endpoint

Start a local HTTP server exposing both TMS and OGC WMTS 1.0.0 endpoints from an archive file.

```bash
tilepack serve output.mbtiles --port 8000
tilepack serve output.pmtiles --port 8000
```

### TMS endpoints

- `http://localhost:8000/tilemapresource.xml` — GetCapabilities
- `http://localhost:8000/{z}/{x}/{y}.png` — Tile requests

### WMTS endpoints

- `http://localhost:8000/WMTSCapabilities.xml` — GetCapabilities
- `http://localhost:8000/wmts/{Layer}/{TileMatrixSet}/{z}/{row}/{col}.png` — RESTful tiles
- `http://localhost:8000/wmts?Service=WMTS&Request=GetTile&...` — KVP tiles

### Loading in QGIS

**Layer > Add WMS/WMTS Layer > New**, set URL to `http://localhost:8000/WMTSCapabilities.xml`, then Connect and Add.

## Validate correctness

Randomly sample tiles from the original folder, fetch them from the running server, and verify byte-exact matches.

```bash
# Start the server in one terminal, then in another:
tilepack selftest ./path/to/tiles --base-url http://127.0.0.1:8000 --samples 200
```
