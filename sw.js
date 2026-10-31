/* FORTUNA SIGNAL service worker — offline-tolerant app shell.
 * Strategy: cache-first for versioned static assets (images, JS, JSON data),
 * network-first for HTML pages with cache fallback. Never caches POSTs.
 * Bumping CACHE_VERSION forces a clean refresh on next visit.
 */
var CACHE_VERSION = "fortuna-v2";
var STATIC_CACHE = CACHE_VERSION + "-static";
var PAGES_CACHE = CACHE_VERSION + "-pages";

var STATIC_RE = /\.(png|jpg|jpeg|svg|webp|js|css|json|webmanifest|xml|txt)$/i;

self.addEventListener("install", function (e) {
  self.skipWaiting();
});

self.addEventListener("activate", function (e) {
  e.waitUntil(
    caches.keys().then(function (keys) {
      return Promise.all(
        keys.map(function (k) {
          if (k.indexOf("fortuna-v") === 0 && k !== STATIC_CACHE && k !== PAGES_CACHE) {
            return caches.delete(k);
          }
        })
      );
    }).then(function () { return self.clients.claim(); })
  );
});

function cacheFirst(req) {
  return caches.open(STATIC_CACHE).then(function (cache) {
    return cache.match(req).then(function (hit) {
      if (hit) return hit;
      return fetch(req).then(function (res) {
        if (res && res.ok && req.method === "GET") cache.put(req, res.clone());
        return res;
      });
    });
  });
}

function networkFirst(req) {
  return caches.open(PAGES_CACHE).then(function (cache) {
    return fetch(req).then(function (res) {
      if (res && res.ok && req.method === "GET") cache.put(req, res.clone());
      return res;
    }).catch(function () {
      return cache.match(req).then(function (hit) {
        /* 404 fallback resolved against this worker's own scope, so it works
         * at a domain root and under the GitHub Pages project subpath. */
        return hit || cache.match(new URL("404.html", self.registration.scope).href);
      });
    });
  });
}

self.addEventListener("fetch", function (e) {
  var req = e.request;
  if (req.method !== "GET") return;
  var url = new URL(req.url);
  if (url.origin !== self.location.origin) return;
  /* Only handle requests inside this worker's scope (the domain root on a
   * root host, the project subpath on GitHub Pages) — never a hardcoded base. */
  if (url.pathname.indexOf(new URL(self.registration.scope).pathname) !== 0) return;
  if (STATIC_RE.test(url.pathname)) {
    e.respondWith(cacheFirst(req));
  } else {
    e.respondWith(networkFirst(req));
  }
});
