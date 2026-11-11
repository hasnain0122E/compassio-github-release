# data/db — local project database (git-ignored)

`compassio_dev.sqlite` is created here by:

```powershell
uv run compassio-db migrate
uv run compassio-db ingest --source all
```

It is **derived from registered sources whose rights are `not_reviewed`**. Never commit, upload
or share it. Delete and rebuild it at any time; ingestion is idempotent. See
`docs/data/ingestion_pipeline.md` and `docs/security/source_rights_access_policy.md`.
