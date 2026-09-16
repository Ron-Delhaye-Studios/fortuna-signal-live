/* FORTUNA SIGNAL — market-data renderer (evidence layer only).
 *
 * Reads assets/data/market-snapshot.json (written daily by
 * scripts/daily_refresh.py) and fills any [data-cg-id] element with the
 * current price, 24h change, and a freshness stamp.
 *
 * Defensive by design: if the fetch fails, the JSON is missing, or an id has
 * no data, the page is left exactly as built. This script never writes
 * judgments, never guesses, never breaks the page.
 */
(function () {
  "use strict";

  function siteRoot() {
    try {
      var src = document.currentScript && document.currentScript.src || "";
      var i = src.indexOf("/assets/js/market.js");
      if (i > 0) return src.slice(0, i);
    } catch (e) {}
    return "";
  }

  function fmtUSD(n) {
    if (n === null || n === undefined || !isFinite(n)) return null;
    if (n >= 1000) return "$" + n.toLocaleString("en-US", { maximumFractionDigits: 2 });
    if (n >= 1) return "$" + n.toFixed(2);
    if (n >= 0.01) return "$" + n.toFixed(4);
    return "$" + n.toPrecision(3);
  }

  function fmtDate(iso) {
    try {
      return new Date(iso).toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" });
    } catch (e) { return ""; }
  }

  function fill(el, prices, fetchedAt, staleIds) {
    var id = el.getAttribute("data-cg-id");
    var p = prices[id];
    if (!p || p.usd === null || p.usd === undefined) return;
    var price = fmtUSD(p.usd);
    if (price === null) return;
    var pe = el.querySelector('[data-lp="price"]');
    var ce = el.querySelector('[data-lp="change"]');
    var ae = el.querySelector('[data-lp="asof"]');
    if (pe) pe.textContent = price;
    if (ce && p.usd_24h_change !== null && p.usd_24h_change !== undefined && isFinite(p.usd_24h_change)) {
      var c = p.usd_24h_change;
      ce.textContent = (c >= 0 ? "+" : "") + c.toFixed(2) + "% / 24h";
      ce.className = "m-change " + (c >= 0 ? "up" : "down");
    }
    if (ae && fetchedAt) {
      var stale = staleIds.indexOf(id) !== -1;
      ae.textContent = stale ? "· price data stale" : "· as of " + fmtDate(fetchedAt);
      if (stale) ae.className = "m-asof stale";
    }
    el.hidden = false;
  }

  function run() {
    var els = document.querySelectorAll("[data-cg-id]");
    if (!els.length) return;
    fetch(siteRoot() + "/assets/data/market-snapshot.json", { cache: "no-store" })
      .then(function (r) { return r.ok ? r.json() : null; })
      .then(function (d) {
        if (!d || !d.prices) return;
        var stale = Array.isArray(d.stale_ids) ? d.stale_ids : [];
        for (var i = 0; i < els.length; i++) {
          try { fill(els[i], d.prices, d.fetched_at, stale); } catch (e) {}
        }
      })
      .catch(function () { /* leave the page as built */ });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", run);
  } else {
    run();
  }
})();
