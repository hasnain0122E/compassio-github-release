# Task 001 — Environment reconnaissance

Recorded 2026-11-08 on the developer machine, before any changes.

## Starting state

- Working directory `D:\AI LEARNING\Compassio - Give Green Funding a Better Direction` was **empty**
  (no files, no Git repository). No user files existed, so nothing was moved or deleted.
- No source datasets were present in or under the directory.

## Operating system and shells

| Item | Detected |
| --- | --- |
| OS | Microsoft Windows 11 Pro 10.0.26300 (x86_64) |
| Windows PowerShell | 5.1.26100.9818 |
| Git Bash | provided by Git for Windows |

## Tools

| Tool | Detected version | Notes |
| --- | --- | --- |
| Python (default on PATH) | 3.14.7 | **Not used**; the brief prefers 3.12 |
| Python 3.13 / 3.11 | 3.13.15 / 3.11.7 | Installed, not used |
| Python 3.12 | **3.12.15** (uv-managed CPython) | **Selected** via `.python-version` |
| uv | 0.13.0 (2026-10-09) | Used for the Python workspace and lockfile |
| Node.js | 24.19.0 | Meets Next.js 16's `>=20.9` requirement |
| npm | 12.0.2 | Used only for `npm view` version lookups |
| pnpm | 11.21.0 | Pinned via `packageManager` in `apps/web/package.json` |
| corepack | 0.35.0 | Available |
| Git | 2.55.0.windows.3 | Repository initialized with `git init -b main` |
| Claude Code | 2.1.319 | Available |

## Missing prerequisites

None. No machine-level changes were made: no global installs, no PATH edits, no Python installs
(3.12.15 was already present in uv's managed store).

## Discrepancies and choices

- The system default Python is 3.14. The project pins 3.12 through `.python-version`, which uv
  honours, so the system default does not matter.
- Network access to PyPI and npm worked. Versions were taken from the registries at setup time
  (FastAPI 0.162.2, Next.js 16.4.5, and so on; full list in `docs/architecture/tech_stack.md`).
