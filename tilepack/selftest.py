"""Selftest command: validate served tiles against original TMS folder."""

from __future__ import annotations

import random
import time
from pathlib import Path

import click
import httpx

from tilepack.tms_utils import PNG_SIGNATURE, iter_tiles


def run_selftest(input_root: str, base_url: str, samples: int) -> None:
    root = Path(input_root).resolve()
    base = base_url.rstrip("/")

    click.echo(f"Selftest: {root}")
    click.echo(f"Server:   {base}")
    click.echo(f"Samples:  {samples}\n")

    # Collect all tile coordinates
    all_tiles = [(z, x, y, p) for z, x, y, p in iter_tiles(root)]
    if not all_tiles:
        click.echo("No tiles found in input folder.", err=True)
        raise SystemExit(1)

    # Sample
    if samples >= len(all_tiles):
        selected = all_tiles
    else:
        selected = random.sample(all_tiles, samples)

    passed = 0
    failed = 0
    errors = []
    latencies = []

    with httpx.Client(timeout=30.0) as client:
        for z, x, y, tile_path in selected:
            url = f"{base}/{z}/{x}/{y}.png"
            original = tile_path.read_bytes()

            t0 = time.perf_counter()
            try:
                resp = client.get(url)
            except httpx.RequestError as e:
                failed += 1
                errors.append(f"  {z}/{x}/{y}: connection error: {e}")
                continue
            latency_ms = (time.perf_counter() - t0) * 1000
            latencies.append(latency_ms)

            # Check status
            if resp.status_code != 200:
                failed += 1
                errors.append(f"  {z}/{x}/{y}: HTTP {resp.status_code}")
                continue

            # Check content type
            ct = resp.headers.get("content-type", "")
            if "image/png" not in ct:
                failed += 1
                errors.append(f"  {z}/{x}/{y}: wrong content-type: {ct}")
                continue

            # Check PNG header
            if resp.content[:8] != PNG_SIGNATURE:
                failed += 1
                errors.append(f"  {z}/{x}/{y}: invalid PNG header")
                continue

            # Byte comparison
            if resp.content != original:
                failed += 1
                errors.append(
                    f"  {z}/{x}/{y}: byte mismatch "
                    f"(original={len(original)}, served={len(resp.content)})"
                )
                continue

            passed += 1

    # Report
    avg_latency = sum(latencies) / len(latencies) if latencies else 0

    click.echo(f"Total tested: {passed + failed}")
    click.echo(f"Passed:       {passed}")
    click.echo(f"Failed:       {failed}")
    click.echo(f"Avg latency:  {avg_latency:.1f}ms")

    if errors:
        click.echo(f"\nFailures:")
        for e in errors[:20]:
            click.echo(e)
        if len(errors) > 20:
            click.echo(f"  ... and {len(errors) - 20} more")

    if failed > 0:
        raise SystemExit(1)
