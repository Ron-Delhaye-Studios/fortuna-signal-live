#!/usr/bin/env python3
"""FORTUNA SIGNAL — daily market-data refresh (evidence layer only).

HARD RULE: "automate evidence, not judgment."
This script may ONLY update machine-fetched evidence: current prices, 24h
changes, fetch timestamps, and data-freshness flags. It MUST NOT create,
modify, or delete briefs, verdicts, rankings, classifications, dossier copy,
or any human judgment. Anything judgment-shaped stays human-gated — always.

Reads:  <data-dir>/tracked-assets.json   [{"ticker": ..., "cg_id": ...}, ...]
Writes: <data-dir>/market-snapshot.json  {"fetched_at": iso, "prices": {cg_id: {"usd", "usd_24h_change", "last_updated_at"}}, "stale_ids": [...]}
        <data-dir>/freshness.json        {"generated_at": iso, "ok_ids": [...], "stale_ids": [...], "missing_ids": [...]}

Data source: CoinGecko public API (free tier, no key). Polite batching with
sleeps between calls; one retry on transient failure; unknown ids are
reported as missing, never guessed.

Usage:
    python3 daily_refresh.py --data-dir assets/data          # real run
    python3 daily_refresh.py --data-dir assets/data --dry-run # fetch + report, write nothing
"""

import argparse
import json
import os
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone

COINGECKO_SIMPLE_PRICE = "https://api.coingecko.com/api/v3/simple/price"
BATCH_SIZE = 40          # ids per API call
BATCH_SLEEP_S = 65       # free-tier politeness between batches
REQUEST_TIMEOUT_S = 30
STALE_AFTER_S = 48 * 3600  # price data older than this is flagged stale


def now_iso():
    return datetime.now(timezone.utc).isoformat()


def load_tracked(data_dir):
    path = os.path.join(data_dir, "tracked-assets.json")
    with open(path, encoding="utf-8") as f:
        doc = json.load(f)
    assets = doc["assets"] if isinstance(doc, dict) else doc
    seen, out = set(), []
    for a in assets:
        cg_id = (a.get("cg_id") or "").strip()
        if cg_id and cg_id not in seen:
            seen.add(cg_id)
            out.append({"ticker": a.get("ticker", ""), "cg_id": cg_id})
    return out


def fetch_batch(ids):
    params = urllib.parse.urlencode({
        "ids": ",".join(ids),
        "vs_currencies": "usd",
        "include_24hr_change": "true",
        "include_last_updated_at": "true",
    })
    url = COINGECKO_SIMPLE_PRICE + "?" + params
    last_err = None
    for attempt in (1, 2):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "fortuna-signal-daily-refresh/1.0"})
            with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT_S) as resp:
                if resp.status != 200:
                    raise RuntimeError(f"HTTP {resp.status}")
                return json.load(resp)
        except Exception as e:  # noqa: BLE001 - transient network failure, retry once
            last_err = e
            time.sleep(5)
    raise RuntimeError(f"CoinGecko fetch failed after retry: {last_err}")


def fetch_all(cg_ids):
    merged = {}
    for i in range(0, len(cg_ids), BATCH_SIZE):
        batch = cg_ids[i:i + BATCH_SIZE]
        merged.update(fetch_batch(batch))
        if i + BATCH_SIZE < len(cg_ids):
            time.sleep(BATCH_SLEEP_S)
    return merged


def build_snapshot(tracked, raw):
    now = time.time()
    prices, stale_ids, missing_ids, ok_ids = {}, [], [], []
    for a in tracked:
        cid = a["cg_id"]
        entry = raw.get(cid)
        if not entry or entry.get("usd") is None:
            missing_ids.append(cid)
            continue
        try:
            usd = float(entry["usd"])
        except (TypeError, ValueError):
            missing_ids.append(cid)
            continue
        change = entry.get("usd_24h_change")
        try:
            change = float(change) if change is not None else None
        except (TypeError, ValueError):
            change = None
        last_upd = entry.get("last_updated_at")
        prices[cid] = {"usd": usd, "usd_24h_change": change, "last_updated_at": last_upd}
        if isinstance(last_upd, (int, float)) and now - last_upd > STALE_AFTER_S:
            stale_ids.append(cid)
        else:
            ok_ids.append(cid)
    return {
        "fetched_at": now_iso(),
        "source": "coingecko-public-api",
        "prices": prices,
        "stale_ids": sorted(stale_ids),
        "missing_ids": sorted(missing_ids),
    }


def main():
    ap = argparse.ArgumentParser(description="Daily market-data refresh (evidence layer only).")
    ap.add_argument("--data-dir", required=True, help="Directory holding tracked-assets.json; outputs written here.")
    ap.add_argument("--dry-run", action="store_true", help="Fetch and report; write nothing.")
    args = ap.parse_args()

    tracked = load_tracked(args.data_dir)
    if not tracked:
        print("no tracked assets — nothing to do", file=sys.stderr)
        return 2
    cg_ids = [a["cg_id"] for a in tracked]

    raw = fetch_all(cg_ids)
    snapshot = build_snapshot(tracked, raw)
    n_ok = len(snapshot["prices"]) - len(snapshot["stale_ids"])

    print(f"tracked={len(tracked)} ok={n_ok} stale={len(snapshot['stale_ids'])} missing={len(snapshot['missing_ids'])}")
    if snapshot["stale_ids"]:
        print("stale: " + ", ".join(snapshot["stale_ids"]))
    if snapshot["missing_ids"]:
        print("missing: " + ", ".join(snapshot["missing_ids"]))

    if args.dry_run:
        print("dry-run: wrote nothing")
        return 0

    with open(os.path.join(args.data_dir, "market-snapshot.json"), "w", encoding="utf-8") as f:
        json.dump(snapshot, f, indent=2, sort_keys=True)
        f.write("\n")
    freshness = {
        "generated_at": snapshot["fetched_at"],
        "ok_ids": sorted(cid for cid in snapshot["prices"] if cid not in snapshot["stale_ids"]),
        "stale_ids": snapshot["stale_ids"],
        "missing_ids": snapshot["missing_ids"],
        "rule": "price data older than 48h is stale; unknown ids are missing, never guessed",
    }
    with open(os.path.join(args.data_dir, "freshness.json"), "w", encoding="utf-8") as f:
        json.dump(freshness, f, indent=2, sort_keys=True)
        f.write("\n")
    print(f"wrote market-snapshot.json + freshness.json to {args.data_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
