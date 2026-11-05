"""Smoke-test the built wheel the way a user installs it. Needs network (PyPI).

    python scripts/smoke_install.py           # light install, co-installed with cassandra-driver
    python scripts/smoke_install.py --full    # also install and check the [full] extra

Builds the wheel from this checkout, installs it into a throwaway venv, and runs every
check from a directory OUTSIDE the repo, so the source tree can't shadow the installed
package. Checks:

* the wheel's top-level entries are only `cassandra_ai` and its .dist-info;
* it installs next to cassandra-driver, and `import cassandra` is the driver's;
* the `cassandra` console script runs, and `cassandra scan` works offline (no LLM) on the
  bundled TravelPal sample;
* a light install points pipeline commands at the [full] extra instead of crashing;
* `cassandra dashboard` explains it needs a source checkout;
* with --full: the MCP server imports (mcp<2), `pip check` passes, and opentelemetry-api
  resolves to a version with the CVE-2026-114603 fix (>= 1.45.1).

Exit code 0 means every check passed.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import tempfile
import venv
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SAMPLE_LOGS = ROOT / "poc" / "travelpal" / "runs_heldout.jsonl"
SAMPLE_SPEC = ROOT / "poc" / "travelpal" / "grounding_spec.json"
OTEL_FIXED = (1, 45, 1)

_failures: list[str] = []


def check(ok: bool, what: str, detail: str = "") -> None:
    print(f"  [{'ok' if ok else 'FAIL'}] {what}" + (f"\n         {detail}" if detail and not ok else ""))
    if not ok:
        _failures.append(what)


def run(cmd: list[str], cwd: Path, env: dict | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, cwd=cwd, env=env, capture_output=True, text=True, check=False)


def build_wheel(out: Path) -> Path:
    print(f"building wheel from {ROOT} ...")
    r = run([sys.executable, "-m", "pip", "wheel", str(ROOT), "--no-deps", "-q", "-w", str(out)],
            cwd=ROOT)
    if r.returncode != 0:
        sys.exit(f"wheel build failed:\n{r.stdout}\n{r.stderr}")
    (wheel,) = out.glob("cassandra_ai-*.whl")
    return wheel


def venv_bin(env_dir: Path) -> Path:
    return env_dir / ("Scripts" if os.name == "nt" else "bin")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--full", action="store_true", help="also install and check the [full] extra")
    args = ap.parse_args()

    with tempfile.TemporaryDirectory(prefix="cassandra-smoke-") as tmp_s:
        tmp = Path(tmp_s)
        wheel = build_wheel(tmp / "dist")
        print(f"wheel: {wheel.name}")

        tops = {name.split("/")[0] for name in zipfile.ZipFile(wheel).namelist()}
        dist_info = [t for t in tops if t.endswith(".dist-info")]
        check(tops - set(dist_info) == {"cassandra_ai"} and len(dist_info) == 1,
              "wheel ships only cassandra_ai (+ dist-info)", f"top-level entries: {sorted(tops)}")

        env_dir = tmp / "venv"
        print("creating venv ...")
        venv.create(env_dir, with_pip=True)
        bindir = venv_bin(env_dir)
        py = str(bindir / ("python.exe" if os.name == "nt" else "python"))
        cli = str(bindir / ("cassandra.exe" if os.name == "nt" else "cassandra"))
        env = {**os.environ, "CASS_DRIVER_NO_EXTENSIONS": "1"}  # skip the driver's C build
        work = tmp / "work"  # outside the repo: the source tree must not shadow the install
        work.mkdir()

        print("installing the light wheel next to cassandra-driver ...")
        r = run([py, "-m", "pip", "install", "-q", str(wheel), "cassandra-driver"], work, env)
        check(r.returncode == 0, "light wheel + cassandra-driver install", r.stderr[-2000:])
        if r.returncode != 0:
            return 1

        probe = (
            "import cassandra, cassandra_ai, pathlib; "
            "assert 'site-packages' in cassandra_ai.__file__, cassandra_ai.__file__; "
            "assert pathlib.Path(cassandra.__file__).parent.name == 'cassandra'; "
            "assert hasattr(cassandra, 'ConsistencyLevel'), 'cassandra is not the driver'; "
            "print(cassandra_ai.__version__)"
        )
        r = run([py, "-c", probe], work, env)
        check(r.returncode == 0, "`import cassandra` is cassandra-driver; cassandra_ai imports",
              r.stderr[-2000:])

        r = run([cli], work, env)
        check(r.returncode == 0 and "commands:" in r.stdout, "`cassandra` prints the command list",
              r.stderr[-2000:])

        report = work / "scan_report.md"
        r = run([cli, "scan", str(SAMPLE_LOGS), "--spec", str(SAMPLE_SPEC), "--out", str(report)],
                work, env)
        check(r.returncode == 0 and report.exists()
              and "Cassandra scan report" in report.read_text(encoding="utf-8"),
              "`cassandra scan` runs offline on the TravelPal sample", r.stdout + r.stderr)
        if r.returncode == 0:
            print(f"         {r.stdout.strip()}")

        r = run([cli, "run"], work, env)
        check(r.returncode == 1 and "cassandra-ai[full]" in r.stderr,
              "light install: `cassandra run` points at the [full] extra", r.stderr[-2000:])

        r = run([cli, "dashboard"], work, env)
        check(r.returncode == 1 and "source checkout" in r.stderr,
              "`cassandra dashboard` explains it needs a source checkout", r.stderr[-2000:])

        if args.full:
            print("installing the [full] extra ...")
            r = run([py, "-m", "pip", "install", "-q", f"{wheel}[full]"], work, env)
            check(r.returncode == 0, "[full] extra installs", r.stderr[-2000:])
            r = run([py, "-m", "pip", "check"], work, env)
            check(r.returncode == 0, "`pip check` finds no broken requirements", r.stdout[-2000:])
            r = run([py, "-c", "import cassandra_ai.mcp_server"], work, env)
            check(r.returncode == 0, "MCP server imports (mcp<2)", r.stderr[-2000:])
            r = run([py, "-c", "import importlib.metadata as m; print(m.version('opentelemetry-api'))"],
                    work, env)
            got = r.stdout.strip()
            parts = tuple(int(p) for p in got.split(".")[:3] if p.isdigit())
            check(r.returncode == 0 and parts >= OTEL_FIXED,
                  f"opentelemetry-api >= 1.45.1 (got {got or '?'})", r.stderr[-2000:])

    print()
    if _failures:
        print(f"{len(_failures)} check(s) FAILED: " + "; ".join(_failures))
        return 1
    print("all smoke checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
