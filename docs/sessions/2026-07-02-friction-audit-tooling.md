# Session Log: 2026-07-02 — Cross-project friction audit + global tooling fixes

Branch: `cassandra-v2` (no cassandra code touched — this session audited Claude Code
sessions across all projects and fixed global machine/agent config; recorded here because
this repo hosts the session-protocol memory).

## Scope

Audited ~77 Claude Code session transcripts across 14 projects (June 2026) with four
parallel subagents, clustered recurring friction, then implemented the approved fixes.

## Findings (top clusters)

1. Status-checking thrash: /usage ×103, /model ×73, /effort ×33 in prompt history.
2. Manual session close-out chores (~40× "push / update session logs / commit under my name").
3. Windows dual-shell traps (~35 errors) incl. a UTF-16 `.bashrc` erroring on every Bash call.
4. C: and D: drives at 100% — root cause: ~147 GB astrophotography on D: + 27.9 GB D:\pagefile.sys
   (dev projects are only ~15 GB); disk-full killed a session on 2026-07-02.
5. Long-run babysitting (training on silent CPU fallback, Cloud Build polling).
6. Permission-denial loops (direct-to-master intern workflow, co-author-trailer scrubs).
7. Unverified frontend fixes (user as test harness); secrets pasted into transcripts 6+ times.

## Changes (all outside this repo)

- `~/.bashrc` re-encoded UTF-16→UTF-8 (backup: `~/.bashrc.utf16.bak`); verified clean shell.
- Removed deprecated `npm_config_tmp` user env var; purged pip cache (933 MB).
- `~/.claude/settings.json`: removed expired internship SessionStart hook; added
  `statusLine` (new `~/.claude/statusline.js`, shell-tested: model | ctx% | dir | branch | cost);
  added `attribution: {commit:"", pr:""}` (no more Co-Authored-By trailers).
- Pruned `~/.claude/skills` 1,295 → 55 curated; 1,241 archived to `G:\claude-skills-archive`
  (move a folder back to restore).
- **New** `~/.claude/CLAUDE.md` (global): git identity rules, Windows shell rules, kcl venv
  path, CUDA preflight, away-mode no-destructive-ops rule, secrets hygiene, UI-verify rule.
- **New** `~/.claude/skills/wrap/SKILL.md` — `/wrap` = session notes + memory + logical
  commits (no AI trailers) + push in one pass.
- Auto-memory: added `claude-code-friction-audit-2026-07.md` + MEMORY.md index line.

## Verification

`.bashrc` login shell runs clean; settings.json parses (PS ConvertFrom-Json) after each
edit; statusline.js piped a sample payload and rendered correctly; skills move reported
kept=55 moved=1241 failed=0.

## Open items

- Settings changes take effect on next Claude Code restart.
- User-side disk actions: move astro data off D:, shrink D: pagefile, `powercfg /h off`,
  compact WSL vhdx.
- Not yet built (proposed): intern-repo push-to-master permission rule, `/train` (kcl),
  `/sync-team`, run `/fewer-permission-prompts`.
- The v2 grounding-verifier working tree (B1) from earlier today is intentionally left
  uncommitted — see `2026-07-02-grounding-verifier.md`.
