"""ASCII-art name banner for the `cassandra` CLI.

Deliberately dependency-free (no pyfiglet) and import-light so it prints instantly.
"""

from __future__ import annotations

import sys
from importlib.metadata import PackageNotFoundError, version

# Block-letter "Cassandra" (figlet 'standard' font). Raw string — do not reflow;
# the backslashes are art.
_ART = r"""
  ____                              _
 / ___|__ _ ___ ___  __ _ _ __   __| |_ __ __ _
| |   / _` / __/ __|/ _` | '_ \ / _` | '__/ _` |
| |__| (_| \__ \__ \ (_| | | | | (_| | | | (_| |
 \____\__,_|___/___/\__,_|_| |_|\__,_|_|  \__,_|
"""

_TAGLINE = "the meta-agent that watches other agents"


def get_version() -> str:
    """Installed distribution version, or a dev sentinel when running from source."""
    try:
        return version("cassandra-ai")
    except PackageNotFoundError:
        return "0.0.0-dev"


def print_banner(*, file=None) -> None:
    """Print the art + tagline + version. No heavy imports; safe to call at startup."""
    file = file if file is not None else sys.stdout
    print(_ART, file=file)
    print(f"    {_TAGLINE}  --  v{get_version()}", file=file)
    print(file=file)
