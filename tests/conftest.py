"""Shared test fixtures for tilepack tests."""

from pathlib import Path

import pytest

from tilepack.convert import run_convert
from tilepack.tms_utils import PNG_SIGNATURE

# Minimal valid PNG: 1x1 pixel, 8-bit RGBA
# PNG signature + IHDR + IDAT + IEND (the smallest valid PNG possible)
_MINIMAL_PNG = (
    PNG_SIGNATURE
    + b"\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde"
    + b"\x00\x00\x00\x0cIDATx\x9cc\xf8\x0f\x00\x00\x01\x01\x00\x05\x18\xd8N"
    + b"\x00\x00\x00\x00IEND\xaeB`\x82"
)


def _write_tile(root: Path, z: int, x: int, y: int) -> Path:
    """Write a minimal PNG tile at root/z/x/y.png."""
    tile_dir = root / str(z) / str(x)
    tile_dir.mkdir(parents=True, exist_ok=True)
    tile_path = tile_dir / f"{y}.png"
    tile_path.write_bytes(_MINIMAL_PNG)
    return tile_path


@pytest.fixture()
def tiny_tms_dir(tmp_path: Path) -> Path:
    """Create a minimal TMS tile directory (y=0 at south).

    Uses z=1 with a tile in the northern hemisphere:
      - TMS y=1 (north half), x=0 (western half)
      - TMS y=1, x=1 (eastern half)

    And z=2 with a couple tiles:
      - TMS y=2, x=0
      - TMS y=3, x=1
    """
    root = tmp_path / "tms_tiles"
    root.mkdir()

    # z=1: 2x2 grid. TMS y=1 = northern hemisphere
    _write_tile(root, 1, 0, 1)
    _write_tile(root, 1, 1, 1)

    # z=2: 4x4 grid. TMS y=2,3 = northern hemisphere
    _write_tile(root, 2, 0, 2)
    _write_tile(root, 2, 1, 3)

    return root


@pytest.fixture()
def tiny_xyz_dir(tmp_path: Path) -> Path:
    """Create a minimal XYZ tile directory (y=0 at north).

    Equivalent geographic area to tiny_tms_dir but with flipped y values.
    z=1: XYZ y=0 (north half) = TMS y=1
    z=2: XYZ y=1 (TMS y=2), XYZ y=0 (TMS y=3)
    """
    root = tmp_path / "xyz_tiles"
    root.mkdir()

    # z=1: XYZ y=0 = TMS y=1 (northern hemisphere)
    _write_tile(root, 1, 0, 0)
    _write_tile(root, 1, 1, 0)

    # z=2: XYZ y=1 = TMS y=2, XYZ y=0 = TMS y=3
    _write_tile(root, 2, 0, 1)
    _write_tile(root, 2, 1, 0)

    return root


@pytest.fixture()
def tiny_mbtiles(tmp_path: Path, tiny_tms_dir: Path) -> Path:
    """Convert tiny_tms_dir to a small .mbtiles file."""

    out = tmp_path / "test.mbtiles"
    run_convert(str(tiny_tms_dir), str(out), scheme="tms")
    return out


@pytest.fixture()
def tiny_pmtiles(tmp_path: Path, tiny_tms_dir: Path) -> Path:
    """Convert tiny_tms_dir to a small .pmtiles file."""

    out = tmp_path / "test.pmtiles"
    run_convert(str(tiny_tms_dir), str(out), scheme="tms")
    return out
