# Session Log: 2026-06-10 — Live Integration, Phoenix URLs, and Feedback Loop Fixes

## Overview
In this session, we focused on fixing end-to-end live integration bugs that emerged when running the Cassandra meta-agent against a fresh local instance of the Arize Phoenix MCP server. The primary issues revolved around broken dashboard links, script execution paths, and an infinite feedback loop triggered by Cassandra's own adversarial testing traffic. We also formalized a comprehensive test suite to move beyond hardcoded testing.

## Issues Addressed & Fixes

### 1. Phoenix URL Generation Bug ("Unknown node")
**Problem:** The dashboard's "Open in Phoenix" links were generating GraphQL errors (`Unknown node: patient-prod`). The Phoenix UI router requires **base64-encoded node IDs** (e.g., `UHJvamVjdDoy`) rather than plaintext project names (`patient-prod`).
**Fix:**
- Updated `cassandra/phoenix_mcp.py` to dynamically resolve the project name to its base64 node ID by calling the Phoenix `list-projects` tool.
- Introduced a **module-level cache** (`_project_id_cache`) to ensure all `PhoenixMCP` instances (Watcher, Diagnostician, RootCauseAnalyst) share the resolved node ID without needing redundant MCP queries.
- Pre-warmed the cache during the initial `query_spans` call.

### 2. Pipeline Script Path Execution (`ModuleNotFoundError`)
**Problem:** Running `python scripts/run_pipeline.py` directly from the project root caused an import error for the `cassandra` module.
**Fix:**
- Added a `sys.path.insert(0, ...)` directive at the top of `scripts/run_pipeline.py` to ensure the project root is always in the Python path when executed directly.

### 3. Infinite Feedback Loop (Watcher Re-processing Replay/Red-Team Spans)
**Problem:** During the Replay and Red-Team stages, Cassandra sends test messages to the Patient agent. These calls generated new Phoenix traces. The Watcher's filter was failing to reliably ignore these traces because it only checked for `span.session_id == "test"`. Child tool spans (like `tool.lookup_order`) defaulted to a `"demo"` session ID, slipping past the filter, which caused the pipeline to continuously re-diagnose its own adversarial probes.
**Fixes Applied:**
- **Robust Watcher Filtering (`cassandra/watcher.py`):** Added explicit filters to skip spans marked with `prompt_variant = "candidate"` and to ignore all child spans of kind `"TOOL"`.
- **State De-duplication Fix (`cassandra/state.py`):** The `StateStore` was instantiating multiple independent `LocalState` objects, causing the Watcher to read stale in-memory data instead of the latest disk state. We converted `get_state()` into a memoized singleton so all components share the same deduplication memory.
- **Dashboard Polling Cooldown (`dashboard/main.py`):** Increased the delay after a successful pipeline run from 5s to 30s to allow test spans to flush and be correctly marked as seen before the next polling cycle.

### 4. Comprehensive Live Integration Test Suite
**Feature:** Added `docs/test_suite.md`.
- Expanded testing beyond the 11 hardcoded traps to include **49 test points** across 7 distinct categories.
- Covers diverse hallucination triggers, tricky tool failure boundaries, prompt drift (jailbreaks), and true negatives (OK verdicts).
- Formalized downstream validation criteria for the Patcher, Replay, Red-Team, and Self-Evaluation stages.

## Status Updates
- **Feedback loop protection:** ✅ Verified live. The loop is broken and test traffic is properly ignored.
- **Live end-to-end run on Phoenix:** ✅ Verified live. Links correctly route to Phoenix UI.
- **Tests:** ✅ Documented robust live integration criteria in `docs/test_suite.md`.

## Next Steps
- Finalize the video demo script using the newly stabilized end-to-end flow.
- Execute Vertex Agent Engine deployment (requires GCP credentials).
