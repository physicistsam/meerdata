"""Site configuration loading, auto-detection, and resolution.

A "site" describes where meerdata is running: default paths, and whether jobs
are submitted to SLURM or run directly (local mode). Known sites ship as YAML
files in `meerdata/configs/`; unlisted HPC systems can be described in an
arbitrary YAML file passed via `--site-config`.
"""

import os
import socket
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

import click
import yaml

CONFIGS_DIR = Path(__file__).resolve().parent / "configs"


@dataclass
class SlurmConfig:
    """SLURM settings for a site.

    `options` and each entry in `resources` are lists of raw `--flag=value`
    sbatch directive strings (same shape as `-s`/`--slurm-override`) so a
    site config can set any SBATCH-compatible option, not just a fixed set
    of fields. `options` applies to every generated job; `resources[step]`
    applies (and can override `options`) for that one step.
    """

    modules: list[str] = field(default_factory=list)
    scontrol_path: str = "scontrol"
    options: list[str] = field(default_factory=list)
    resources: dict[str, list[str]] = field(default_factory=dict)


@dataclass
class SitePaths:
    venv: Path | None = None
    data_folder: Path | None = None
    sanity_check_folder: Path | None = None


@dataclass
class SiteConfig:
    name: str
    scheduler: str
    paths: SitePaths
    slurm: SlurmConfig

    @classmethod
    def from_dict(cls, name: str, data: dict) -> "SiteConfig":
        paths_data = data.get("paths") or {}
        paths = SitePaths(
            venv=_maybe_path(paths_data.get("venv")),
            data_folder=_maybe_path(paths_data.get("data_folder")),
            sanity_check_folder=_maybe_path(paths_data.get("sanity_check_folder")),
        )
        slurm_data = data.get("slurm") or {}
        slurm = SlurmConfig(
            modules=slurm_data.get("modules", []),
            scontrol_path=slurm_data.get("scontrol_path", "scontrol"),
            options=slurm_data.get("options", []),
            resources=slurm_data.get("resources", {}),
        )
        return cls(
            name=name,
            scheduler=data.get("scheduler", "slurm"),
            paths=paths,
            slurm=slurm,
        )


def _maybe_path(value: str | None) -> Path | None:
    return Path(value) if value else None


def _load_yaml(path: Path) -> dict:
    with path.open("r") as fh:
        return yaml.safe_load(fh) or {}


def list_known_sites() -> list[str]:
    """Names of all site configs shipped inside the package."""
    return sorted(p.stem for p in CONFIGS_DIR.glob("*.yaml"))


def load_site_config(name_or_path: str) -> SiteConfig:
    """Load a site config by known name (e.g. "ilifu") or filesystem path."""
    candidate = Path(name_or_path)
    if candidate.suffix in (".yaml", ".yml") and candidate.is_file():
        return SiteConfig.from_dict(candidate.stem, _load_yaml(candidate))

    packaged = CONFIGS_DIR / f"{name_or_path}.yaml"
    if not packaged.is_file():
        raise click.ClickException(
            f'Unknown site "{name_or_path}". Known sites: '
            f"{', '.join(list_known_sites())}. Use --site-config to point at "
            "a custom YAML file instead."
        )
    return SiteConfig.from_dict(name_or_path, _load_yaml(packaged))


def _score_markers(detect: dict) -> tuple[int, dict[str, bool]]:
    """Score a site's `detect:` marker block against the current machine."""
    markers: dict[str, bool] = {}

    for env_var, expected in (detect.get("env") or {}).items():
        actual = os.environ.get(env_var, "")
        markers[f"env:{env_var}"] = bool(actual) and expected.lower() in actual.lower()

    hostname = socket.getfqdn().lower()
    for substr in detect.get("hostname_contains", []):
        markers[f"hostname_contains:{substr}"] = substr.lower() in hostname
    for suffix in detect.get("hostname_suffix", []):
        markers[f"hostname_suffix:{suffix}"] = hostname.endswith(suffix.lower())

    for path_str in detect.get("path_exists", []):
        markers[f"path_exists:{path_str}"] = Path(path_str).exists()

    command = detect.get("command")
    if command:
        try:
            res = subprocess.run(
                [command["name"]], capture_output=True, text=True, check=False
            )
            out = (res.stdout or "") + (res.stderr or "")
            markers[f"command:{command['name']}"] = (
                command["output_contains"].lower() in out.lower()
            )
        except OSError:
            markers[f"command:{command['name']}"] = False

    return sum(1 for hit in markers.values() if hit), markers


def detect_site() -> str | None:
    """Return the first known non-local site whose markers score high enough."""
    for name in list_known_sites():
        if name == "local":
            continue
        detect = _load_yaml(CONFIGS_DIR / f"{name}.yaml").get("detect")
        if not detect:
            continue
        score, _markers = _score_markers(detect)
        if score >= detect.get("min_markers", 2):
            return name
    return None


def resolve_site(
    explicit_site: str | None = None, explicit_config_path: str | None = None
) -> SiteConfig:
    """Resolve which site config to use.

    Priority: --site-config path > --site name > MEERDATA_SITE env var >
    auto-detection > the "local" fallback.
    """
    if explicit_config_path:
        return load_site_config(explicit_config_path)
    if explicit_site:
        return load_site_config(explicit_site)

    env_site = os.environ.get("MEERDATA_SITE")
    if env_site:
        return load_site_config(env_site)

    detected = detect_site()
    return load_site_config(detected or "local")
