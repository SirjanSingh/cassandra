import { useEffect, useRef } from "react";

/**
 * Bespoke animated "trace graph": drifting nodes with signal pulses travelling
 * along edges — evokes spans/traces flowing through an observability pipeline.
 * Hand-built canvas, not a template. Pauses for prefers-reduced-motion.
 */
export function TraceCanvas() {
  const ref = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const cv = ref.current;
    if (!cv) return;
    const ctx = cv.getContext("2d");
    if (!ctx) return;
    const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

    let w = 0;
    let h = 0;
    const dpr = Math.min(window.devicePixelRatio || 1, 2);
    const N = 26;
    const nodes = Array.from({ length: N }, () => ({
      x: Math.random(),
      y: Math.random(),
      vx: (Math.random() - 0.5) * 0.0004,
      vy: (Math.random() - 0.5) * 0.0004,
    }));
    const edges: [number, number][] = [];
    for (let i = 0; i < N; i++)
      for (let j = i + 1; j < N; j++)
        if (Math.random() < 0.08) edges.push([i, j]);
    const pulses = edges.map(() => Math.random());

    const resize = () => {
      w = cv.clientWidth;
      h = cv.clientHeight;
      cv.width = w * dpr;
      cv.height = h * dpr;
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    };
    resize();
    window.addEventListener("resize", resize);

    let raf = 0;
    const draw = () => {
      ctx.clearRect(0, 0, w, h);
      for (const n of nodes) {
        if (!reduce) {
          n.x += n.vx;
          n.y += n.vy;
        }
        if (n.x < 0 || n.x > 1) n.vx *= -1;
        if (n.y < 0 || n.y > 1) n.vy *= -1;
      }
      edges.forEach(([a, b], k) => {
        const A = nodes[a];
        const B = nodes[b];
        const ax = A.x * w;
        const ay = A.y * h;
        const bx = B.x * w;
        const by = B.y * h;
        ctx.strokeStyle = "rgba(244,241,234,0.07)";
        ctx.lineWidth = 1;
        ctx.beginPath();
        ctx.moveTo(ax, ay);
        ctx.lineTo(bx, by);
        ctx.stroke();
        if (!reduce) pulses[k] = (pulses[k] + 0.004) % 1;
        const px = ax + (bx - ax) * pulses[k];
        const py = ay + (by - ay) * pulses[k];
        ctx.fillStyle = "rgba(242,169,59,0.85)";
        ctx.beginPath();
        ctx.arc(px, py, 1.7, 0, Math.PI * 2);
        ctx.fill();
      });
      for (const n of nodes) {
        ctx.fillStyle = "rgba(244,241,234,0.5)";
        ctx.beginPath();
        ctx.arc(n.x * w, n.y * h, 1.8, 0, Math.PI * 2);
        ctx.fill();
      }
      raf = requestAnimationFrame(draw);
    };
    draw();
    return () => {
      cancelAnimationFrame(raf);
      window.removeEventListener("resize", resize);
    };
  }, []);

  return <canvas ref={ref} className="absolute inset-0 h-full w-full" aria-hidden />;
}
