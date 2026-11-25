"""Smoke-test the built wheel the way a user installs it. Needs network (PyPI).

    python scripts/smoke_install.py           # core install, next to cassandra-driver
    python scripts/smoke_install.py --full    # also install and check the [full] extra

Builds the wheel from this checkout, installs it into a throwaway venv, and runs every
check from a directory OUTSIDE the repo, so the source tree can't shadow the installed
package. Checks:

* the wheel's top-level entries are only `cassandra_ai` and its .dist-info, and the
  bundled demo sample is inside it;
* it installs next to cassandra-driver, and `import cassandra` is the driver's;
* the core install pulls no optional dependency (openai, fastapi, uvicorn);
* `cassandra demo` and `cassandra scan` work offline on the core install;
* `scan --llm` and `serve` without their extras print a one-line install hint (exit 2);
* with --full: the extras install, `pip check` passes, and the HTTP app builds.

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
EXAMPLE_LOGS = ROOT / "examples" / "logs.jsonl"
EXAMPLE_SPEC = ROOT / "examples" / "spec.json"

_failures: list[str] = []


def check(ok: bool, what: str, detail: str = "") -> None:
    print(f"  [{'ok' if ok else 'FAIL'}] {what}")
    if detail and not ok:
        print(f"         {detail}")
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
    ap = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    ap.add_argument("--full", action="store_true", help="also install and check the [full] extra")
    args = ap.parse_args()

    with tempfile.TemporaryDirectory(prefix="cassandra-smoke-") as tmp_s:
        tmp = Path(tmp_s)
        wheel = build_wheel(tmp / "dist")
        print(f"wheel: {wheel.name}")

        names = zipfile.ZipFile(wheel).namelist()
        tops = {name.split("/")[0] for name in names}
        dist_info = [t for t in tops if t.endswith(".dist-info")]
        check(tops - set(dist_info) == {"cassandra_ai"} and len(dist_info) == 1,
              "wheel ships only cassandra_ai (+ dist-info)", f"top-level entries: {sorted(tops)}")
        check("cassandra_ai/samples/travel_bot_logs.jsonl" in names,
              "wheel bundles the demo sample")

        env_dir = tmp / "venv"
        print("creating venv ...")
        venv.create(env_dir, with_pip=True)
        bindir = venv_bin(env_dir)
        py = str(bindir / ("python.exe" if os.name == "nt" else "python"))
        cli = str(bindir / ("cassandra.exe" if os.name == "nt" else "cassandra"))
        env = {**os.environ, "CASS_DRIVER_NO_EXTENSIONS": "1",  # skip the driver's C build
               "PYTHONUTF8": "1",  # the banner and reports are UTF-8, also on Windows
               "OPENAI_API_KEY": "", "CASSANDRA_API_KEY": ""}
        work = tmp / "work"  # outside the repo: the source tree must not shadow the install
        work.mkdir()

        print("installing the core wheel next to cassandra-driver ...")
        r = run([py, "-m", "pip", "install", "-q", str(wheel), "cassandra-driver"], work, env)
        check(r.returncode == 0, "core wheel + cassandra-driver install", r.stderr[-2000:])
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

        probe = ("import importlib.util as u; "
                 "print([m for m in ('openai', 'fastapi', 'uvicorn') if u.find_spec(m)])")
        r = run([py, "-c", probe], work, env)
        check(r.returncode == 0 and r.stdout.strip() == "[]",
              "core install pulls no optional dependency", r.stdout + r.stderr)

        r = run([cli, "demo", "--out", str(work / "demo.html")], work, env)
        check(r.returncode == 0 and (work / "demo.html").exists() and "8 of 50" in r.stdout,
              "`cassandra demo` runs offline (8 of 50 flagged)", r.stdout + r.stderr[-2000:])

        report = work / "scan.md"
        r = run([cli, "scan", str(EXAMPLE_LOGS), "--spec", str(EXAMPLE_SPEC), "--out", str(report)],
                work, env)
        check(r.returncode == 0 and report.exists(),
              "`cassandra scan` runs offline on examples/logs.jsonl", r.stdout + r.stderr[-2000:])

        r = run([cli, "scan", str(EXAMPLE_LOGS), "--llm", "--out", str(work / "x.md")], work, env)
        check(r.returncode == 2 and "cassandra-ai[llm]" in r.stderr,
              "core install: `scan --llm` points at the [llm] extra", r.stderr[-2000:])

        r = run([cli, "serve"], work, env)
        check(r.returncode == 2 and "cassandra-ai[serve]" in r.stderr,
              "core install: `serve` points at the [serve] extra", r.stderr[-2000:])

        if args.full:
            print("installing the [full] extra ...")
            r = run([py, "-m", "pip", "install", "-q", f"{wheel}[full]"], work, env)
            check(r.returncode == 0, "[full] extra installs", r.stderr[-2000:])
            r = run([py, "-m", "pip", "check"], work, env)
            check(r.returncode == 0, "`pip check` finds no broken requirements", r.stdout[-2000:])
            r = run([py, "-c", "from cassandra_ai.server import create_app; create_app()"],
                    work, env)
            check(r.returncode == 0, "HTTP app builds with [serve]", r.stderr[-2000:])
            # Builds the client only; nothing is sent, so a placeholder key is enough.
            llm_env = {**env, "OPENAI_API_KEY": "placeholder",
                       "OPENAI_BASE_URL": "http://127.0.0.1:9/v1"}
            r = run([py, "-c", "import cassandra_ai.llm as l; l._client()"], work, llm_env)
            check(r.returncode == 0, "LLM client builds with [llm]", r.stderr[-2000:])

    print()
    if _failures:
        print(f"{len(_failures)} check(s) FAILED: " + "; ".join(_failures))
        return 1
    print("all smoke checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
