"""MeerKLASS data management CLI."""

import click

from meerdata import sites
from meerdata.cli.common import CONTEXT_SETTINGS


@click.group(
    context_settings=CONTEXT_SETTINGS,
    epilog="Run `meerdata COMMAND -h` for more details.",
)
@click.option(
    "--site",
    type=str,
    default=None,
    help=(
        'Explicit site name to use (e.g. "ilifu", "local"). Overrides '
        "auto-detection. Can also be set via the MEERDATA_SITE environment "
        "variable."
    ),
)
@click.option(
    "--site-config",
    "site_config_path",
    type=click.Path(exists=True, dir_okay=False, resolve_path=True),
    default=None,
    help="Path to a custom site config YAML file. Overrides --site and "
    "auto-detection entirely.",
)
@click.pass_context
def cli(ctx, site, site_config_path):
    """MeerKLASS data management tool."""
    ctx.obj = sites.resolve_site(site, site_config_path)


from meerdata.cli import check, extract, pull, verify  # noqa: F401
