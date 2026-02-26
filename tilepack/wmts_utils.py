"""Generate OGC WMTS GetCapabilities XML documents."""

from __future__ import annotations

import math
from xml.sax.saxutils import escape

# OGC WMTS constants for GoogleMapsCompatible tile matrix set
_R = 6378137.0  # WGS-84 Earth radius in metres
_TOP_LEFT_CORNER = f"-{math.pi * _R:.10f} {math.pi * _R:.10f}"
# OGC defines 1 pixel = 0.28 mm for scale denominator calculation
_PIXEL_SIZE_M = 0.00028
# Scale denominator at zoom 0 for 256px tiles in EPSG:3857
_SCALE_DENOM_Z0 = (2 * math.pi * _R) / (256 * _PIXEL_SIZE_M)


def generate_wmts_capabilities_xml(
    *,
    minzoom: int,
    maxzoom: int,
    bounds: tuple[float, float, float, float],
    tile_format: str = "png",
    title: str = "WMTS Tiles",
    tile_size: int = 256,
    base_url: str = "http://localhost:8000",
) -> str:
    """Generate an OGC WMTS 1.0.0 GetCapabilities XML string.

    Parameters
    ----------
    minzoom, maxzoom : int
        Zoom level range.
    bounds : tuple
        (min_lon, min_lat, max_lon, max_lat) in EPSG:4326.
    tile_format : str
        Tile image format (png, jpg, webp).
    title : str
        Layer/service title.
    tile_size : int
        Tile width/height in pixels (default 256).
    base_url : str
        Server base URL used for ResourceURL templates.
    """
    min_lon, min_lat, max_lon, max_lat = bounds
    layer_id = escape(title)
    tms_id = "GoogleMapsCompatible"
    mime = "image/jpeg" if tile_format in ("jpg", "jpeg") else f"image/{tile_format}"

    # Build TileMatrix entries for each zoom level
    tile_matrices = []
    for z in range(minzoom, maxzoom + 1):
        scale_denom = _SCALE_DENOM_Z0 / (2**z)
        matrix_size = 2**z
        tile_matrices.append(
            f"""      <TileMatrix>
        <ows:Identifier>{z}</ows:Identifier>
        <ScaleDenominator>{scale_denom:.10f}</ScaleDenominator>
        <TopLeftCorner>{_TOP_LEFT_CORNER}</TopLeftCorner>
        <TileWidth>{tile_size}</TileWidth>
        <TileHeight>{tile_size}</TileHeight>
        <MatrixWidth>{matrix_size}</MatrixWidth>
        <MatrixHeight>{matrix_size}</MatrixHeight>
      </TileMatrix>"""
        )

    # Bounding box in EPSG:3857 (metres)
    bb_minx = min_lon * math.pi * _R / 180.0
    bb_miny = math.log(math.tan(math.pi / 4 + math.radians(min_lat) / 2)) * _R
    bb_maxx = max_lon * math.pi * _R / 180.0
    bb_maxy = math.log(math.tan(math.pi / 4 + math.radians(max_lat) / 2)) * _R

    resource_url = f"{base_url}/wmts/{title}/{tms_id}/{{TileMatrix}}/{{TileRow}}/{{TileCol}}.png"

    return f"""<?xml version="1.0" encoding="UTF-8"?>
<Capabilities xmlns="http://www.opengis.net/wmts/1.0"
              xmlns:ows="http://www.opengis.net/ows/1.1"
              xmlns:xlink="http://www.w3.org/1999/xlink"
              version="1.0.0">
  <ows:ServiceIdentification>
    <ows:Title>{layer_id}</ows:Title>
    <ows:ServiceType>OGC WMTS</ows:ServiceType>
    <ows:ServiceTypeVersion>1.0.0</ows:ServiceTypeVersion>
  </ows:ServiceIdentification>
  <Contents>
    <Layer>
      <ows:Title>{layer_id}</ows:Title>
      <ows:Identifier>{layer_id}</ows:Identifier>
      <ows:WGS84BoundingBox>
        <ows:LowerCorner>{min_lon:.10f} {min_lat:.10f}</ows:LowerCorner>
        <ows:UpperCorner>{max_lon:.10f} {max_lat:.10f}</ows:UpperCorner>
      </ows:WGS84BoundingBox>
      <Style isDefault="true">
        <ows:Identifier>default</ows:Identifier>
      </Style>
      <Format>{mime}</Format>
      <TileMatrixSetLink>
        <TileMatrixSet>{tms_id}</TileMatrixSet>
        <TileMatrixSetLimits>
{_tile_matrix_set_limits(minzoom, maxzoom, bounds)}
        </TileMatrixSetLimits>
      </TileMatrixSetLink>
      <ResourceURL format="{mime}" resourceType="tile"
                   template="{escape(resource_url)}"/>
    </Layer>
    <TileMatrixSet>
      <ows:Identifier>{tms_id}</ows:Identifier>
      <ows:SupportedCRS>urn:ogc:def:crs:EPSG::3857</ows:SupportedCRS>
      <ows:BoundingBox crs="urn:ogc:def:crs:EPSG::3857">
        <ows:LowerCorner>{bb_minx:.10f} {bb_miny:.10f}</ows:LowerCorner>
        <ows:UpperCorner>{bb_maxx:.10f} {bb_maxy:.10f}</ows:UpperCorner>
      </ows:BoundingBox>
{chr(10).join(tile_matrices)}
    </TileMatrixSet>
  </Contents>
</Capabilities>
"""


def _lat_to_wmts_row(lat_deg: float, n: int) -> int:
    """Convert latitude (degrees) to WMTS tile row at grid size n."""
    lat_rad = math.radians(lat_deg)
    frac = (1.0 - math.log(math.tan(lat_rad) + 1.0 / math.cos(lat_rad)) / math.pi) / 2.0
    return int(math.floor(frac * n))


def _tile_matrix_set_limits(
    minzoom: int,
    maxzoom: int,
    bounds: tuple[float, float, float, float],
) -> str:
    """Compute TileMatrixSetLimits for the given bounds at each zoom level.

    Returns XML fragment with min/max row/col for each TileMatrix.
    """
    min_lon, min_lat, max_lon, max_lat = bounds
    lines = []
    for z in range(minzoom, maxzoom + 1):
        n = 2**z
        # Column range (same as x in both TMS and XYZ)
        min_col = int(math.floor((min_lon + 180.0) / 360.0 * n))
        max_col = int(math.floor((max_lon + 180.0) / 360.0 * n))
        max_col = min(max_col, n - 1)

        # Row range (WMTS row = XYZ y, row 0 at north)
        min_row = _lat_to_wmts_row(max_lat, n)
        max_row = _lat_to_wmts_row(min_lat, n)
        min_row = max(min_row, 0)
        max_row = min(max_row, n - 1)

        lines.append(
            f"""          <TileMatrixLimits>
            <TileMatrix>{z}</TileMatrix>
            <MinTileRow>{min_row}</MinTileRow>
            <MaxTileRow>{max_row}</MaxTileRow>
            <MinTileCol>{min_col}</MinTileCol>
            <MaxTileCol>{max_col}</MaxTileCol>
          </TileMatrixLimits>"""
        )
    return "\n".join(lines)
