"""Thin wrapper — the runner now lives in the installed package.

Kept so the documented `python scripts/run_pipeline.py` command keeps working. The real
implementation is `cassandra/run_once.py` (shipped in the wheel; `scripts/` is not).
"""

from cassandra.run_once import main

if __name__ == "__main__":
    main()
