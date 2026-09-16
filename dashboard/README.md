# dashboard/

Operational (quantum) dashboard for the FORTUNA SIGNAL trading program.

## Layout

- `d-<16 hex>/` — the dashboard app at an unguessable path. `index.html` is the
  app (PIN gate → Three.js quantum hero → SVG graphs → insight cards),
  `snapshot.json` is its data, `config.json` holds ONLY the PIN's SHA-256 hash,
  `manifest.webmanifest` + icons enable iPhone "Add to Home Screen."
- `export_snapshot.py` — CI-mode refresher used by `dashboard-refresh.yml`.
  It ONLY touches the `site` section of `snapshot.json` (reachability +
  analytics status) and `meta.generated_at`. Trading sections are written
  exclusively by the local exporter
  (`fortuna-signal-site/cmgr/scripts/export_dashboard_snapshot.py`), which has
  the ledger and DB. Never the reverse.
- `PRIVACY.md` — honest threat model. Read it.

## Deploy hygiene (important)

The main site is built by `build.py` into `dist/` and copied over this repo.
That copy MUST be additive (`cp -r dist/* .`), never `rsync --delete` —
`dashboard/` and `.github/` live only here and would be wiped otherwise.

## The other builder's workflow

`.github/workflows/daily-refresh.yml` (site content refresh) is owned by a
separate workstream. This dashboard's automation lives in
`.github/workflows/dashboard-refresh.yml` — separate file, no overlap.
