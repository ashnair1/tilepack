"""Tests for tilepack.convert."""

import sqlite3
from pathlib import Path

from tilepack.convert import run_convert


class TestConvertToMbtiles:
    def test_creates_mbtiles_file(self, tmp_path: Path, tiny_tms_dir: Path):
        out = tmp_path / "output.mbtiles"
        run_convert(str(tiny_tms_dir), str(out), scheme="tms")
        assert out.exists()
        assert out.stat().st_size > 0

    def test_mbtiles_tile_count(self, tmp_path: Path, tiny_tms_dir: Path):
        out = tmp_path / "output.mbtiles"
        run_convert(str(tiny_tms_dir), str(out), scheme="tms")
        conn = sqlite3.connect(str(out))
        count = conn.execute("SELECT COUNT(*) FROM tiles").fetchone()[0]
        conn.close()
        assert count == 4

    def test_mbtiles_metadata(self, tmp_path: Path, tiny_tms_dir: Path):
        out = tmp_path / "output.mbtiles"
        run_convert(str(tiny_tms_dir), str(out), scheme="tms")
        conn = sqlite3.connect(str(out))
        meta = dict(conn.execute("SELECT name, value FROM metadata").fetchall())
        conn.close()
        assert meta["format"] == "png"
        assert "minzoom" in meta
        assert "maxzoom" in meta
        assert meta["minzoom"] == "1"
        assert meta["maxzoom"] == "2"

    def test_xyz_input_flips_y(self, tmp_path: Path, tiny_xyz_dir: Path):
        out = tmp_path / "output.mbtiles"
        run_convert(str(tiny_xyz_dir), str(out), scheme="xyz")
        conn = sqlite3.connect(str(out))
        # z=1, x=0, XYZ y=0 should become TMS y=1
        row = conn.execute(
            "SELECT tile_data FROM tiles WHERE zoom_level=1 AND tile_column=0 AND tile_row=1"
        ).fetchone()
        conn.close()
        assert row is not None, "Expected XYZ y=0 to be stored as TMS y=1"

    def test_auto_detect_scheme(self, tmp_path: Path, tiny_tms_dir: Path):
        out = tmp_path / "output.mbtiles"
        # No scheme specified — should auto-detect as TMS
        run_convert(str(tiny_tms_dir), str(out))
        assert out.exists()
        conn = sqlite3.connect(str(out))
        count = conn.execute("SELECT COUNT(*) FROM tiles").fetchone()[0]
        conn.close()
        assert count == 4


class TestConvertToPmtiles:
    def test_creates_pmtiles_file(self, tmp_path: Path, tiny_tms_dir: Path):
        out = tmp_path / "output.pmtiles"
        run_convert(str(tiny_tms_dir), str(out), scheme="tms")
        assert out.exists()
        assert out.stat().st_size > 0

    def test_pmtiles_tiles_readable(self, tmp_path: Path, tiny_tms_dir: Path):
        out = tmp_path / "output.pmtiles"
        run_convert(str(tiny_tms_dir), str(out), scheme="tms")

        from pmtiles.reader import MmapSource
        from pmtiles.reader import Reader as PMTilesReader

        source = MmapSource(open(out, "rb"))
        reader = PMTilesReader(source)
        header = reader.header()
        assert header["min_zoom"] == 1
        assert header["max_zoom"] == 2

    def test_xyz_input_to_pmtiles(self, tmp_path: Path, tiny_xyz_dir: Path):
        out = tmp_path / "output.pmtiles"
        run_convert(str(tiny_xyz_dir), str(out), scheme="xyz")
        assert out.exists()

        from pmtiles.reader import MmapSource
        from pmtiles.reader import Reader as PMTilesReader

        source = MmapSource(open(out, "rb"))
        reader = PMTilesReader(source)
        # z=1, x=0, XYZ y=0 — should be stored directly as XYZ (no flip)
        data = reader.get(1, 0, 0)
        assert data is not None


class TestConvertErrors:
    def test_unknown_format(self, tmp_path: Path, tiny_tms_dir: Path):
        out = tmp_path / "output.unknown"
        try:
            run_convert(str(tiny_tms_dir), str(out))
        except SystemExit as e:
            assert e.code == 1

    def test_empty_dir(self, tmp_path: Path):
        empty = tmp_path / "empty"
        empty.mkdir()
        out = tmp_path / "output.mbtiles"
        try:
            run_convert(str(empty), str(out))
        except SystemExit as e:
            assert e.code == 1
