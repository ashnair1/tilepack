"""Tests for tilepack.wmts_utils."""

from tilepack.wmts_utils import (
    _tile_matrix_set_limits,
    generate_wmts_capabilities_xml,
)


class TestGenerateWmtsCapabilitiesXml:
    def test_contains_expected_elements(self):
        xml = generate_wmts_capabilities_xml(
            minzoom=0,
            maxzoom=2,
            bounds=(-180, -85, 180, 85),
            title="Test Layer",
            base_url="http://localhost:8000",
        )
        assert "<Capabilities" in xml
        assert "<Contents>" in xml
        assert "<Layer>" in xml
        assert "<TileMatrixSet>" in xml
        assert "GoogleMapsCompatible" in xml
        assert "Test Layer" in xml
        assert "EPSG::3857" in xml
        assert "1.0.0" in xml

    def test_resource_url_template(self):
        xml = generate_wmts_capabilities_xml(
            minzoom=0,
            maxzoom=1,
            bounds=(-10, -10, 10, 10),
            title="Tiles",
            base_url="http://example.com",
        )
        assert "http://example.com/wmts/Tiles/GoogleMapsCompatible" in xml
        assert "ResourceURL" in xml

    def test_tile_matrix_count(self):
        xml = generate_wmts_capabilities_xml(
            minzoom=5,
            maxzoom=8,
            bounds=(-10, -10, 10, 10),
        )
        # Should have zoom levels 5-8, not 4 or 9
        assert "<ows:Identifier>5</ows:Identifier>" in xml
        assert "<ows:Identifier>8</ows:Identifier>" in xml
        assert "<ows:Identifier>4</ows:Identifier>" not in xml
        assert "<ows:Identifier>9</ows:Identifier>" not in xml


class TestTileMatrixSetLimits:
    def test_contains_limits_for_each_zoom(self):
        limits = _tile_matrix_set_limits(minzoom=0, maxzoom=2, bounds=(-10, -10, 10, 10))
        assert limits.count("<TileMatrixLimits>") == 3

    def test_col_range_full_world(self):
        limits = _tile_matrix_set_limits(minzoom=0, maxzoom=0, bounds=(-180, -85, 180, 85))
        assert "<MinTileCol>0</MinTileCol>" in limits
        assert "<MaxTileCol>0</MaxTileCol>" in limits

    def test_row_range_reasonable(self):
        # Northern hemisphere only: rows should be in upper half
        limits = _tile_matrix_set_limits(minzoom=1, maxzoom=1, bounds=(0, 30, 90, 60))
        assert "<MinTileRow>0</MinTileRow>" in limits
        assert "<MaxTileRow>0</MaxTileRow>" in limits
