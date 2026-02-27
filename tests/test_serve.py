"""Tests for tilepack.serve."""

from pathlib import Path

from starlette.testclient import TestClient

from tilepack.serve import _build_mbtiles_app, _build_pmtiles_app
from tilepack.tms_utils import PNG_SIGNATURE


class TestMbtilesServing:
    def test_tilemapresource(self, tiny_mbtiles: Path):
        app = _build_mbtiles_app(tiny_mbtiles, host="127.0.0.1", port=8000)
        client = TestClient(app)
        resp = client.get("/tilemapresource.xml")
        assert resp.status_code == 200
        assert "<TileMap" in resp.text
        assert "application/xml" in resp.headers["content-type"]

    def test_tile_found(self, tiny_mbtiles: Path):
        app = _build_mbtiles_app(tiny_mbtiles, host="127.0.0.1", port=8000)
        client = TestClient(app)
        # z=1, x=0, y=1 (TMS) should exist
        resp = client.get("/1/0/1.png")
        assert resp.status_code == 200
        assert resp.content[:8] == PNG_SIGNATURE

    def test_tile_not_found(self, tiny_mbtiles: Path):
        app = _build_mbtiles_app(tiny_mbtiles, host="127.0.0.1", port=8000)
        client = TestClient(app)
        resp = client.get("/0/0/0.png")
        assert resp.status_code == 404

    def test_wmts_capabilities(self, tiny_mbtiles: Path):
        app = _build_mbtiles_app(tiny_mbtiles, host="127.0.0.1", port=8000)
        client = TestClient(app)
        resp = client.get("/WMTSCapabilities.xml")
        assert resp.status_code == 200
        assert "<Capabilities" in resp.text

    def test_wmts_tile_rest(self, tiny_mbtiles: Path):
        app = _build_mbtiles_app(tiny_mbtiles, host="127.0.0.1", port=8000)
        client = TestClient(app)
        # WMTS row 0 at z=1 = XYZ y=0 → TMS y=1
        resp = client.get("/wmts/test/GoogleMapsCompatible/1/0/0.png")
        assert resp.status_code == 200
        assert resp.content[:8] == PNG_SIGNATURE

    def test_wmts_kvp_get_capabilities(self, tiny_mbtiles: Path):
        app = _build_mbtiles_app(tiny_mbtiles, host="127.0.0.1", port=8000)
        client = TestClient(app)
        resp = client.get("/wmts?Service=WMTS&Request=GetCapabilities")
        assert resp.status_code == 200
        assert "<Capabilities" in resp.text


class TestPmtilesServing:
    def test_tilemapresource(self, tiny_pmtiles: Path):
        app = _build_pmtiles_app(tiny_pmtiles, host="127.0.0.1", port=8000)
        client = TestClient(app)
        resp = client.get("/tilemapresource.xml")
        assert resp.status_code == 200
        assert "<TileMap" in resp.text

    def test_tile_found(self, tiny_pmtiles: Path):
        app = _build_pmtiles_app(tiny_pmtiles, host="127.0.0.1", port=8000)
        client = TestClient(app)
        # z=1, x=0, y_tms=1 should exist (PMTiles serves TMS y internally flipped)
        resp = client.get("/1/0/1.png")
        assert resp.status_code == 200
        assert resp.content[:8] == PNG_SIGNATURE

    def test_tile_not_found(self, tiny_pmtiles: Path):
        app = _build_pmtiles_app(tiny_pmtiles, host="127.0.0.1", port=8000)
        client = TestClient(app)
        resp = client.get("/0/0/0.png")
        assert resp.status_code == 404

    def test_wmts_capabilities(self, tiny_pmtiles: Path):
        app = _build_pmtiles_app(tiny_pmtiles, host="127.0.0.1", port=8000)
        client = TestClient(app)
        resp = client.get("/WMTSCapabilities.xml")
        assert resp.status_code == 200
        assert "<Capabilities" in resp.text
