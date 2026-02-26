"""CLI entrypoint for tms_packager."""

import click


@click.group()
def cli():
    """Convert TMS tile folders to MBTiles/PMTiles and serve as TMS endpoints."""


@cli.command()
@click.argument("input_root", type=click.Path(exists=True, file_okay=False))
def verify(input_root):
    """Scan a TMS folder and report tile statistics."""
    from tms_packager.verify import run_verify

    run_verify(input_root)


@cli.command()
@click.argument("input_root", type=click.Path(exists=True, file_okay=False))
@click.argument("output_file", type=click.Path())
def convert(input_root, output_file):
    """Convert a TMS folder to MBTiles or PMTiles (inferred from extension)."""
    from tms_packager.convert import run_convert

    run_convert(input_root, output_file)


@cli.command()
@click.argument("archive_file", type=click.Path(exists=True, dir_okay=False))
@click.option("--port", default=8000, help="Port to bind to.")
@click.option("--host", default="127.0.0.1", help="Host to bind to.")
def serve(archive_file, port, host):
    """Serve an MBTiles or PMTiles archive as a TMS endpoint."""
    from tms_packager.serve import run_serve

    run_serve(archive_file, host, port)


@cli.command()
@click.argument("input_root", type=click.Path(exists=True, file_okay=False))
@click.option("--base-url", required=True, help="Base URL of the running TMS server.")
@click.option("--samples", default=200, help="Number of tiles to sample.")
def selftest(input_root, base_url, samples):
    """Validate a served TMS endpoint against the original tile folder."""
    from tms_packager.selftest import run_selftest

    run_selftest(input_root, base_url, samples)
