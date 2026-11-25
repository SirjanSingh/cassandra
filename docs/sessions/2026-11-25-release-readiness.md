# Session log: 2026-11-25 — make the focused 0.4.0 releasable

Branch: `claude/project-thread-9g4qva`, cut from `focus/answer-check` @ `cedb317`.
Nothing was merged, force-pushed, deleted or published.

## Scope

A consolidated plan (all branches) recommended `focus/answer-check` as the canonical line,
but found it not releasable: it still installed a top-level `cassandra` package (the
cassandra-driver collision), its dependencies were floor-only, and no branch had CI. The
fixes existed only on `claude/loving-planck-llm1bd`, on top of the old pipeline. The
founder asked to proceed with those engineering steps tonight, carefully.

## What changed and why

1. **Import package `cassandra` → `cassandra_ai`.** `git mv` plus a scripted rewrite of
   imports, module paths and living docs. Brand strings, the `cassandra` command and the
   PyPI name are unchanged. Session notes are historical and were not rewritten.
2. **Dependency caps + one version source.** Every runtime and dev dependency is capped at
   the next major above what the suite passes with (openai 3.59, fastapi 0.165, pydantic
   2.14…); ruff 0.17.6 and mypy 2.4.1 pinned; hatch reads `__version__`.
3. **Pinned ruff rule set (E, F, W, I).** ruff 0.17 enables many more rules by default (21
   findings on this branch, which its notes recorded as "clean" under an older ruff). The 7
   findings under the pinned set were fixed; one was a stale `--judge-model` help text that
   still described the old `.env` override.
4. **CI** (`.github/workflows/ci.yml`): ruff, mypy, pytest and the smoke install on
   ubuntu/macos/windows × py3.11/3.13, plus build + `twine check --strict`. Runs on PRs and
   pushes to `main`.
5. **`scripts/smoke_install.py` + `tests/test_packaging.py`**, ported from loving-planck and
   rewritten for this package (demo/scan offline, `[llm]`/`[serve]` hints, no optional deps
   in the core install, co-install with cassandra-driver). The `system_override` fix from
   loving-planck was not ported: this branch has no replay endpoint or Patient.
6. **Rule layer compares field values** (open item from the Nov 10 note and the Aug 5
   audit). New `FailureClass.CONTRADICTED` → finding kind `contradicted`. Conservative by
   design: it flags only when every successful result is comparable (text containment,
   number within 0.5%, month+day across ISO and named dates) and disagrees; anything else
   still counts as backed. `match_values: false` opts a rule out. Extractors now check every
   match, not only the first.
7. Docs: `CHANGELOG.md` (new, with release steps), README, `docs/ARCHITECTURE.md`, `CLAUDE.md`.

## Verification

- `pytest`: 57 passed (43 before + 5 packaging + 9 rule/engine). `ruff check .` clean,
  `mypy cassandra_ai scripts` clean.
- `python scripts/smoke_install.py --full`: all 13 checks pass (Linux, py3.13).
- `python -m build` + `twine check --strict`: PASSED; wheel top level is only
  `cassandra_ai` + dist-info.
- `cassandra demo`: still 8 of 50 flagged (the TravelPal spec uses claim-type rules only, so
  value matching doesn't touch it). `examples/logs.jsonl`: still 3 of 4; `o1` is now also
  caught by the rule ("FedEx" vs UPS), not only by the number check.
- Not verified here: macOS/Windows (CI covers them); no LLM calls were made, so claim-check
  accuracy is unchanged and `docs/EVIDENCE.md` needs no update.

## Open items

- **[human]** Review and merge the PR; publish 0.4.0 and yank 0.3.0 (`CHANGELOG.md`).
- Second-pass verification to cut claim-check false alarms (ROADMAP Phase 1). Needs an API
  key and RAGTruth train runs; not started.
- "Tool errored, bot said done" check (80.4% precision in the Nov 5 tau-bench probe).
- Redact PII in reports before sending audits.
- The rule reports only the first failing claim per turn; reporting all would be clearer.
- Rename the product before any public launch (ASF trademark).
