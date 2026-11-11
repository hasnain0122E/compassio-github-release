# data/raw_db — backend-only source snapshots (git-ignored)

Downloaded by the backend, **never** placed in `data/raw/` (which belongs to the canonical
nine-source manifest used by the ML track):

```powershell
uv run compassio-db fetch --source gcf_api_projects   # new timestamped snapshot; never overwrites
uv run compassio-db registry                          # validate hashes, sizes, stray files
```

* `registry.json` — operational provenance registry (identical copy tracked in Git at
  `data/manifests/backend_source_registry.json`, metadata only).
* `<backend_source_id>/<UTC snapshot>/…` — immutable payload + `http_headers.json` sidecar.

All backend sources are `rights_status: not_reviewed`. Do not commit, share or redistribute these
files. See `docs/data/backend_source_registry.md`.
