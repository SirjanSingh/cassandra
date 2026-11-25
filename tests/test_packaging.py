"""Packaging guards for what pyproject.toml declares.

cassandra-ai 0.3.0 shipped defects the rest of the suite could not see, because entry
points, wheel contents and version ranges are strings in pyproject.toml: the wheel
installed a top-level `cassandra` package (cassandra-driver's import name), and a
floor-only `mcp` range resolved to a breaking major. `scripts/smoke_install.py` checks
the *built* wheel in a clean venv; these tests keep the declarations honest on every run.
"""

from __future__ import annotations

import importlib
import re
import tomllib
from pathlib import Path

import cassandra_ai

ROOT = Path(__file__).resolve().parents[1]
PYPROJECT = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
PROJECT = PYPROJECT["project"]
EXTRAS = PROJECT["optional-dependencies"]
_NAME = re.compile(r"^\s*([A-Za-z0-9_.-]+)")


def _requirements(*groups: list[str]) -> list[str]:
    reqs = [r for group in groups for r in group]
    return [r for r in reqs if not r.startswith(PROJECT["name"])]  # skip self-referencing extras


def test_wheel_ships_only_the_namespaced_package():
    wheel = PYPROJECT["tool"]["hatch"]["build"]["targets"]["wheel"]
    assert wheel["packages"] == ["cassandra_ai"]
    assert not (ROOT / "cassandra" / "__init__.py").exists()  # the old name must not return


def test_console_script_resolves_to_a_callable():
    for name, target in PROJECT["scripts"].items():
        module_name, _, attr = target.partition(":")
        assert module_name.split(".")[0] == "cassandra_ai", name
        assert callable(getattr(importlib.import_module(module_name), attr)), name


def test_version_has_a_single_source():
    assert "version" not in PROJECT and "version" in PROJECT["dynamic"]
    version_file = ROOT / PYPROJECT["tool"]["hatch"]["version"]["path"]
    assert version_file == ROOT / "cassandra_ai" / "__init__.py"
    assert f'__version__ = "{cassandra_ai.__version__}"' in version_file.read_text("utf-8")


def test_every_dependency_has_an_upper_bound():
    # A floor-only range lets a breaking upstream major break fresh installs.
    groups = [PROJECT["dependencies"], *EXTRAS.values()]
    for req in _requirements(*groups):
        assert re.search(r"(<|<=|==|~=)", req), f"{req} has no upper bound"


def test_core_install_stays_small():
    names = {_NAME.match(r).group(1).lower() for r in PROJECT["dependencies"]}
    assert names == {"pydantic", "pydantic-settings"}
