"""Tests for tilepack.cli."""

from pathlib import Path

from click.testing import CliRunner

from tilepack.cli import cli


class TestVerifyCommand:
    def test_verify_tms_dir(self, tiny_tms_dir: Path):
        runner = CliRunner()
        result = runner.invoke(cli, ["verify", str(tiny_tms_dir)])
        assert result.exit_code == 0
        assert "Zoom range" in result.output
        assert "Detected scheme: TMS" in result.output

    def test_verify_empty_dir(self, tmp_path: Path):
        empty = tmp_path / "empty"
        empty.mkdir()
        runner = CliRunner()
        result = runner.invoke(cli, ["verify", str(empty)])
        assert result.exit_code == 1


class TestConvertCommand:
    def test_convert_to_mbtiles(self, tmp_path: Path, tiny_tms_dir: Path):
        out = tmp_path / "output.mbtiles"
        runner = CliRunner()
        result = runner.invoke(cli, ["convert", str(tiny_tms_dir), str(out)])
        assert result.exit_code == 0
        assert out.exists()

    def test_convert_with_scheme_flag(self, tmp_path: Path, tiny_xyz_dir: Path):
        out = tmp_path / "output.mbtiles"
        runner = CliRunner()
        result = runner.invoke(cli, ["convert", str(tiny_xyz_dir), str(out), "--scheme", "xyz"])
        assert result.exit_code == 0
        assert "Using specified scheme: XYZ" in result.output

    def test_convert_auto_detect(self, tmp_path: Path, tiny_tms_dir: Path):
        out = tmp_path / "output.mbtiles"
        runner = CliRunner()
        result = runner.invoke(cli, ["convert", str(tiny_tms_dir), str(out)])
        assert result.exit_code == 0
        assert "Detected input scheme:" in result.output
