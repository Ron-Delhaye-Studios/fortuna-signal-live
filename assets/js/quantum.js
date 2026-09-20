/* quantum.js — dashboard-inspired motion for FORTUNA SIGNAL (2026-09-16).
   - Twinkling starfield + drifting dust canvas injected into .hero / .page-hero
   - Reveal-on-scroll via IntersectionObserver
   - No-JS safe: content is visible by default; this script adds the pre-reveal state.
   - Honors prefers-reduced-motion: no canvas, no reveals, no motion at all. */
(function () {
  "use strict";
  var root = document.documentElement;
  root.classList.add("qjs");

  var reduceMotion = window.matchMedia &&
    window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  if (reduceMotion) return; /* CSS static fallbacks take over */

  /* ---------- reveal on scroll ---------- */
  /* HARD RULE: reveal units are small elements (cards, rows, facts). Never
     .section — a container taller than ~8x the viewport can never satisfy the
     intersection threshold, so its whole subtree stays invisible forever. */
  var revealSel = ".card, .narrative, .record-row, .fact, " +
    ".tldr, .vocab article, .anatomy article, .dossier, .concept";
  var targets = document.querySelectorAll(revealSel);
  if (targets.length && "IntersectionObserver" in window) {
    Array.prototype.forEach.call(targets, function (el) {
      el.classList.add("rv");
      var sibs = el.parentNode ? el.parentNode.children : [];
      var i = Array.prototype.indexOf.call(sibs, el);
      if (i > 0 && i < 8) el.style.transitionDelay = (i * 70) + "ms";
    });
    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (e) {
        if (e.isIntersecting) {
          e.target.classList.add("in");
          io.unobserve(e.target);
        }
      });
    }, { threshold: 0.12, rootMargin: "0px 0px -8% 0px" });
    Array.prototype.forEach.call(targets, function (el) { io.observe(el); });
    /* Safety net: no element may stay invisible. If the observer never fires
       for a target (tall ancestor, quirk, race), force it visible after 3s. */
    window.setTimeout(function () {
      Array.prototype.forEach.call(
        document.querySelectorAll(".rv:not(.in)"),
        function (el) { el.classList.add("in"); });
    }, 3000);
  }

  /* ---------- quantum starfield ---------- */
  var heroes = document.querySelectorAll(".hero, .page-hero");
  if (!heroes.length || !("requestAnimationFrame" in window)) return;

  var COLORS = ["198,167,106", "57,208,216", "154,123,255", "128,221,178"];

  Array.prototype.forEach.call(heroes, function (hero) {
    var cv = document.createElement("canvas");
    cv.className = "quantum-field";
    cv.setAttribute("aria-hidden", "true");
    hero.insertBefore(cv, hero.firstChild);
    var ctx = cv.getContext("2d");
    if (!ctx) return;

    var W = 0, H = 0, dpr = 1;
    var stars = [], dust = [];
    var running = false, visible = true, t0 = 0;

    function seed() {
      stars = [];
      dust = [];
      var n = Math.max(28, Math.min(90, Math.floor(W * H / 16000)));
      for (var i = 0; i < n; i++) {
        stars.push({
          x: Math.random() * W, y: Math.random() * H,
          r: Math.random() * 1.3 + 0.4,
          p: Math.random() * Math.PI * 2,
          s: 0.4 + Math.random() * 0.9,
          c: COLORS[i % COLORS.length]
        });
      }
      var m = Math.max(8, Math.min(26, Math.floor(W * H / 60000)));
      for (var j = 0; j < m; j++) {
        dust.push({
          x: Math.random() * W, y: Math.random() * H,
          r: Math.random() * 2.2 + 1.2,
          vx: (Math.random() - 0.5) * 0.12,
          vy: (Math.random() - 0.5) * 0.08,
          c: COLORS[(j + 1) % COLORS.length]
        });
      }
    }

    function resize() {
      dpr = Math.min(window.devicePixelRatio || 1, 2);
      W = hero.clientWidth;
      H = hero.clientHeight;
      cv.width = Math.max(1, Math.floor(W * dpr));
      cv.height = Math.max(1, Math.floor(H * dpr));
      seed();
    }

    function frame(t) {
      if (!running) return;
      var dt = Math.min(50, (t - t0) || 16);
      t0 = t;
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      ctx.clearRect(0, 0, W, H);
      var i, s, a;
      for (i = 0; i < stars.length; i++) {
        s = stars[i];
        s.p += 0.0016 * dt * s.s; /* slow twinkle */
        a = 0.25 + 0.55 * Math.abs(Math.sin(s.p));
        ctx.beginPath();
        ctx.arc(s.x, s.y, s.r, 0, 6.2832);
        ctx.fillStyle = "rgba(" + s.c + "," + a.toFixed(3) + ")";
        ctx.fill();
      }
      for (i = 0; i < dust.length; i++) {
        var d = dust[i];
        d.x += d.vx * dt / 16;
        d.y += d.vy * dt / 16;
        if (d.x < -8) d.x = W + 8; else if (d.x > W + 8) d.x = -8;
        if (d.y < -8) d.y = H + 8; else if (d.y > H + 8) d.y = -8;
        var g = ctx.createRadialGradient(d.x, d.y, 0, d.x, d.y, d.r * 4);
        g.addColorStop(0, "rgba(" + d.c + ",0.10)");
        g.addColorStop(1, "rgba(" + d.c + ",0)");
        ctx.fillStyle = g;
        ctx.beginPath();
        ctx.arc(d.x, d.y, d.r * 4, 0, 6.2832);
        ctx.fill();
      }
      if (visible && !document.hidden) {
        requestAnimationFrame(frame);
      } else {
        running = false;
      }
    }

    function start() {
      if (!running && visible && !document.hidden) {
        running = true;
        t0 = 0;
        requestAnimationFrame(frame);
      }
    }
    function stop() { running = false; }

    if ("IntersectionObserver" in window) {
      new IntersectionObserver(function (es) {
        visible = es[0].isIntersecting;
        if (visible) start(); else stop();
      }, { threshold: 0 }).observe(hero);
    }
    document.addEventListener("visibilitychange", function () {
      if (document.hidden) stop(); else start();
    });
    window.addEventListener("resize", resize);
    resize();
    start();
  });
})();
