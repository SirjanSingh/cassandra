"""Packaging guards for what pyproject.toml declares.

cassandra-ai 0.3.0 shipped two defects the rest of the suite could not see, because
entry points, wheel contents and version ranges are strings in pyproject.toml:

1. the wheel installed top-level `cassandra`, `patient` and `dashboard` packages
   (`cassandra` is cassandra-driver's import name);
2. `mcp>=1.2.0` resolved to mcp 2.x, which removed `mcp.server.fastmcp`.

`scripts/smoke_install.py` checks the *built* wheel in a clean venv; these tests keep
the declarations themselves honest on every run.
"""

from __future__ import annotations

import importlib
import tomllib
from pathlib import Path

from packaging.requirements import Requirement

import cassandra_ai

ROOT = Path(__file__).resolve().parents[1]
PYPROJECT = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
PROJECT = PYPROJECT["project"]
EXTRAS = PROJECT["optional-dependencies"]


def _requirements(*groups: list[str]) -> list[Requirement]:
    reqs = [Requirement(r) for group in groups for r in group]
    return [r for r in reqs if r.name != PROJECT["name"]]  # skip self-referencing extras


def test_wheel_ships_only_the_namespaced_package():
    assert PYPROJECT["tool"]["hatch"]["build"]["targets"]["wheel"]["packages"] == [
        "cassandra_ai"
    ]
    assert not (ROOT / "cassandra" / "__init__.py").exists()  # the old name must not return


def test_console_scripts_resolve_to_callables():
    for name, target in PROJECT["scripts"].items():
        module_name, _, attr = target.partition(":")
        assert module_name.split(".")[0] == "cassandra_ai", name
        obj = getattr(importlib.import_module(module_name), attr)
        assert callable(obj), f"{name} -> {target} is not callable"


def test_version_has_a_single_source():
    assert "version" not in PROJECT and "version" in PROJECT["dynamic"]
    version_file = ROOT / PYPROJECT["tool"]["hatch"]["version"]["path"]
    assert version_file == ROOT / "cassandra_ai" / "__init__.py"
    assert f'__version__ = "{cassandra_ai.__version__}"' in version_file.read_text("utf-8")


def test_every_runtime_dependency_has_an_upper_bound():
    # A floor-only range lets a breaking major upstream release break fresh installs.
    groups = [PROJECT["dependencies"], EXTRAS["full"], EXTRAS["adk"]]
    for req in _requirements(*groups):
        ops = {spec.operator for spec in req.specifier}
        assert ops & {"<", "<=", "==", "~="}, f"{req} has no upper bound"


def test_mcp_stays_on_the_1x_api():
    (mcp,) = [r for r in _requirements(EXTRAS["full"]) if r.name == "mcp"]
    assert mcp.specifier.contains("1.30.0")
    assert not mcp.specifier.contains("2.0.0")  # mcp_server.py imports mcp.server.fastmcp


def test_google_adk_is_opt_in():
    # google-adk caps opentelemetry-api <= 1.44; keeping it out of `full` lets `full`
    # resolve the fixed opentelemetry-api (CVE-2026-114603, fixed in 1.45.1).
    assert "google-adk" not in {r.name for r in _requirements(EXTRAS["full"])}
    assert "google-adk" in {r.name for r in _requirements(EXTRAS["adk"])}
