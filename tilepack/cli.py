"""CLI entrypoint for tilepack."""

from importlib.metadata import version

import click


@click.group()
@click.version_option(version("tilepack"), prog_name="tilepack")
def cli():
    """Convert TMS/XYZ tile folders to MBTiles/PMTiles and serve as TMS/WMTS endpoints."""


@cli.command()
@click.argument("input_path", type=click.Path(exists=True))
def verify(input_path):
    """Scan a TMS folder or MBTiles/PMTiles archive and report tile statistics."""
    from tilepack.verify import run_verify

    run_verify(input_path)


@cli.command()
@click.argument("input_root", type=click.Path(exists=True, file_okay=False))
@click.argument("output_file", type=click.Path())
@click.option(
    "--scheme",
    type=click.Choice(["tms", "xyz"]),
    default=None,
    help="Input tile scheme (auto-detected if omitted).",
)
def convert(input_root, output_file, scheme):
    """Convert a tile folder to MBTiles or PMTiles (inferred from extension)."""
    from tilepack.convert import run_convert

    run_convert(input_root, output_file, scheme=scheme)


@cli.command()
@click.argument("archive_file", type=click.Path(exists=True, dir_okay=False))
@click.option("--port", default=8000, help="Port to bind to.")
@click.option("--host", default="127.0.0.1", help="Host to bind to.")
def serve(archive_file, port, host):
    """Serve an MBTiles or PMTiles archive as a TMS endpoint."""
    from tilepack.serve import run_serve

    run_serve(archive_file, host, port)


@cli.command()
@click.argument("input_root", type=click.Path(exists=True, file_okay=False))
@click.option("--base-url", required=True, help="Base URL of the running TMS server.")
@click.option("--samples", default=200, help="Number of tiles to sample.")
def selftest(input_root, base_url, samples):
    """Validate a served TMS endpoint against the original tile folder."""
    from tilepack.selftest import run_selftest

    run_selftest(input_root, base_url, samples)
