/**
 * CINTEXA scroll-driven 3D canvas — constant motion + scroll camera.
 * Canvas 2D perspective (no extra libraries).
 */
(function (global) {
  "use strict";

  function prefersReduce() {
    return window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  }

  function Scene3D(canvas, options) {
    this.canvas = canvas;
    this.ctx = canvas.getContext("2d", { alpha: true });
    this.opts = options || {};
    this.scrollEl = this.opts.scrollEl || null;
    this.t = 0;
    this.scroll = 0;
    this.targetScroll = 0;
    this.pointer = { x: 0, y: 0 };
    this.running = false;
    this.dpr = Math.min(window.devicePixelRatio || 1, 2);
    this.stars = [];
    this.rings = [];
    this.nodes = [];
    this._resize = this.resize.bind(this);
    this._loop = this.loop.bind(this);
    this._onScroll = this.onScroll.bind(this);
    this._onPointer = this.onPointer.bind(this);
    this.initField();
    this.resize();
  }

  Scene3D.prototype.initField = function () {
    const n = this.opts.stars || 140;
    this.stars = [];
    for (let i = 0; i < n; i++) {
      this.stars.push({
        x: (Math.random() - 0.5) * 1600,
        y: (Math.random() - 0.5) * 1000,
        z: Math.random() * 1400 + 80,
        s: 0.6 + Math.random() * 1.8,
        hue: Math.random() < 0.18 ? 46 : Math.random() < 0.5 ? 168 : 210,
      });
    }
    this.rings = [
      { r: 180, tilt: 0.55, speed: 0.28, color: "rgba(240,196,70,0.35)" },
      { r: 260, tilt: 1.1, speed: -0.16, color: "rgba(120,210,190,0.22)" },
      { r: 340, tilt: 0.35, speed: 0.11, color: "rgba(130,180,255,0.16)" },
    ];
    this.nodes = [];
    for (let i = 0; i < 18; i++) {
      const a = (i / 18) * Math.PI * 2;
      this.nodes.push({
        x: Math.cos(a) * 220,
        y: Math.sin(a * 1.4) * 70,
        z: Math.sin(a) * 220,
        pulse: Math.random() * Math.PI * 2,
      });
    }
  };

  Scene3D.prototype.resize = function () {
    const c = this.canvas;
    const w = c.parentElement ? c.parentElement.clientWidth : window.innerWidth;
    const h = c.parentElement ? c.parentElement.clientHeight : window.innerHeight;
    this.w = Math.max(1, w);
    this.h = Math.max(1, h);
    c.width = Math.floor(this.w * this.dpr);
    c.height = Math.floor(this.h * this.dpr);
    c.style.width = this.w + "px";
    c.style.height = this.h + "px";
    this.ctx.setTransform(this.dpr, 0, 0, this.dpr, 0, 0);
  };

  Scene3D.prototype.onScroll = function () {
    const el = this.scrollEl;
    if (el) {
      const max = Math.max(1, el.scrollHeight - el.clientHeight);
      this.targetScroll = el.scrollTop / max;
    } else {
      const doc = document.documentElement;
      const max = Math.max(1, doc.scrollHeight - window.innerHeight);
      this.targetScroll = window.scrollY / max;
    }
  };

  Scene3D.prototype.onPointer = function (e) {
    this.pointer.x = (e.clientX / this.w - 0.5) * 2;
    this.pointer.y = (e.clientY / this.h - 0.5) * 2;
  };

  Scene3D.prototype.project = function (x, y, z, rotY, rotX) {
    const cy = Math.cos(rotY), sy = Math.sin(rotY);
    const cx = Math.cos(rotX), sx = Math.sin(rotX);
    let x1 = x * cy - z * sy;
    let z1 = z * cy + x * sy;
    let y1 = y * cx - z1 * sx;
    z1 = z1 * cx + y * sx;
    const fov = 520;
    const depth = z1 + 720;
    const scale = fov / Math.max(60, depth);
    return {
      x: this.w / 2 + x1 * scale,
      y: this.h / 2 + y1 * scale * 0.92,
      s: scale,
      z: depth,
    };
  };

  Scene3D.prototype.loop = function (now) {
    if (!this.running) return;
    const dt = Math.min(0.05, (now - (this._last || now)) / 1000);
    this._last = now;
    this.t += dt;
    this.scroll += (this.targetScroll - this.scroll) * 0.06;

    const ctx = this.ctx;
    ctx.clearRect(0, 0, this.w, this.h);

    const rotY = this.t * 0.18 + this.scroll * 1.35 + this.pointer.x * 0.35;
    const rotX = Math.sin(this.t * 0.22) * 0.18 + this.scroll * 0.55 + this.pointer.y * 0.2;
    const drift = this.t * 90 + this.scroll * 380;

    // Stars / particles
    for (let i = 0; i < this.stars.length; i++) {
      const p = this.stars[i];
      let z = p.z - drift * 0.35;
      z = ((z % 1400) + 1400) % 1400;
      const pr = this.project(p.x, p.y, z - 700, rotY * 0.35, rotX * 0.4);
      if (pr.z < 40) continue;
      const alpha = Math.min(0.9, 0.15 + pr.s * 0.55);
      const size = Math.max(0.4, p.s * pr.s * 1.6);
      ctx.beginPath();
      ctx.fillStyle =
        p.hue === 46
          ? "rgba(240,196,70," + alpha + ")"
          : p.hue === 168
          ? "rgba(120,210,190," + alpha * 0.85 + ")"
          : "rgba(210,220,240," + alpha * 0.7 + ")";
      ctx.arc(pr.x, pr.y, size, 0, Math.PI * 2);
      ctx.fill();
    }

    // Orbital rings
    for (let r = 0; r < this.rings.length; r++) {
      const ring = this.rings[r];
      ctx.beginPath();
      let first = true;
      const steps = 96;
      for (let i = 0; i <= steps; i++) {
        const a = (i / steps) * Math.PI * 2 + this.t * ring.speed;
        const x = Math.cos(a) * ring.r;
        const y = Math.sin(a) * ring.r * 0.22 * Math.sin(ring.tilt + this.t * 0.2);
        const z = Math.sin(a) * ring.r;
        const pr = this.project(x, y, z, rotY, rotX);
        if (first) {
          ctx.moveTo(pr.x, pr.y);
          first = false;
        } else ctx.lineTo(pr.x, pr.y);
      }
      ctx.strokeStyle = ring.color;
      ctx.lineWidth = 1.2;
      ctx.stroke();
    }

    // Network nodes
    const projected = [];
    for (let i = 0; i < this.nodes.length; i++) {
      const n = this.nodes[i];
      const spin = this.t * 0.4;
      const x = n.x * Math.cos(spin) - n.z * Math.sin(spin);
      const z = n.z * Math.cos(spin) + n.x * Math.sin(spin);
      const y = n.y + Math.sin(this.t * 1.2 + n.pulse) * 12;
      projected.push(this.project(x, y, z, rotY * 0.7, rotX * 0.7));
    }
    ctx.lineWidth = 0.7;
    for (let i = 0; i < projected.length; i++) {
      for (let j = i + 1; j < projected.length; j++) {
        const a = projected[i], b = projected[j];
        const dx = a.x - b.x, dy = a.y - b.y;
        const d = Math.hypot(dx, dy);
        if (d < 160) {
          ctx.strokeStyle = "rgba(240,196,70," + (0.18 * (1 - d / 160)) + ")";
          ctx.beginPath();
          ctx.moveTo(a.x, a.y);
          ctx.lineTo(b.x, b.y);
          ctx.stroke();
        }
      }
    }
    for (let i = 0; i < projected.length; i++) {
      const p = projected[i];
      const pulse = 2 + Math.sin(this.t * 2 + i) * 1.2;
      ctx.beginPath();
      ctx.fillStyle = "rgba(240,196,70,0.85)";
      ctx.arc(p.x, p.y, pulse, 0, Math.PI * 2);
      ctx.fill();
    }

    requestAnimationFrame(this._loop);
  };

  Scene3D.prototype.start = function () {
    if (prefersReduce() || this.running) return;
    this.running = true;
    window.addEventListener("resize", this._resize);
    window.addEventListener("pointermove", this._onPointer, { passive: true });
    if (this.scrollEl) this.scrollEl.addEventListener("scroll", this._onScroll, { passive: true });
    else window.addEventListener("scroll", this._onScroll, { passive: true });
    this.onScroll();
    requestAnimationFrame(this._loop);
  };

  Scene3D.prototype.mount = function () {
    this.start();
    return this;
  };

  global.CintexaScene3D = Scene3D;

  function boot() {
    if (prefersReduce()) return;
    const canvas = document.getElementById("scene3d");
    if (!canvas) return;
    const scrollEl =
      document.getElementById("messages") ||
      document.querySelector(".content") ||
      null;
    new Scene3D(canvas, { scrollEl: scrollEl, stars: 160 }).mount();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot);
  } else {
    boot();
  }
})(window);
