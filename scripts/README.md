# scripts

| Script | Purpose |
| --- | --- |
| `check.ps1` | Run every Phase 0 quality gate on Windows PowerShell. |
| `check.sh` | Same gates for POSIX shells (Git Bash, Linux, macOS, CI). |

File hashing is provided as an installed console command, not a script:
`uv run compassio-hash <file> [<file> ...]`.
