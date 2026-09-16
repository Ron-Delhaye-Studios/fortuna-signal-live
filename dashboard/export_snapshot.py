#!/usr/bin/env python3
"""CI-mode dashboard refresher — used by .github/workflows/dashboard-refresh.yml.

STRICT SCOPE: this script may ONLY touch the `site` section of snapshot.json
(reachability check + analytics status) and meta.generated_at / generated_by.
Trading sections (pilot, experiments, heuristics, systems, equity_curve,
insights) are written EXCLUSIVELY by the local exporter
(cmgr/scripts/export_dashboard_snapshot.py), which has the ledger and DB.
This script never reads, fabricates, or modifies trading data.

It merges into the existing snapshot.json; if none exists it writes a
site-only skeleton so the dashboard renders an honest empty state.
"""
from __future__ import annotations

import json
import os
import sys
import urllib.request
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
SITE_URL = "https://whitewizard888.github.io/fortuna-signal-live/"
# The dashboard dir is the single d-*/ child of dashboard/.
DASH_DIRS = [d for d in os.listdir(HERE)
             if d.startswith("d-") and os.path.isdir(os.path.join(HERE, d))]


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def check_site() -> dict:
    try:
        req = urllib.request.Request(SITE_URL, method="HEAD")
        with urllib.request.urlopen(req, timeout=20) as r:
            return {"reachable": r.status < 400, "http_status": r.status}
    except Exception as e:  # noqa: BLE001
        return {"reachable": False, "error": type(e).__name__}


def main() -> int:
    if not DASH_DIRS:
        print("no dashboard dir found", file=sys.stderr)
        return 1
    dash = os.path.join(HERE, DASH_DIRS[0])
    snap_path = os.path.join(dash, "snapshot.json")
    snap = {}
    if os.path.exists(snap_path):
        with open(snap_path) as f:
            snap = json.load(f)

    site = check_site()
    site["as_of"] = utcnow()
    site["url"] = SITE_URL
    site["status"] = "live" if site["reachable"] else "unreachable"
    # Analytics is wired by the other builder's workstream; detect the beacon
    # token placeholder in the built index.html (dist copy in repo root).
    idx = os.path.join(os.path.dirname(HERE), "index.html")
    beacon_live = False
    if os.path.exists(idx):
        html = open(idx, encoding="utf-8", errors="replace").read()
        beacon_live = ("beacon.min.js" in html and "YOUR_CF_TOKEN" not in html
                       and "CLOUDFLARE_BEACON_TOKEN" not in html)
    site["dossiers"] = 146
    site["analytics"] = "live" if beacon_live else "pending"
    snap["site"] = site
    snap.setdefault("meta", {})["generated_at"] = utcnow()
    snap["meta"]["generated_by"] = "dashboard-refresh.yml (CI site layer)"

    tmp = snap_path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(snap, f, indent=1)
    os.replace(tmp, snap_path)
    print(f"refreshed site layer in {snap_path}: {site['status']}, "
          f"analytics={site['analytics']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
