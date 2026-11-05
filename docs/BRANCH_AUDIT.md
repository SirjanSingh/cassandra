# Branch audit (2026-11-05)

> Part of the strategy set. Master document: [PRODUCT_VISION_AND_COMPANY_ROADMAP.md](PRODUCT_VISION_AND_COMPANY_ROADMAP.md).
>
> **Method.** `git fetch --all`, then ancestry (`merge-base --is-ancestor`), per-segment commit logs, file-level
> diffs between tips, and a full `pytest` run of each live tip in a fresh Python 3.13 venv. Nothing was
> merged, rebased or deleted. Code references in this set use the form `branch:path:line`; unless a branch
> is named, they mean **`feature/nli-and-hindi` @ `23994bf`**, which is the most advanced code.

---

## 1. The one-paragraph answer

The repository has **two divergent lines of work that have never been reconciled**. Both grew from a
shared trunk (`62790b4`, 2026-07-21). **Sirjan's line** (`cassandra-v2` → `task0-grounding-base-rate`)
produced no product code after the trunk, but it did produce the project's most important evidence: a
correctness audit, a security audit, and a reproducible measurement on 1,980 real agent trajectories that
**does not support the core grounding thesis**. **Kshitij's line** (`multi-agent-v1` →
`demo/mock-bot-integration` → `feature/nli-and-hindi`) produced every product feature since July (jury, PR
flow, NLI layer, Hindi, the TravelPal proof of concept, `cassandra scan`, the PyPI 0.3.0 release). It never
received Sirjan's audits or the Task 0 result. `main` is a stale August snapshot that has neither line.
**The strongest foundation is `feature/nli-and-hindi`. The strongest *evidence* lives only on
`task0-grounding-base-rate`. The product needs both.**

## 2. Topology

```
                                   ┌─ 09ef23e  main  (+TAM/SAM/SOM doc, 2026-08-11)        ← default branch, STALE
8692b73 (2026-06-11 hackathon end) ┤
                                   └─ 14 commits (Jun 28 – Jul 21, Sirjan) ─ 62790b4  shared trunk  [tag v0.2.0-alpha.1 = 91c7a2e]
                                                                              │
                     ┌────────────────────────────────────────────────────────┴────────────────────────┐
                     │ Sirjan's line (docs + measurement only)                                          │ Kshitij's line (all product work)
              5ae9f85 audit + launch plan                                                       25c002a jury + PR
              dd322a6 security audit + stress probe                                             de88f46 (Sirjan's review of jury/PR)
              df10549 CLAUDE.md structure map  ← cassandra-v2                                   66981d0 Windows CLI fix
              1694ebb Task 0 base-rate measurement ← task0-grounding-base-rate                  bd62d50 production-adoption guide
                                                                                                e3400d1 seeder poisoning + jury math ← multi-agent-v1
                                                                                                aa20794, e58eea2 HTML demo ← demo/mock-bot-integration
                                                                                                0f06fd9 NLI + Hindi + declutter
                                                                                                14669d9, c9a5b4c TravelPal PoC + week 1
                                                                                                d1570ba `cassandra scan`
                                                                                                8b740c3 outreach kit
                                                                                                0cb1ef9, 23994bf light install, PyPI 0.3.0 ← feature/nli-and-hindi
```

Ancestry facts (verified with `git merge-base --is-ancestor`):

- `cassandra-v2` ⊂ `task0-grounding-base-rate`.
- `multi-agent-v1` ⊂ `demo/mock-bot-integration` ⊂ `feature/nli-and-hindi`.
- `feature/ci-prompt-gate` and `feature/incident-postmortems` are ancestors of every branch, including `main`.
  They were merged on 2026-06-10 (`38e2de2`, `0b39363`).
- Local `main` and this working branch (`claude/loving-planck-llm1bd`) both sit at `09ef23e`.

## 3. Branch intelligence matrix

| Branch | Tip / date / author | Purpose (from code + commits) | Unique content (not on any other line) | Status | Quality | Reuse potential | Recommendation |
|---|---|---|---|---|---|---|---|
| `main` (default) | `09ef23e` · 2026-08-11 · Kshitij | Hackathon-end snapshot plus one research doc | `docs/TAM_SAM_SOM.md` | Stale: 31 commits behind `nli-and-hindi`, 18 behind `task0`; no grounding, oracle, CLI, scan or PyPI packaging | Hackathon-grade | Low (one doc) | **Replace** with a consolidation branch (§6). Carry `TAM_SAM_SOM.md` over with its caveats. |
| `feature/nli-and-hindi` | `23994bf` · 2026-11-05 · Kshitij | Product line: scan CLI, light PyPI install, TravelPal PoC, NLI, Hindi, outreach | `cassandra/scan.py`, `nli.py`, `jury.py`, `pr.py`; `poc/travelpal/` (98 + 50 labelled turns, fix-loop artefacts); `demo/` HTML; `docs/POSITIONING.md`, `30_DAY_PLAN.md`, `OUTREACH.md`, `SCAN.md`, `PRODUCTION_ADOPTION.md`; docs archive | Active. 116 tests pass **only with `mcp<2`**: a fresh install today resolves `mcp` 2.3.0 and `tests/test_mcp_server.py` fails at collection | Good seams and tests. Known verifier holes are unfixed (§5) | **High**: the base for the product | **Make it the base** of the consolidation branch |
| `demo/mock-bot-integration` | `e58eea2` · 2026-09-04 · Kshitij | No-install HTML demo: bank + airline agents with a live faithfulness panel | None (fully contained in `nli-and-hindi`) | Complete; 92 tests pass | Good demo; the JS checker is a port of `grounding.py` | Medium (sales demo) | **Delete** after consolidation; no unique content |
| `multi-agent-v1` | `e3400d1` · 2026-07-26 · Kshitij | Multi-judge jury, open-fix-as-PR, seeder poisoning fix, jury confidence fix | None (contained in `nli-and-hindi`) | Complete | Fixes verified by Sirjan's review (`de88f46`) | Contained | **Delete** after consolidation |
| `task0-grounding-base-rate` | `1694ebb` · 2026-09-25 · Sirjan | Falsification test of the grounding thesis on tau-bench | `docs/TASK0_GROUNDING_BASE_RATE.md`; `scripts/task0_measure_grounding.py`, `task0_bound_addressable.py` | Complete. **Reproduced exactly in this audit** (§4) | High: reproducible, conservative, honest about threats to validity | **High**: the most decision-relevant artefact in the repo | **Merge into consolidation** (docs + scripts, no conflicts expected) |
| `cassandra-v2` | `df10549` · 2026-08-05 · Sirjan | v2 audit, security audit, stress harness, CLAUDE.md known-broken list + structure map | `docs/SECURITY_AUDIT.md`; `docs/sessions/2026-08-05-code-audit-and-launch-plan.md`; `scripts/stress_probe.py`; CLAUDE.md "Known-broken" and "Repository structure" sections | Complete (docs only); 73 tests pass | High | **High** (audits are still accurate: every finding re-verified on `nli-and-hindi`) | **Merge via `task0`** (it is a strict ancestor) |
| `feature/ci-prompt-gate` | `f2d72cc` · 2026-06-10 | `cassandra-gate` CI prompt regression gate | None | Merged 2026-06-10 | — | Contained | **Delete** |
| `feature/incident-postmortems` | `b5d3ed2` · 2026-06-10 | Auto-postmortem per supervision cycle | None | Merged 2026-06-10 | — | Contained | **Delete** |

Tag `v0.2.0-alpha.1` → `91c7a2e` (trunk, 2026-07-21). PyPI has only `cassandra-ai 0.3.0`, published from
`feature/nli-and-hindi` on 2026-11-05.

## 4. What each line knows that the other doesn't

This is the most important finding of the audit. It is a strategy problem, not a merge problem.

| Fact | Sirjan's line | Kshitij's line |
|---|---|---|
| Task 0: on 1,980 tau-bench trajectories, value fabrication is ~0 and a value-grounding alarm has 44.8% precision against a 40.3% base rate (+4.5 pp) | ✅ measured | ❌ never received |
| TravelPal: on a narrow-tool assistant, 14–30% of answers state facts no tool returned; rule-first cascade hits 100% precision (11/11) on held-out turns | ❌ | ✅ measured |
| `grounding.py` checks that a call *succeeded*, not that the claim *matches* it (a DHL result grounds an answer of "UPS") | ✅ audited | ⚠️ known as a "wrong place/date blind spot", not as a value-equality bug |
| Security: 3 CRITICAL, 4 HIGH (fail-open override, unauthenticated LLM spend, loop-per-instance, key in argv, `@latest` npm, dotenv override) | ✅ audited | ❌ never received. All 7 are still present |
| `cassandra` import name collides with `cassandra-driver`; must become `cassandra_ai` | ✅ decided 2026-08-05 | ❌ shipped 0.3.0 to PyPI with top-level `cassandra`, `patient` and `dashboard` packages |
| "Refuse everything" is the degenerate optimum; no regression set | ✅ audited | ❌ |
| Positioning: "catches when your agent states a fact its tools never gave it" | Task 0 §8 says **don't lead with this** | `docs/POSITIONING.md` **leads with this**; outreach is under way on it |

**Reproduction (this audit).** `scripts/task0_measure_grounding.py` and `task0_bound_addressable.py` were run
against the four `sierra-research/tau-bench` `historical_trajectories` files, downloaded 2026-11-05. The
output matched the document exactly: 29,381 values, 2,339 not in the ledger (7.96%), 82.4% of those
arithmetic, residual 1.399%; failed 99/797 versus passed 122/1,183 with an anomaly; precision 44.8%.

**The two results are not contradictory.** They measure different agent shapes:

- tau-bench agents have tools that cover the whole domain and fail **procedurally**: wrong action, wrong arguments.
- TravelPal has narrow tools and open-ended questions, so it fails by **answering beyond its tools**.

Which shape real customers run is the open question (see the master document §15, experiment E1).

### Additional probe run in this audit (exploratory, not committed as product code)

I tested Task 0's suggested pivot, "did the agent actually do what it said", using a ledger-only check on
the same 1,980 trajectories. The probe script lives in the session scratchpad, not in the repo. Its method:

- a regex for completion claims ("has been cancelled", "I've updated"…);
- a check for a successful write-tool call before the claim;
- a comparison of executed write calls against tau-bench's ground-truth `actions`.

| Signal | Failed trajectories | Passed trajectories | Precision (base rate 40.3%) |
|---|---|---|---|
| Any completion claim | 75.7% | 72.4% | 41.3% |
| Completion claim with no prior successful write | 7.7% | 5.8% | 46.9% |
| **Write tool returned `Error`, then agent claimed completion** | **4.6%** | **0.8%** | **80.4%** |

Failure anatomy against ground truth: **94.6% of failed trajectories executed the wrong state-changing
actions**. 44.3% called different write tools than required, 29.4% called the right tools with the wrong
arguments, and 21.0% executed no write at all. In only 5.4% were the writes exactly right.

**Implications:**

1. In transactional agents, the dominant failure is *doing the wrong thing*, not *saying an unsupported thing*.
2. Neither text grounding nor ledger-only completion checks see it.
3. "Swallowed tool error → claimed success" is a cheap, high-precision but low-recall check worth shipping.
4. Catching wrong actions needs a source of truth for the *right* action: business policy or the user's
   stated request. That is a contract problem, and it is where Cassandra's spec machinery could go next.

Caveats:

- The regex is crude.
- tau-bench uses strong 2024 models in a clean environment.
- The ground-truth comparison is only possible offline.

## 5. Defects verified on the product line (`feature/nli-and-hindi`)

Every item below was re-read in current code. None was fixed after the August audit, because the files are
byte-identical across both lines:

- `grounding.py`
- `watcher.py`
- `evaluator.py`
- `redteam.py`
- `state.py`
- `patcher.py`
- `patient/agent.py`
- `dashboard/main.py`

| Area | Defect | Location |
|---|---|---|
| Verifier | Field claims are checked for non-null, never for equality | `cassandra/grounding.py:111-114` |
| Verifier | Any successful call grounds any claim of its type; calls are matched by tool name only, never by arguments | `grounding.py:77-78`, `:139-141` |
| Verifier | First match only per extractor | `grounding.py:69` |
| Verifier | Decline markers are unreachable once any claim is extracted | `grounding.py:85-96` |
| Detection | The live supervision path (`Diagnostician.diagnose`) is **LLM-only**. The rule-first cascade is used only by `scan` and by eval scoring | `cassandra/diagnostician.py` (`diagnose` → `judge_panel`) |
| Dead code | The NLI layer has no production caller. No caller ever passes `evidence=` to `score_case` | `oracle.py:120-141`; `grep` finds no caller |
| Eval | Exceptions are dropped from the denominator, contradicting the comment above them | `cassandra/evaluator.py:65-72` |
| Eval | `_MAX_CASES = 4` quantises the headline metric to 25% steps | `evaluator.py:30` |
| Watcher | The cursor advances past all spans, but only the first failing incident is processed → burst loss. An empty poll jumps the cursor to `now` | `watcher.py:86`, `loop_agent.py:59` |
| State | Read-modify-write with no transaction; 500-entry cap; blocking I/O | `cassandra/state.py:44-71` |
| Safety | **Replay, eval, red-team and gate execute the agent's real tools.** "Sandboxed" means only `session_id="test"` | `examples/adapter_template.py:84`; `patient_client.py` |
| Security | `system_override` fails open when `REPLAY_SHARED_SECRET` is unset. The **adapter template customers copy** also uses non-constant-time `!=` | `patient/agent.py:67`; `examples/adapter_template.py:87-88` |
| Security | Supervision loop starts on every web instance; `/ask` and `/selfeval` are unauthenticated | `dashboard/main.py:34-57,74-85` |
| Security | Phoenix key in argv; `npx @arizeai/phoenix-mcp@latest`; `load_dotenv(override=True)` | `phoenix_mcp.py:60-61`; `config.py:10,31` |
| Injection | Production traffic flows into the Patcher as "TRIGGERING INPUT", and the candidate prompt is written to Phoenix before it is scored | `patcher.py:53,70` |
| Packaging | Wheel installs top-level `cassandra`, `patient`, `dashboard` (verified from the PyPI wheel). `cassandra` collides with `cassandra-driver` 3.30.1 | `pyproject.toml:85` |
| Packaging | `mcp>=1.2.0` resolves to 2.3.0, which removed `mcp.server.fastmcp` → `cassandra mcp` and a fresh `[full]` install are broken | `pyproject.toml`; `cassandra/mcp_server.py:32` |
| Packaging | Every dependency is floor-only; no lockfile. `ruff` 0.17.3 reports 49 findings where sessions recorded "clean" with older ruff. `google-adk` 2.13 deprecates `LoopAgent` | `pyproject.toml` |
| Process | **No CI at all** (no `.github/`). The product sells a CI gate | — |
| PR flow | The `git switch` fallback's return code is unchecked → may commit onto the current branch | `cassandra/pr.py:142-143` |

Also checked: a secrets scan of every ref's full history found no API keys, tokens or private keys, and no
`.env`, credentials, `.pem` or `.key` file was ever added. README advertises a public demo URL. It was **not
probed**; see the master document §11.

## 6. Consolidation plan (recommended; not executed, per instructions)

1. Create `consolidation/2026-11` from `origin/feature/nli-and-hindi`.
2. Merge `origin/task0-grounding-base-rate`. Expected conflicts are limited to `CLAUDE.md` and `docs/CODEBASE_MAP.md`:
   - keep `nli-and-hindi`'s doc archive layout;
   - keep task0's "Known-broken" and structure-map sections;
   - re-verify each known-broken item against code (all still present per §5).
3. Bring `docs/TAM_SAM_SOM.md` from `main`, marked as unverified third-party estimates.
4. Bring this strategy set from `claude/loving-planck-llm1bd`.
5. Fix the release-blockers (backlog `PKG-1..3`, `CI-1`). Then fast-forward `main` to the consolidation branch.
6. Delete merged branches: `feature/ci-prompt-gate`, `feature/incident-postmortems`, `multi-agent-v1`,
   `demo/mock-bot-integration`, `cassandra-v2`, `task0-grounding-base-rate`. Tag each tip first
   (`archive/<name>`) so nothing is lost.
7. From then on, there is one integration branch. Short-lived feature branches merge only through CI.

What should **not** be merged forward as active product scope:

- NLI and Hindi: keep the code, but stop extending it.
- The ADK `LoopAgent` / Agent Engine wrapper.
- The React marketing cockpit.

These stay in the repo but leave the default install and the roadmap (master document §19, "stop building").
