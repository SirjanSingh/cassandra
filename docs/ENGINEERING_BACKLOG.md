# Engineering backlog (2026-11-05)

> Part of the strategy set. Master document: [PRODUCT_VISION_AND_COMPANY_ROADMAP.md](PRODUCT_VISION_AND_COMPANY_ROADMAP.md).
> Features referenced as F-xx are in [PRODUCT_REQUIREMENTS.md](PRODUCT_REQUIREMENTS.md). Debt items TD-xx
> and security items SEC findings are in the master document §10–§11.
>
> **Base branch for all work:** the consolidation branch (see [BRANCH_AUDIT.md](BRANCH_AUDIT.md) §6), built
> from `feature/nli-and-hindi` @ `23994bf`. File paths are relative to that tree. After PKG-1, read
> `cassandra/` as `cassandra_ai/`.
>
> **Conventions:**
>
> - Priority: P0 = blocks the 30-day plan · P1 = needed for MVP/alpha · P2 = beta/commercial · P3 = later.
> - Complexity: S ≤ 1 day · M 2–4 days · L 1–2 weeks · XL > 2 weeks (part-time founders: multiply calendar time by about 2).
> - Every task ends with green CI (once CI-1 exists) and a session-note entry (CLAUDE.md protocol).
> - Tasks marked **[human]** need an explicit founder decision or approval because they are destructive or outward-facing.

---

## Milestones and critical path

| Milestone | Target (calendar) | Contents | Exit criterion |
|---|---|---|---|
| **M0: One releasable branch** | Nov 6 – Nov 12 | CON-1..4, PKG-1..5, CI-1, SEC-1, SEC-2 | 0.4.0 on PyPI installs cleanly next to `cassandra-driver`; CI green on 3 OSes |
| **M1: Trustworthy scan** | Nov 10 – Nov 26 | CHK-1, CHK-2, CHK-3, CHK-5, GOLD-1, CI-2, SEC-5, VAL-1, VAL-2 | Published per-check precision ≥ 90% (unsupported-claim) / ≥ 80% (swallowed-error) on the golden set; partner reports produced with it |
| **M2: Stranger-ready onboarding** | Nov 24 – Dec 12 | INIT-1, INIT-2, INIT-4, DOC-1 | A non-founder gets a ≥ 70%-decided contract in < 30 min, timed |
| **D1: Decision gate** | Fri Dec 4 | Evidence from E1–E3 (master §15) | Founders choose: continue / re-target detectors / stop (written in `docs/sessions/`) |
| **M3: Regression loop** | Dec – Jan | RPL-1..4, GATE-1, CHK-4/6/8, ING-1 | A design partner runs `test` in CI with cassettes for 4 weeks |
| **M4: Design-partner server** | Feb – Apr | MON-1..6 | 3 teams on continuous verification; ≥ 1 paying |

**Critical path (engineering):**

`CON-1 → PKG-1 → PKG-2/3 → CI-1 → CHK-1 → CHK-2/3/5 + GOLD-1 → INIT-1 → INIT-2 → [D1] → RPL-1 → RPL-2 → RPL-3 → RPL-4 → GATE-1 → MON-1`

**Critical path (business). It runs in parallel and must not wait for engineering:**

`VAL-1 → outreach (today) → logs from partners → concierge contract + scan → hand-checked reports → reactions → D1`

The current `scan` with founder-written contracts is good enough to start partner reports this week. M1
makes those reports trustworthy; it doesn't gate sending the first messages.

---

## Epic CON: consolidate the repository

### CON-1: Create the consolidation branch and merge Sirjan's line
- **Description:**
  - Branch `consolidation/2026-11` from `origin/feature/nli-and-hindi`.
  - Merge `origin/task0-grounding-base-rate`. It brings `docs/SECURITY_AUDIT.md`, `docs/TASK0_GROUNDING_BASE_RATE.md`,
    the 2026-08-05 session note, `scripts/stress_probe.py`, `scripts/task0_*.py`, and CLAUDE.md's
    "Known-broken" and "Repository structure" sections.
- **User impact:** One source of truth. The product line finally carries the audits and the evidence.
- **Technical details:**
  - Expected conflicts: `CLAUDE.md`, `docs/CODEBASE_MAP.md`.
  - Keep `nli-and-hindi`'s `docs/archive/` layout.
  - Place task0's root-level docs per that layout: audits and measurement in `docs/`, hackathon docs in `docs/archive/`.
  - Keep both CLAUDE.md protocol versions merged: task0's has the stricter "reconcile CLAUDE.md" step.
- **Files:** `CLAUDE.md`, `docs/**`, `scripts/**`.
- **Dependencies:** none. **Priority:** P0. **Complexity:** S–M.
- **Acceptance criteria:**
  - `git merge-base --is-ancestor origin/task0-grounding-base-rate HEAD` is true;
  - `pytest` passes (with PKG-3's pin);
  - no file from either tip is lost (`git ls-tree` diff shows only intended moves).
- **Verification:** run the file-set comparison in BRANCH_AUDIT §3 again; run `pytest`.

### CON-2: Bring over the strategy set and the market doc; make README honest
- **Description:**
  - Add this strategy set and `docs/TAM_SAM_SOM.md` (from `main`, with a header noting its figures are
    third-party estimates not re-verified).
  - Rewrite README's top section so it doesn't claim a live hosted demo or "supervises any agent" until those are true.
- **User impact:** First-time visitors aren't misled. Credibility is the brand.
- **Files:** `README.md`, `docs/*.md`. **Deps:** CON-1. **P0. S.**
- **Acceptance criteria:** README states the current scope (offline scan of JSONL logs + an experimental Phoenix pipeline) and links POSITIONING and the master doc.
- **Verification:** a non-founder reads the README and states what the product does in one sentence. Their answer matches.

### CON-3 [human]: Fast-forward `main`, archive-tag and delete merged branches
- **Description:**
  - After M0 is green, fast-forward `main` to the consolidation branch.
  - Push `archive/<branch>` tags for `cassandra-v2`, `task0-grounding-base-rate`, `multi-agent-v1`,
    `demo/mock-bot-integration`, `feature/ci-prompt-gate`, `feature/incident-postmortems`. Then delete those branches.
- **User impact:** Contributors see one line of history.
- **Deps:** CON-1, CI-1. **P0. S.**
- **Acceptance criteria:** `git branch -r` shows `main` plus active feature branches only; every former tip is reachable from a tag.
- **Verification:** `git tag -l 'archive/*'`; `git rev-parse archive/<name>` equals the old tip SHA in BRANCH_AUDIT §3.

### CON-4: Reconcile the CLAUDE.md known-broken list with the code
- **Description:** Re-verify each of the 6 known-broken items (all still present per BRANCH_AUDIT §5). Add the items this audit found:
  - NLI has no caller;
  - the live `diagnose` is LLM-only;
  - the adapter template fails open and uses non-constant-time `!=`;
  - `mcp` 2.x breaks `[full]`;
  - the wheel ships top-level `patient`/`dashboard`;
  - replay executes real tools;
  - there is no CI.
- **Files:** `CLAUDE.md`. **Deps:** CON-1. **P0. S.**
- **Acceptance criteria:** every listed item cites a file:line that exists; nothing fixed remains listed.
- **Verification:** open each cited location.

---

## Epic PKG: packaging and release

### PKG-1: Rename the import package to `cassandra_ai`
> **Status: ✅ done (2026-11-05, branch `claude/loving-planck-llm1bd`, unreleased 0.4.0).** Verified by `scripts/smoke_install.py`: co-installs with cassandra-driver 3.30.1, and `import cassandra` resolves to the driver.

- **Description:**
  - Move `cassandra/` → `cassandra_ai/` and update all imports, entry points, tests, docs, Dockerfiles and examples.
  - The CLI command stays `cassandra`.
  - Do **not** ship a `cassandra` shim package: it would recreate the collision.
- **User impact:** Installing us no longer breaks environments that use the Apache Cassandra driver, which
  is common in exactly the backend teams we target.
- **Technical details:**
  - `git mv cassandra cassandra_ai`;
  - `sed` over `from cassandra`, `import cassandra`, `cassandra.` module strings (including `patch("cassandra.…")` in tests and `[project.scripts]`);
  - update `[tool.hatch.build.targets.wheel] packages`.
- **Files:** `cassandra/**`, `tests/**`, `pyproject.toml`, `deploy/*`, `functions/trace_poller/main.py`, `examples/*`, `scripts/*`, `poc/travelpal/*.py`, `docs/**`, `CLAUDE.md`.
- **Deps:** CON-1. **P0. M.**
- **Acceptance criteria:**
  - in one fresh venv, `pip install ./dist/*.whl cassandra-driver` then `python -c "import cassandra_ai, cassandra; assert 'cassandra_ai' not in cassandra.__file__"` succeeds;
  - `cassandra scan` works.
- **Verification:** CI smoke job (PKG-5) runs exactly this.

### PKG-2: Stop shipping `patient` and `dashboard` as top-level packages
> **Status: ✅ done, implemented more narrowly than described below.** The directories stay where they are (so every documented `uvicorn patient.agent:app` / `dashboard.main:app` command, the Dockerfile and the tests keep working from a checkout). They are only excluded from the wheel, and `cassandra dashboard` explains the source-checkout requirement on a pip install. Moving them to `examples/shopbot/` and `apps/dashboard/` remains optional.

- **Description:** Move `patient/` → `examples/shopbot/` and `dashboard/` → `apps/dashboard/`. Exclude both from the wheel. The `cassandra dashboard` subcommand prints how to run it from a checkout.
- **User impact:** We don't squat on generic import names in users' environments.
- **Files:** `pyproject.toml`, `patient/**`, `dashboard/**`, `cassandra_ai/cli.py`, `deploy/cloudrun.Dockerfile`, tests importing `patient`.
- **Deps:** PKG-1. **P0. S–M.**
- **Acceptance criteria:** the built wheel's top-level entries are exactly `cassandra_ai` + `.dist-info`.
- **Verification:** `python -c "import zipfile,glob; print({n.split('/')[0] for n in zipfile.ZipFile(glob.glob('dist/*.whl')[0]).namelist()})"`.

### PKG-3: Bound fast-moving dependencies; pin the dev toolchain
> **Status: ✅ done, except the constraints file (deferred until CI-1 exists).** Every runtime dependency is capped at the next major. `ruff==0.17.3` and `mypy==2.4.1` are pinned. `google-adk` moved to a new `[adk]` extra: its `opentelemetry-api<=1.44` cap blocked the CVE-2026-114603 fix, and `[full]` now resolves opentelemetry-api 1.45.2. Guarded by `tests/test_packaging.py`.

- **Description:**
  - `mcp>=1.2,<2` (2.x removed `mcp.server.fastmcp`; verified 2026-11-05 with mcp 2.3.0);
  - add `<next-major` caps on `google-genai`, `google-adk`, `openai`, `fastapi`;
  - pin `ruff==<current>` and `mypy==<current>` in `dev`;
  - add a `constraints/dev.txt` (or `uv.lock`) used by CI.
- **User impact:** `pip install "cassandra-ai[full]"` works today and keeps working.
- **Files:** `pyproject.toml`, `constraints/`. **Deps:** none. **P0. S.**
- **Acceptance criteria:** fresh `pip install -e ".[dev]"` → `pytest` 116+ passed with no manual pins.
- **Verification:** CI from a clean cache.

### PKG-4 [human]: Release 0.4.0; yank 0.3.0
> **Status: ⏳ waiting on a founder.** The code and CHANGELOG are ready; steps are in `CHANGELOG.md` ("Release steps").

- **Description:** Build and `twine check`. Publish 0.4.0 with a CHANGELOG entry for the rename. Then yank 0.3.0 on PyPI with the reason "installs top-level `cassandra` package that conflicts with cassandra-driver; use ≥0.4.0".
- **Deps:** PKG-1..3, CI-1. **P0. S.**
- **Acceptance criteria:** `pip install cassandra-ai` resolves 0.4.0. 0.3.0 shows as yanked.
- **Verification:** a fresh venv from PyPI, not a local wheel.

### PKG-5: Fresh-venv smoke tests (light and full)
> **Status: ✅ done as `scripts/smoke_install.py [--full]`.** Python rather than bash, so it also runs on Windows. All 11 checks pass.

- **Description:** Add `scripts/smoke_install.sh`. It:
  - builds the wheel;
  - installs light into an empty venv and runs `cassandra`, `cassandra scan examples/sample_logs.jsonl --spec examples/sample_contract.json`;
  - asserts that `scan --judge` prints the `[full]` hint;
  - installs `[full]` and asserts `cassandra mcp --help` exits 0;
  - co-installs `cassandra-driver`.
- **Deps:** PKG-1, PKG-2. **P0. S.**
- **Acceptance criteria:** the script exits 0 on Linux, macOS and Windows runners.
- **Verification:** CI-1 job.

---

## Epic CI: continuous integration and quality gates

### CI-1: GitHub Actions for tests, lint, types, build, smoke
- **Description:**
  - `.github/workflows/ci.yml`: matrix Python 3.11/3.12/3.13 on ubuntu, plus 3.12 on windows/macos;
  - steps: install with constraints → `pytest -q` → `ruff check .` (pinned) → `mypy cassandra_ai` (core modules only at first; add a baseline file) → `python -m build` → `twine check` → PKG-5 smoke.
- **User impact:** The product that sells a CI gate has one. Regressions like the `mcp` 2.x break are caught before users see them.
- **Files:** `.github/workflows/ci.yml`. **Deps:** PKG-3 (pins). **P0. M.**
- **Acceptance criteria:** CI is required on `main`, and it fails on any test, lint or smoke failure.
- **Verification:** open a PR that breaks a test and confirm it's blocked.

### CI-2: Precision regression job on the golden corpus
- **Description:** `pytest benchmarks/` computes precision and recall per check on GOLD-1 and fails below thresholds stored in `benchmarks/thresholds.yaml`.
- **Deps:** GOLD-1, CHK-2, CHK-5. **P1. S.**
- **Acceptance criteria:** lowering a regex's precision in a test PR fails CI with a per-check table.
- **Verification:** a deliberately broken extractor PR.

### CI-3: Dependency hygiene
- **Description:** Dependabot (pip + npm for `web/`) and a weekly `pip-audit` workflow.
- **Deps:** CI-1. **P1. S.**
- **Acceptance criteria:** the weekly job runs. Advisories open issues.

---

## Epic CHK: the check library (verdict correctness)

### CHK-1: Contract schema v1 with a GroundingSpec migration
- **Description:** Define `cassandra_ai/contract/schema.py` (Pydantic) and publish a JSON Schema. Sections:
  - **`tools`**: name, kind (`read`/`write`), success predicate (`key == value`, `not startswith "Error"`, `http_status < 400`), fields;
  - **`claims`**: id, extractor (regex for now; F-26 later), value type (`money|date|number|string|enum`), source `tool.field`, normaliser;
  - **`completion_claims`**: phrases or extractor → write tool;
  - **`declines`**;
  - **`policies`**: placeholder for CHK-7.

  `load_contract()` accepts the old `GroundingSpec` JSON and converts it, so `poc/travelpal/grounding_spec.json` loads unchanged.
- **User impact:** One readable file describes what "correct" means for an agent.
- **Files:** new `cassandra_ai/contract/`; `cassandra_ai/grounding.py` (kept as a compatibility layer); `cassandra_ai/scan.py`; `docs/SCAN.md`.
- **Deps:** PKG-1. **P0. M.**
- **Acceptance criteria:**
  - the TravelPal and ShopBot specs load and round-trip;
  - the JSON Schema validates them;
  - an invalid regex is reported with its claim id (today it's silently skipped: `grounding.py:70-71`).
- **Verification:** unit tests; `cassandra scan` on `poc/travelpal/runs_heldout.jsonl` still reports 8 of 50 (same as 0.3.0) before CHK-2 changes semantics.

### CHK-2: Value-matched unsupported-claim check
- **Description:** A claim is supported only if its normalised value equals (or is within tolerance of) the
  value in the cited tool field of a successful call. Normalisers:
  - money: currency symbol/code + amount, with comma/decimal handling;
  - dates: ISO, "June 20", weekday names resolved against ledger dates;
  - numbers with units;
  - case-insensitive strings, with synonyms in the contract.
- **User impact:** Fixes the false-OK class (DHL result grounding an answer of "UPS"). Without this, every "OK" verdict is unreliable.
- **Technical details:**
  - replaces `grounding.py:111-114` (non-null test) and `:139-141` (any success);
  - evidence = `{call_index, field, expected, actual}`;
  - unparseable value → `abstain` with a reason, never `ok`.
- **Files:** `cassandra_ai/checks/unsupported_claim.py`, `cassandra_ai/checks/normalize.py`, tests.
- **Deps:** CHK-1. **P0. L.**
- **Acceptance criteria:**
  - new unit tests for: carrier mismatch → flagged; refund "45 days" vs policy "30-day" → flagged; currency formatting variants → OK;
  - GOLD-1 unsupported-claim precision ≥ 90%;
  - TravelPal held-out recall ≥ the 0.3.0 baseline (73%).
- **Verification:** CI-2 table in the PR description.

### CHK-3: All matches, per-claim declines, user-echo exclusion
- **Description:**
  - Use `re.finditer`, not `re.search` (`grounding.py:69`).
  - Evaluate declines per claim span, so "I can't provide the refund policy; orders usually ship in 2 days" isn't a hallucination (`grounding.py:85-96`).
  - Values that appear in the user's own message are echoes, not claims (TravelPal false positive q081).
- **Files:** `cassandra_ai/checks/extract.py`. **Deps:** CHK-1. **P0. M.**
- **Acceptance criteria:**
  - tests for multi-claim answers, mixed decline + claim, and an echoed amount;
  - q081 is no longer flagged.
- **Verification:** golden set + CI-2.

### CHK-4: Argument-aware call matching
- **Description:** A claim about an entity (city, order id, date) is supported only by calls whose args or result reference that entity, rather than by any call to the same tool (`grounding.py:77-78`). Contract: `claims[].entity_from: tool.arg|tool.result_field`.
- **User impact:** Starts catching the "wrong place / wrong date" misses (TravelPal: 5 misses on the original set, 4 on held-out).
- **Deps:** CHK-2. **P1. M.**
- **Acceptance criteria:** the TravelPal "Bombay, United States" and weekday cases are flagged, with no new false positives on the golden set.

### CHK-5: Swallowed-tool-error check
- **Description:** If a `write` tool's result matches its failure predicate and the next assistant text contains a completion claim, flag `swallowed_error` with evidence (the failing call + the claim span).
- **User impact:** The highest-precision signal found in this audit (80.4% on tau-bench; 0.8% false-flag rate on successful trajectories). Cheap, and it maps to a costly failure.
- **Files:** `cassandra_ai/checks/swallowed_error.py`. **Deps:** CHK-1. **P0. S.**
- **Acceptance criteria:**
  - unit tests;
  - on the tau-bench reproduction (`benchmarks/tau_anatomy.py`, which downloads data at runtime), precision ≥ 75% and the flagged count is reported.
- **Verification:** CI-2 (tau-bench job optional/nightly because of the download).

### CHK-6: Claimed-vs-executed action check
- **Description:** Extract typed completion claims (`{action, entity_id}`) and match them to executed write calls by tool and key argument. Flag: claim with no matching successful call, or a matching call with a different entity id.
- **Deps:** CHK-1, CHK-5. **P1. M.**
- **Acceptance criteria:** ≥ 80% precision on a 50-turn labelled tau-bench sample (GOLD-1 extension).

### CHK-7: Action-policy predicates (gated on decision D1)
- **Description:**
  - A small deterministic DSL: `when: tool == cancel_order` → `require: ledger.last(get_order, args.order_id).status == "pending"`.
  - Evaluated over the ledger before the write. Post-hoc only, never in-path.
  - The tau-bench retail/airline policies are the first test bed: their policies are written in the system prompt.
- **User impact:** Targets the dominant failure in transactional agents (94.6% of tau-bench failures had wrong writes).
- **Deps:** CHK-1, D1. **P1. L.**
- **Acceptance criteria:** precision ≥ 80% on a labelled tau-bench retail sample. Report recall against reward-failed trajectories.

### CHK-8: Derived-value awareness
- **Description:** Treat sums, differences and per-unit splits of ledger values (bounded search, depth 2) as supported. Task 0 found 82.4% of non-ledger numbers were arithmetic.
- **Deps:** CHK-2. **P1. M.**
- **Acceptance criteria:** on tau-bench, the unsupported-money false-flag rate on passed trajectories drops by ≥ 50% versus CHK-2 alone.

### GOLD-1: Golden labelled corpus
- **Description:** `benchmarks/` with:
  - TravelPal 98 + 50 turns and existing labels (map labels → expected check outcomes);
  - ShopBot unit cases;
  - a script that downloads tau-bench trajectories and samples 50 turns per check for founder labelling. Store labels with labeller id and date; never commit the third-party data itself.
- **User impact:** Precision claims become reproducible, and the corpus doubles as our regression suite.
- **Deps:** CHK-1. **P0. M.**
- **Acceptance criteria:** `pytest benchmarks/` prints a per-check precision/recall table, with sample sizes.
- **Verification:** two founders label an overlapping 20-turn subset. Report agreement (Cohen's κ).

---

## Epic INIT: onboarding without hand-written regex

### INIT-1: Deterministic contract miner
- **Description:** `cassandra init logs.jsonl -o contract.yaml`. From the ledgers:
  - list tools with call counts;
  - infer the success predicate: a boolean key that's present and varies, an `Error` prefix, or an HTTP status;
  - classify read/write by name verbs (`get|list|find|search` vs `cancel|update|create|book|refund|send|modify|return|exchange`) and argument shapes;
  - enumerate result fields with types and sample values.

  Propose claim entries for fields whose sample values appear verbatim in answers (value co-occurrence), with extractors generated from the value type. Emit YAML with comments explaining each inference.
- **User impact:** Removes the adoption blocker: hand-writing regex cost us about 1 h per bot and stops strangers entirely.
- **Files:** new `cassandra_ai/init/miner.py`, `cassandra_ai/cli.py`.
- **Deps:** CHK-1. **P0. L.**
- **Acceptance criteria:**
  - on TravelPal `runs.jsonl` with the spec deleted, the mined contract reaches ≥ 80% of the hand-written spec's decided-turn coverage and ≥ 90% of its precision on held-out;
  - on a tau-bench retail sample it correctly marks the 7 write tools.
- **Verification:** benchmark script comparing mined vs hand-written contracts.

### INIT-2: Backtest / coverage report
- **Description:** `init` (and `scan --coverage`) prints:
  - decided %;
  - flagged % per check;
  - top abstain reasons ("claim matched no rule", "no tool_calls in turn", "unparseable value");
  - 10 sample flags for review.

  Optional `--judge` adds the disagreement set (rule vs LLM).
- **Deps:** INIT-1. **P0. M.**
- **Acceptance criteria:** a non-founder can say from the output alone which claims are uncovered.

### INIT-3: Optional LLM proposer
- **Description:** `init --propose` sends a *sample* of turns (default 30, redacted by SEC-5) to the configured LLM. It's few-shot prompted with the ShopBot, TravelPal and fintech example contracts, and proposes extractors and declines for uncovered claims. Output is marked `proposed: true` and needs `contract lint --accept`.
- **Deps:** INIT-1, SEC-5. **P1. M.**
- **Acceptance criteria:** coverage improves ≥ 10 points on TravelPal without a precision drop > 5 points.

### INIT-4: `contract lint` and `explain`
- **Description:**
  - `lint`: invalid regex, extractors that never fire on the sample, overlapping extractors, unknown tool names.
  - `explain <turn-id>`: shows each claim, its extractor, the matched call, and the decision.
- **Deps:** CHK-1. **P1. M.**
- **Acceptance criteria:** every flag in a report can be explained by one command.

### DOC-1: The 5-minute quickstart
- **Description:** `examples/sample_logs.jsonl` (TravelPal held-out, 50 turns), `examples/sample_contract.yaml`, and `docs/QUICKSTART.md`: install → init → scan → explain → keep, with no keys.
- **Deps:** INIT-1, INIT-4. **P0. S.**
- **Acceptance criteria:** timed run by someone outside the team in < 5 min.

---

## Epic RPL: safe replay and regression tests

### RPL-1: Cassette format + Python recorder/replayer
- **Description:**
  - A `@cassandra_ai.tool` decorator (and `wrap_tools(dict)`) records `(name, args) → result` into
    `cassettes/<case>.jsonl` in record mode and serves them in replay mode.
  - **Strict:** an unexpected call or argument mismatch raises `CassetteMismatch`, which is recorded as a
    test failure "agent changed its tool plan".
  - Matching is by order + name + normalised args. Configurable to name-only for tolerant mode.
- **User impact:** Regression tests never touch production systems and don't flake on live data.
- **Deps:** PKG-1. **P0. L.**
- **Acceptance criteria:**
  - ShopBot and TravelPal tools wrapped; replaying a recorded session makes **zero** network calls (asserted with a socket guard in the test);
  - 5 replays at temperature 0 give identical tool plans.
- **Verification:** unit + integration tests with `pytest-socket` or an equivalent guard.

### RPL-2: Adapter contract v2 (default-deny replay mode) + conformance checker
- **Description:**
  - Replace the `system_override` + `session_id="test"` convention with a signed replay request:
    `X-Verify-Replay: HMAC(secret, body)`, body `{message, history, prompt_override?, cassette_id}`.
  - No secret configured → replay mode is refused (fail closed).
  - Update `examples/adapter_template.py` to implement it with `hmac.compare_digest`.
  - Add `cassandra adapter check URL --secret-env VAR`, which verifies:
    1. an unsigned override is ignored;
    2. a signed one is honoured;
    3. replay mode doesn't call real tools (the adapter must echo the cassette id it served).
- **User impact:** Closes the "anyone can rewrite my production prompt" hole customers would copy from our template.
- **Deps:** RPL-1, SEC-1. **P0. M.**
- **Acceptance criteria:** all three conformance checks pass against the updated template, and the old template fails check 1 when no secret is set.

### RPL-3: `keep`: turn a confirmed failure into a regression case
- **Description:** `cassandra keep <turn-id> --from report.json` writes `cases/<id>.yaml`:
  `{conversation_prefix, user_message, cassette_ref, assertions: [the failing check must pass; must_not_decline_if_tools_succeeded: true]}`.
  If the source log already has full tool results, the cassette is built from the log, so no re-recording is needed.
- **Deps:** RPL-1, CHK-2/5. **P0. M.**
- **Acceptance criteria:** a kept TravelPal case replays and reproduces the original failure under the baseline prompt.

### RPL-4: `test`: run the suite, deterministic scoring, CI exit codes
- **Description:** `cassandra test [--prompt FILE] [--model NAME]` runs every case via the in-process
  recorder or the HTTP adapter, scores with checks, and emits a summary + JUnit XML. Exit 1 on any regression
  versus the stored baseline. Includes `cases/normal/` (answerable questions that must still be answered) so
  "refuse everything" fails.
- **Replaces:** the live, LLM-scored `gate.py` path, which stays available as `test --live` for read-only agents.
- **Deps:** RPL-3. **P0. M.**
- **Acceptance criteria:**
  - on TravelPal, the baseline prompt fails the kept cases and Cassandra's candidate prompt passes them;
  - a "refuse everything" prompt fails `normal/`.

### RPL-5: Recorder integration for one agent framework
- **Description:** First target is the OpenAI Agents SDK, a likely ICP framework; confirm with partners in week 2. A one-line hook records turns to Turn JSONL **and** cassettes.
- **Deps:** RPL-1. **P1. M.**
- **Acceptance criteria:** the framework's official example agent produces scannable logs with one added line.

### GATE-1: GitHub Action
- **Description:** A composite action wrapping `cassandra test`, uploading JUnit, and posting a PR comment table (cases, pass/fail, check, evidence link). Lives in this repo under `action/` until a dedicated repo is warranted.
- **Deps:** RPL-4, CI-1. **P1. S.**
- **Acceptance criteria:** used in this repo's own CI against `examples/shopbot` cases.

---

## Epic ING: ingestion

### ING-1: OpenInference / Phoenix export importer (file-based)
- **Description:** `cassandra scan --format openinference spans.jsonl` groups spans by trace into Turns. It reuses `phoenix_mcp._extract_tool_calls` (move it to `ingest/openinference.py`, keeping it pure).
- **Deps:** CHK-1. **P1. M.**
- **Acceptance criteria:** a Phoenix export of ShopBot traffic scans to the same verdicts as the JSONL path.

### ING-2: OTLP-JSON importer (`gen_ai.*`, `execute_tool`)
- **Deps:** ING-1. **P2. M.**
- **Acceptance criteria:** the Sentry/OTel sample traces scan correctly. Unknown attributes are tolerated.

### ING-3: Langfuse export importer
- **Deps:** ING-1. **P2. M.**

---

## Epic SEC: security hardening

### SEC-1: Fail-closed override in the Patient and the adapter template
> **Status: ✅ done (2026-11-05, unreleased 0.4.0).** Beyond the spec below:
> - agents now report `override_applied`;
> - `ask_patient` raises `OverrideRejectedError` on a refused override, and the gate exits 2, so a misconfigured secret can't silently score the live prompt as the candidate;
> - the token compare is on bytes (the str form raised `TypeError` on non-ASCII header values);
> - secrets are whitespace-stripped.
>
> 5 of the new tests fail against the original code.

- **Description:** In both `patient/agent.py:63-69` and `examples/adapter_template.py:84-89`, honour the override only when a secret is configured **and** `hmac.compare_digest(token, secret)` holds. No secret means never.
- **User impact:** Customers copying the template no longer ship an unauthenticated system-prompt override.
- **Deps:** none. **P0. S.**
- **Acceptance criteria:** tests for: no secret → ignored; wrong token → ignored; right token → honoured. `tests/test_patient_security.py` extended to the template.
- **Verification:** `pytest tests/test_patient_security.py`.

### SEC-2 [human]: Lock or take down the public demo
- **Description:** README advertises a public demo URL (not probed in this audit). Decide:
  - (a) take it down; or
  - (b) keep it with:
    - auth on `/ask` and `/selfeval`;
    - `CASSANDRA_LOOP_ENABLED=false` on web instances;
    - `--max-instances=1` for any instance that runs the loop;
    - a per-IP rate limit;
    - `REPLAY_SHARED_SECRET` set.
- **Deps:** none. **P0. S (ops).**
- **Acceptance criteria:** an unauthenticated POST to `/ask` returns 401, or the URL is gone and the README is updated.

### SEC-3: Secrets and supply-chain hygiene for the Phoenix path
- **Description:**
  - pass `PHOENIX_API_KEY` via the env of the child process, not `--apiKey` argv (`phoenix_mcp.py:60-61`);
  - pin `@arizeai/phoenix-mcp@<version>` (`config.py:31`);
  - change `load_dotenv(override=True)` → `override=False` (`config.py:10,139`).
- **Deps:** none. **P1. S.**
- **Acceptance criteria:** `ps` during a run shows no key. The config test shows that injected env beats `.env`.

### SEC-4: Patcher prompt-injection hardening and score-before-persist
- **Description:**
  - Wrap traffic in explicit data delimiters with an instruction that its content is untrusted data (`patcher.py:53`).
  - Don't call `create_prompt_version` until the candidate is scored and `delta > 0` on kept + normal cases (`patcher.py:70`, `loop_agent.py:55`).
  - Add a test with an injected instruction in the triggering input. The candidate must not contain it.
- **Deps:** RPL-4 (for scoring). **P2. M.**

### SEC-5: Report redaction
- **Description:** `--redact` with built-in patterns (emails, phones, card-like numbers, IBAN-like strings) plus contract-defined patterns, applied to report output and to anything sent to an LLM (`--judge`, `--propose`). Print a warning that reports contain customer text when redaction is off.
- **Deps:** CHK-1. **P1. S.**
- **Acceptance criteria:** a test log with PII produces a report with none of the planted values.

### SEC-6: Safe PR branch handling
- **Description:** In `pr.py:142-143`, check the fallback `git switch` return code and refuse on a dirty tree or when the current branch is the base.
- **Deps:** none. **P2. S.**

---

## Epic PIPE: legacy Phoenix pipeline (freeze; fix only what demos need)

| ID | Title | Description | Files | Pri | Cx | Acceptance |
|---|---|---|---|---|---|---|
| PIPE-1 | Count probe errors as failures | `evaluator.py:72` excludes exceptions from the denominator, contradicting its comment. Count them as failures; report `n_errors` in the event | `cassandra_ai/evaluator.py` | P2 | S | 1-of-4-ok-3-timeouts test → 25% with `n_errors=3` |
| PIPE-2 | Watcher cursor correctness | Advance the cursor only to the last *processed* span; don't jump to `now` on an empty batch; mark spans lacking input/output as seen | `watcher.py:86`, `loop_agent.py:59` | P2 | M | Burst of 3 failing spans → 3 incidents over 3 cycles |
| PIPE-3 | Move GCP/ADK deploy to `examples/gcp/` | `deploy/`, `functions/`, `build_adk_agent` | — | P2 | S | Core wheel has no `google-adk` import path |
| PIPE-4 | Rule-first live diagnosis | `Diagnostician.diagnose` uses the oracle cascade instead of the LLM judge on every span | `diagnostician.py` | P2 | S | Spans decided by rule make no LLM call (mocked LLM call count) |

---

## Epic VAL: validation tooling (supports master §15)

| ID | Title | Description | Pri | Cx | Acceptance |
|---|---|---|---|---|---|
| VAL-1 | Partner workspace template | `partners/<slug>/{contract.yaml, logs/ (gitignored), labels.jsonl, report.md, notes.md}` + a README on data handling (delete logs after the engagement) | P0 | S | First partner folder created from it |
| VAL-2 | Failure-anatomy report | Generalise this audit's probe into `scripts/anatomy.py`: counts by check × hand label, per partner, plus confusion vs labels | P0 | S | Runs on TravelPal and one partner log |
| VAL-3 | Research post + benchmark repo | GO_TO_MARKET §3 #1–#2 | P1 | M | Reviewed by both founders; every number reproducible from scripts |
| VAL-4 | Landing page + waitlist | Single static page (reuse `web/` styles) describing the CLI; the waitlist collects company, role, agent type, and the failure they fear. Store submissions outside the repo | P1 | S | Live; conversion measured |

---

## Epic MON: design-partner server (Phase 5; outline, refine after D1)

| ID | Title | Description | Deps | Pri | Cx |
|---|---|---|---|---|---|
| MON-1 | Server skeleton | FastAPI + Postgres + jobs table (`SKIP LOCKED`) + one worker importing `cassandra_ai`; docker compose | RPL-4 | P2 | L |
| MON-2 | Ingest API | `POST /v1/turns` (JSONL), `POST /v1/otlp`; idempotent on `(org, trace, span)`; redaction before persist | MON-1, SEC-5 | P2 | L |
| MON-3 | Review queue | Confirm/dismiss flags; labels → per-agent precision; export to `cases/` | MON-2 | P2 | L |
| MON-4 | Digests | Weekly Slack digest; GitHub PR comment from CI runs | MON-3 | P3 | M |
| MON-5 | Self-host packaging | One image + compose + docs; no outbound calls by default | MON-1 | P2 | M |
| MON-6 | Tenancy | Orgs, API keys, Postgres RLS | MON-1 | P2 | M |
