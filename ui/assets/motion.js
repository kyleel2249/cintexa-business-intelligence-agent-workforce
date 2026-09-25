/*!
 * CINTEXA Motion — shared 3D interaction toolkit used by both the chat UI
 * (index.html) and the executive dashboard (dashboard.html).
 *
 * Everything here degrades gracefully: prefers-reduced-motion disables all
 * animation, and every feature is opt-in via a small `data-*` attribute or
 * class so plain HTML never breaks if this file fails to load.
 */
(function (global) {
  "use strict";

  const REDUCE = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  function lerp(a, b, t) {
    return a + (b - a) * t;
  }
  function clamp(v, lo, hi) {
    return Math.max(lo, Math.min(hi, v));
  }

  /* ---------------------------------------------------------------------
   * initStage(selector) — pointer + device-orientation parallax with
   * independent per-layer depth. Each child of the stage can declare
   * data-depth="N" (px of travel at full tilt); the stage itself also gets
   * a gentle whole-scene rotateX/rotateY. Uses the CSS `translate` property
   * (independent of `transform`) so it composes cleanly with any existing
   * keyframe animation on the same element instead of fighting it.
   * ------------------------------------------------------------------- */
  function initStage(selector) {
    const stage = document.querySelector(selector || ".stage");
    if (!stage || REDUCE) return { enableGyro: () => {} };

    const layers = Array.from(stage.querySelectorAll("[data-depth]")).map((el) => ({
      el,
      depth: parseFloat(el.getAttribute("data-depth")) || 10,
    }));

    let targetX = 0, targetY = 0, curX = 0, curY = 0, running = true;

    window.addEventListener(
      "pointermove",
      (e) => {
        targetX = (e.clientX / window.innerWidth - 0.5) * 2;
        targetY = (e.clientY / window.innerHeight - 0.5) * 2;
      },
      { passive: true }
    );
    window.addEventListener(
      "pointerleave",
      () => { targetX = 0; targetY = 0; },
      { passive: true }
    );

    function handleOrientation(e) {
      if (e.gamma == null || e.beta == null) return;
      targetX = clamp(e.gamma / 28, -1, 1);
      targetY = clamp((e.beta - 40) / 28, -1, 1);
    }
    function enableGyro() {
      if (typeof DeviceOrientationEvent !== "undefined" && typeof DeviceOrientationEvent.requestPermission === "function") {
        DeviceOrientationEvent.requestPermission()
          .then((state) => {
            if (state === "granted") window.addEventListener("deviceorientation", handleOrientation, { passive: true });
          })
          .catch(() => {});
      } else if (window.DeviceOrientationEvent) {
        window.addEventListener("deviceorientation", handleOrientation, { passive: true });
      }
    }

    function frame() {
      if (!running) return;
      curX = lerp(curX, targetX, 0.06);
      curY = lerp(curY, targetY, 0.06);
      stage.style.transform = "rotateY(" + (curX * 4) + "deg) rotateX(" + (-curY * 3) + "deg)";
      for (const layer of layers) {
        layer.el.style.translate = (curX * layer.depth) + "px " + (curY * layer.depth * 0.7) + "px " + layer.depth + "px";
      }
      requestAnimationFrame(frame);
    }
    requestAnimationFrame(frame);

    document.addEventListener("visibilitychange", () => {
      running = document.visibilityState === "visible";
      if (running) requestAnimationFrame(frame);
    });

    return { enableGyro };
  }

  /* ---------------------------------------------------------------------
   * spawnParticles(hostId, count) — rising ambient particle field.
   * ------------------------------------------------------------------- */
  function spawnParticles(hostId, count) {
    const host = document.getElementById(hostId || "particles");
    if (!host || REDUCE) return;
    const n = count || Math.min(36, Math.floor(window.innerWidth / 40));
    for (let i = 0; i < n; i++) {
      const el = document.createElement("span");
      el.className = "particle";
      el.style.left = Math.random() * 100 + "%";
      el.style.animationDuration = 8 + Math.random() * 14 + "s";
      el.style.animationDelay = -Math.random() * 12 + "s";
      el.style.width = el.style.height = 2 + Math.random() * 3 + "px";
      el.style.opacity = String(0.3 + Math.random() * 0.5);
      host.appendChild(el);
    }
  }

  /* ---------------------------------------------------------------------
   * initTilt(selector) — real per-element 3D tilt-on-hover. Rotation is
   * computed from the pointer's position inside each element's own bounding
   * box, so every card tilts independently and "follows" the cursor.
   * ------------------------------------------------------------------- */
  function initTilt(selector, opts) {
    if (REDUCE) return;
    const max = (opts && opts.max) || 8;
    const scale = (opts && opts.scale) || 1.015;
    document.addEventListener("pointermove", (e) => {
      const target = e.target.closest(selector);
      if (!target) return;
      const rect = target.getBoundingClientRect();
      const px = (e.clientX - rect.left) / rect.width - 0.5;
      const py = (e.clientY - rect.top) / rect.height - 0.5;
      target.style.transform =
        "perspective(700px) rotateX(" + (-py * max) + "deg) rotateY(" + (px * max) + "deg) scale3d(" + scale + "," + scale + "," + scale + ")";
      target.style.setProperty("--glow-x", (px * 50 + 50) + "%");
      target.style.setProperty("--glow-y", (py * 50 + 50) + "%");
    });
    document.addEventListener(
      "pointerout",
      (e) => {
        const target = e.target.closest(selector);
        if (!target) return;
        target.style.transform = "";
      },
      true
    );
  }

  /* ---------------------------------------------------------------------
   * countUp(el, target, opts) — animated number count-up, format-aware
   * (keeps a trailing suffix like "/100" or "%" intact).
   * ------------------------------------------------------------------- */
  function countUp(el, target, opts) {
    if (!el) return;
    const duration = (opts && opts.duration) || 900;
    const suffix = (opts && opts.suffix) || "";
    const decimals = (opts && opts.decimals) || 0;
    if (REDUCE || target == null || isNaN(target)) {
      el.textContent = (target == null ? "—" : target.toFixed(decimals)) + suffix;
      return;
    }
    const start = 0;
    const t0 = performance.now();
    function step(now) {
      const p = clamp((now - t0) / duration, 0, 1);
      const eased = 1 - Math.pow(1 - p, 3);
      const val = start + (target - start) * eased;
      el.textContent = val.toFixed(decimals) + suffix;
      if (p < 1) requestAnimationFrame(step);
    }
    requestAnimationFrame(step);
  }

  /* ---------------------------------------------------------------------
   * toast(message, type) — lightweight slide-in notification stack.
   * ------------------------------------------------------------------- */
  function toast(message, type) {
    let host = document.getElementById("toastHost");
    if (!host) {
      host = document.createElement("div");
      host.id = "toastHost";
      host.className = "toast-host";
      document.body.appendChild(host);
    }
    const el = document.createElement("div");
    el.className = "toast toast-" + (type || "info");
    el.textContent = message;
    host.appendChild(el);
    requestAnimationFrame(() => el.classList.add("show"));
    setTimeout(() => {
      el.classList.remove("show");
      setTimeout(() => el.remove(), 350);
    }, 3400);
  }

  /* ---------------------------------------------------------------------
   * orbit(container, items, opts) — a ring of nodes in 3D (CSS
   * rotateY + translateZ), auto-rotating and drag/swipe-able with inertia.
   * items: array of {label, sub} rendered as .orbit-node children.
   * Returns { destroy }.
   * ------------------------------------------------------------------- */
  function orbit(container, items, opts) {
    if (!container) return { destroy() {} };
    const radius = (opts && opts.radius) || 150;
    const speed = REDUCE ? 0 : (opts && opts.speed) || 0.015; // deg/ms auto-rotate
    const onSelect = (opts && opts.onSelect) || function () {};

    container.innerHTML = "";
    const ring = document.createElement("div");
    ring.className = "orbit-ring";
    const step = 360 / items.length;
    items.forEach((item, i) => {
      const node = document.createElement("button");
      node.type = "button";
      node.className = "orbit-node";
      node.style.transform = "rotateY(" + (i * step) + "deg) translateZ(" + radius + "px)";
      node.innerHTML = '<span class="orbit-node-dot"></span><span class="orbit-node-label">' + item.label + "</span>";
      node.title = item.sub || item.label;
      node.addEventListener("click", () => onSelect(item, i));
      ring.appendChild(node);
    });
    container.appendChild(ring);

    let angle = 0;
    let dragging = false;
    let lastX = 0;
    let velocity = 0;
    let raf = null;
    let lastT = performance.now();

    function apply() {
      ring.style.transform = "rotateY(" + angle + "deg)";
    }

    function tick(now) {
      const dt = now - lastT;
      lastT = now;
      if (!dragging) {
        angle += speed * dt + velocity * dt;
        velocity *= 0.92;
      }
      apply();
      raf = requestAnimationFrame(tick);
    }
    raf = requestAnimationFrame(tick);

    container.style.touchAction = "pan-y";
    container.addEventListener("pointerdown", (e) => {
      dragging = true;
      lastX = e.clientX;
      velocity = 0;
      container.setPointerCapture(e.pointerId);
      container.classList.add("dragging");
    });
    container.addEventListener("pointermove", (e) => {
      if (!dragging) return;
      const dx = e.clientX - lastX;
      lastX = e.clientX;
      angle += dx * 0.35;
      velocity = dx * 0.006;
    });
    function release() {
      dragging = false;
      container.classList.remove("dragging");
    }
    container.addEventListener("pointerup", release);
    container.addEventListener("pointercancel", release);

    return {
      destroy() {
        if (raf) cancelAnimationFrame(raf);
        container.innerHTML = "";
      },
    };
  }

  /* ---------------------------------------------------------------------
   * commandPalette({ commands, hostId }) — Ctrl/Cmd+K searchable action
   * launcher. commands: [{ id, label, hint, run }].
   * ------------------------------------------------------------------- */
  function commandPalette(config) {
    const commands = (config && config.commands) || [];
    let modal = null;
    let list = null;
    let input = null;
    let active = 0;
    let filtered = commands;

    function build() {
      modal = document.createElement("div");
      modal.className = "cmdk-backdrop hidden";
      modal.innerHTML =
        '<div class="cmdk">' +
        '<input class="cmdk-input" placeholder="Type a command or search… (Esc to close)" autocomplete="off" spellcheck="false" />' +
        '<div class="cmdk-list"></div>' +
        '<div class="cmdk-hint">↑↓ navigate · ↵ select · esc close</div>' +
        "</div>";
      document.body.appendChild(modal);
      input = modal.querySelector(".cmdk-input");
      list = modal.querySelector(".cmdk-list");

      modal.addEventListener("click", (e) => {
        if (e.target === modal) close();
      });
      input.addEventListener("input", () => render(input.value));
      input.addEventListener("keydown", (e) => {
        if (e.key === "Escape") close();
        if (e.key === "ArrowDown") { e.preventDefault(); move(1); }
        if (e.key === "ArrowUp") { e.preventDefault(); move(-1); }
        if (e.key === "Enter") { e.preventDefault(); select(); }
      });
    }

    function render(query) {
      const q = (query || "").toLowerCase().trim();
      filtered = commands.filter((c) => !q || c.label.toLowerCase().includes(q) || (c.hint || "").toLowerCase().includes(q));
      active = 0;
      list.innerHTML = filtered
        .map(
          (c, i) =>
            '<button type="button" class="cmdk-item' + (i === 0 ? " active" : "") + '" data-i="' + i + '">' +
            '<span>' + c.label + "</span>" +
            (c.hint ? '<span class="cmdk-item-hint">' + c.hint + "</span>" : "") +
            "</button>"
        )
        .join("") || '<div class="cmdk-empty">No matching commands.</div>';
      list.querySelectorAll(".cmdk-item").forEach((btn) => {
        btn.addEventListener("click", () => {
          active = Number(btn.getAttribute("data-i"));
          select();
        });
      });
    }

    function move(delta) {
      if (!filtered.length) return;
      active = (active + delta + filtered.length) % filtered.length;
      list.querySelectorAll(".cmdk-item").forEach((el, i) => el.classList.toggle("active", i === active));
      const el = list.querySelector(".cmdk-item.active");
      if (el) el.scrollIntoView({ block: "nearest" });
    }

    function select() {
      const cmd = filtered[active];
      if (cmd) {
        close();
        cmd.run();
      }
    }

    function open() {
      if (!modal) build();
      render("");
      modal.classList.remove("hidden");
      input.value = "";
      setTimeout(() => input.focus(), 30);
    }
    function close() {
      if (modal) modal.classList.add("hidden");
    }

    document.addEventListener("keydown", (e) => {
      const meta = e.metaKey || e.ctrlKey;
      if (meta && e.key.toLowerCase() === "k") {
        e.preventDefault();
        if (!modal || modal.classList.contains("hidden")) open();
        else close();
      }
    });

    return { open, close };
  }

  global.CintexaMotion = { initStage, spawnParticles, initTilt, countUp, toast, orbit, commandPalette };
})(window);
