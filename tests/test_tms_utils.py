"""Tests for tilepack.tms_utils."""

from pathlib import Path

from tilepack.tms_utils import (
    ZoomStats,
    _tile2lat_xyz,
    _tile2lon,
    collect_zoom_stats,
    compute_bounds,
    detect_scheme,
    generate_tilemapresource_xml,
    iter_tiles,
)


class TestTileCoordinates:
    def test_tile2lon_origin(self):
        # x=0, z=0 → -180
        assert _tile2lon(0, 0) == -180.0

    def test_tile2lon_midpoint(self):
        # x=1, z=1 → 0 (prime meridian)
        assert _tile2lon(1, 1) == 0.0

    def test_tile2lon_end(self):
        # x=2^z, z=any → 180
        assert _tile2lon(4, 2) == 180.0

    def test_tile2lat_xyz_north_pole(self):
        # y=0, z=0 → ~85.05 (north)
        lat = _tile2lat_xyz(0, 0)
        assert lat > 85.0

    def test_tile2lat_xyz_equator(self):
        # y=2^(z-1), z=1 → 0 (equator)
        lat = _tile2lat_xyz(1, 1)
        assert abs(lat) < 0.01

    def test_tile2lat_xyz_south_pole(self):
        # y=2^z, z=0 → ~-85.05 (south)
        lat = _tile2lat_xyz(1, 0)
        assert lat < -85.0


class TestZoomStats:
    def test_update_single(self):
        s = ZoomStats()
        s.update(5, 10)
        assert s.min_x == 5
        assert s.max_x == 5
        assert s.min_y == 10
        assert s.max_y == 10
        assert s.count == 1

    def test_update_multiple(self):
        s = ZoomStats()
        s.update(3, 7)
        s.update(1, 10)
        s.update(5, 2)
        assert s.min_x == 1
        assert s.max_x == 5
        assert s.min_y == 2
        assert s.max_y == 10
        assert s.count == 3


class TestIterTiles:
    def test_yields_correct_tiles(self, tiny_tms_dir: Path):
        tiles = sorted(iter_tiles(tiny_tms_dir))
        # Should yield 4 tiles: z1(0,1), z1(1,1), z2(0,2), z2(1,3)
        assert len(tiles) == 4
        assert (tiles[0][0], tiles[0][1], tiles[0][2]) == (1, 0, 1)
        assert (tiles[1][0], tiles[1][1], tiles[1][2]) == (1, 1, 1)
        assert (tiles[2][0], tiles[2][1], tiles[2][2]) == (2, 0, 2)
        assert (tiles[3][0], tiles[3][1], tiles[3][2]) == (2, 1, 3)

    def test_ignores_non_tile_files(self, tiny_tms_dir: Path):
        # Add a non-tile file
        (tiny_tms_dir / "1" / "0" / "readme.txt").write_text("ignore me")
        tiles = list(iter_tiles(tiny_tms_dir))
        assert len(tiles) == 4

    def test_ignores_non_numeric_dirs(self, tiny_tms_dir: Path):
        # Add a non-numeric directory
        (tiny_tms_dir / "metadata").mkdir()
        tiles = list(iter_tiles(tiny_tms_dir))
        assert len(tiles) == 4


class TestCollectZoomStats:
    def test_stats_from_tms_dir(self, tiny_tms_dir: Path):
        stats = collect_zoom_stats(tiny_tms_dir)
        assert set(stats.keys()) == {1, 2}
        assert stats[1].count == 2
        assert stats[2].count == 2
        assert stats[1].min_x == 0
        assert stats[1].max_x == 1
        assert stats[1].min_y == 1
        assert stats[1].max_y == 1

    def test_empty_dir(self, tmp_path: Path):
        stats = collect_zoom_stats(tmp_path)
        assert stats == {}


class TestComputeBounds:
    def test_tms_bounds_northern_hemisphere(self, tiny_tms_dir: Path):
        stats = collect_zoom_stats(tiny_tms_dir)
        bounds = compute_bounds(stats, scheme="tms")
        min_lon, min_lat, max_lon, max_lat = bounds
        # Tiles at z=1 x=0,1 y=1 (TMS) cover the full longitude and northern hemisphere
        assert min_lon < 0
        assert max_lon > 0
        assert min_lat >= 0  # northern hemisphere
        assert max_lat > 0

    def test_xyz_bounds_northern_hemisphere(self, tiny_xyz_dir: Path):
        stats = collect_zoom_stats(tiny_xyz_dir)
        bounds = compute_bounds(stats, scheme="xyz")
        min_lon, min_lat, max_lon, max_lat = bounds
        assert min_lat >= 0  # northern hemisphere
        assert max_lat > 0

    def test_tms_and_xyz_same_geographic_area(self):
        # At higher zoom, TMS and XYZ with equivalent tiles should give close bounds
        # z=10: TMS y=600 corresponds to XYZ y=(1023-600)=423
        stats_tms = {10: ZoomStats(min_x=500, max_x=510, min_y=600, max_y=610, count=100)}
        tms_bounds = compute_bounds(stats_tms, scheme="tms")
        stats_xyz = {10: ZoomStats(min_x=500, max_x=510, min_y=413, max_y=423, count=100)}
        xyz_bounds = compute_bounds(stats_xyz, scheme="xyz")
        # At z=10 one tile row ≈ 0.17°, so off-by-one means ≈0.5° tolerance
        for a, b in zip(tms_bounds, xyz_bounds):
            assert abs(a - b) < 0.5


class TestDetectScheme:
    def test_detects_tms_with_xml(self, tiny_tms_dir: Path):
        stats = collect_zoom_stats(tiny_tms_dir)
        scheme, _, _ = detect_scheme(stats, has_tilemapresource=True)
        assert scheme == "tms"

    def test_detects_tms_heuristic(self, tiny_tms_dir: Path):
        # TMS tiles have high y values (y=1 at z=1, y>midpoint) → detected as TMS
        stats = collect_zoom_stats(tiny_tms_dir)
        scheme, _, _ = detect_scheme(stats, has_tilemapresource=False)
        assert scheme == "tms"

    def test_detects_xyz_heuristic(self, tiny_xyz_dir: Path):
        # XYZ tiles have low y values (y=0 at z=1, y<midpoint) → detected as XYZ
        stats = collect_zoom_stats(tiny_xyz_dir)
        scheme, _, _ = detect_scheme(stats, has_tilemapresource=False)
        assert scheme == "xyz"

    def test_returns_both_bounds(self, tiny_tms_dir: Path):
        stats = collect_zoom_stats(tiny_tms_dir)
        _, tms_bounds, xyz_bounds = detect_scheme(stats)
        assert len(tms_bounds) == 4
        assert len(xyz_bounds) == 4
        # TMS and XYZ bounds should differ (mirrored latitudes)
        assert tms_bounds != xyz_bounds


class TestGenerateTimemapresourceXml:
    def test_contains_expected_elements(self):
        xml = generate_tilemapresource_xml(
            minzoom=0,
            maxzoom=2,
            bounds=(-180, -85, 180, 85),
            tile_format="png",
            title="Test",
        )
        assert "<TileMap" in xml
        assert "<BoundingBox" in xml
        assert "<TileSets" in xml
        assert "<TileSet" in xml
        assert "EPSG:3857" in xml
        assert "<Title>Test</Title>" in xml

    def test_zoom_range(self):
        xml = generate_tilemapresource_xml(minzoom=2, maxzoom=4, bounds=(-10, -10, 10, 10))
        assert 'order="2"' in xml
        assert 'order="3"' in xml
        assert 'order="4"' in xml
        assert 'order="1"' not in xml
        assert 'order="5"' not in xml

    def test_epsg_4326_srs(self):
        xml = generate_tilemapresource_xml(
            minzoom=0, maxzoom=1, bounds=(-180, -85, 180, 85), srs="EPSG:4326"
        )
        assert "EPSG:4326" in xml
        assert "global-geodetic" in xml
