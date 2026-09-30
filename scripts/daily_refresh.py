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

Resilience (2026-09-29): CoinGecko intermittently returns HTTP 403 to cloud
IPs (GitHub runners included). A blocked fetch must NEVER crash the daily
workflow. Behavior on source failure:
  1. Retry with backoff (up to ~35 minutes total) — blocks are often
     transient and the 07:00 run has time to ride them out.
  2. If still unreachable, degrade honestly: keep the last good prices,
     flag EVERYTHING stale in both JSON files, write a note naming the
     cause, and exit 0. The site already renders stale flags ("price data
     stale"); the workflow stays green and no failure mail goes out.
Stale data shown honestly beats no data and a red workflow. The next day's
run overwrites with fresh data when the source answers again.

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
# Optional free "Demo" API key (CoinGecko dashboard → API). When present it is
# sent as the x-cg-demo-api-key header, which restores authenticated requests
# while unauthenticated cloud traffic is blocked. Absent = public requests.
COINGECKO_API_KEY = os.environ.get("COINGECKO_API_KEY", "").strip()
BATCH_SIZE = 40          # ids per API call
BATCH_SLEEP_S = 65       # free-tier politeness between batches
REQUEST_TIMEOUT_S = 30
STALE_AFTER_S = 48 * 3600  # price data older than this is flagged stale

# Outer retry schedule (minutes) when the whole fetch fails. Total worst case
# ~35 minutes of waiting — fine for a once-daily scheduled run.
RETRY_WAIT_MINUTES = (10, 10, 15)


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


def load_previous_snapshot(data_dir):
    path = os.path.join(data_dir, "market-snapshot.json")
    if not os.path.exists(path):
        return None
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def fetch_batch(ids):
    params = urllib.parse.urlencode({
        "ids": ",".join(ids),
        "vs_currencies": "usd",
        "include_24hr_change": "true",
        "include_last_updated_at": "true",
    })
    url = COINGECKO_SIMPLE_PRICE + "?" + params
    headers = {"User-Agent": "fortuna-signal-daily-refresh/1.0"}
    if COINGECKO_API_KEY:
        headers["x-cg-demo-api-key"] = COINGECKO_API_KEY
    last_err = None
    for attempt in (1, 2):
        try:
            req = urllib.request.Request(url, headers=headers)
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


def fetch_with_backoff(cg_ids):
    """Try the full fetch; on failure wait and retry. Returns the raw dict,
    or None when the source stayed unreachable through the whole schedule."""
    try:
        return fetch_all(cg_ids)
    except RuntimeError as e:
        print(f"fetch attempt 1 failed: {e}", flush=True)
    for n, wait_min in enumerate(RETRY_WAIT_MINUTES, start=2):
        print(f"waiting {wait_min} min before fetch attempt {n} ...", flush=True)
        time.sleep(wait_min * 60)
        try:
            raw = fetch_all(cg_ids)
            print(f"fetch attempt {n} succeeded", flush=True)
            return raw
        except RuntimeError as e:
            print(f"fetch attempt {n} failed: {e}", flush=True)
    return None


def build_snapshot(tracked, raw, fetched_at):
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
        "fetched_at": fetched_at,
        "source": "coingecko-public-api",
        "prices": prices,
        "stale_ids": sorted(stale_ids),
        "missing_ids": sorted(missing_ids),
    }


def build_degraded_snapshot(tracked, previous, fetched_at, cause):
    """Honest degradation: keep last-known prices, flag everything stale."""
    prices = {}
    if previous and isinstance(previous.get("prices"), dict):
        prices = previous["prices"]
    have = set(prices)
    stale_ids = sorted(cid for cid in (a["cg_id"] for a in tracked) if cid in have)
    missing_ids = sorted(cid for cid in (a["cg_id"] for a in tracked) if cid not in have)
    return {
        "fetched_at": fetched_at,
        "source": "coingecko-public-api",
        "degraded": True,
        "degraded_note": (
            f"Source unreachable ({cause}); showing last-known prices flagged "
            "stale. No data was guessed or fabricated."
        ),
        "prices": prices,
        "stale_ids": stale_ids,
        "missing_ids": missing_ids,
    }


def write_outputs(data_dir, snapshot, ok_ids):
    with open(os.path.join(data_dir, "market-snapshot.json"), "w", encoding="utf-8") as f:
        json.dump(snapshot, f, indent=2, sort_keys=True)
        f.write("\n")
    freshness = {
        "generated_at": snapshot["fetched_at"],
        "ok_ids": sorted(ok_ids),
        "stale_ids": snapshot["stale_ids"],
        "missing_ids": snapshot["missing_ids"],
        "rule": "price data older than 48h is stale; unknown ids are missing, never guessed",
    }
    if snapshot.get("degraded"):
        freshness["degraded"] = True
        freshness["degraded_note"] = snapshot["degraded_note"]
    with open(os.path.join(data_dir, "freshness.json"), "w", encoding="utf-8") as f:
        json.dump(freshness, f, indent=2, sort_keys=True)
        f.write("\n")
    print(f"wrote market-snapshot.json + freshness.json to {data_dir}")


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

    print(f"coingecko auth: {'demo key' if COINGECKO_API_KEY else 'none (public requests)'}", flush=True)
    raw = fetch_with_backoff(cg_ids)
    fetched_at = now_iso()

    if raw is None:
        cause = "CoinGecko returned errors through all retry attempts"
        print(f"SOURCE UNREACHABLE: {cause} — degrading honestly", flush=True)
        previous = None if args.dry_run else load_previous_snapshot(args.data_dir)
        snapshot = build_degraded_snapshot(tracked, previous, fetched_at, cause)
        n_ok = 0
    else:
        snapshot = build_snapshot(tracked, raw, fetched_at)
        n_ok = len(snapshot["prices"]) - len(snapshot["stale_ids"])

    print(f"tracked={len(tracked)} ok={n_ok} stale={len(snapshot['stale_ids'])} missing={len(snapshot['missing_ids'])}")
    if snapshot["stale_ids"]:
        print("stale: " + ", ".join(snapshot["stale_ids"]))
    if snapshot["missing_ids"]:
        print("missing: " + ", ".join(snapshot["missing_ids"]))

    if args.dry_run:
        print("dry-run: wrote nothing")
        return 0

    write_outputs(data_dir=args.data_dir,
                  snapshot=snapshot,
                  ok_ids=[cid for cid in snapshot["prices"] if cid not in snapshot["stale_ids"]])
    return 0


if __name__ == "__main__":
    sys.exit(main())
