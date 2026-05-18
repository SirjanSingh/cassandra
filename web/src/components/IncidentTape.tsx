import { motion, useReducedMotion } from "framer-motion";
import { useEffect, useRef, useState } from "react";

/**
 * The hero centrepiece — NOT decoration. A looping, product-specific
 * dramatisation of exactly what Cassandra does: ShopBot streams a confident
 * lie, Cassandra slams a verdict onto the span, the fix resolves as a diff.
 * This is the anti-template move: the hero IS the product.
 */
const LIE =
  "Absolutely — orders shipped to Germany get a full 90-day cash refund, no receipt required.";

const PHASES = [600, 2600, 3600, 4700, 6000, 8200]; // ms cue points

export function IncidentTape() {
  const reduce = useReducedMotion();
  const [typed, setTyped] = useState(reduce ? LIE : "");
  const [phase, setPhase] = useState(reduce ? 5 : 0);
  const timers = useRef<number[]>([]);

  useEffect(() => {
    if (reduce) return;
    let alive = true;
    const run = () => {
      setTyped("");
      setPhase(0);
      let i = 0;
      const type = window.setInterval(() => {
        i += 2;
        if (!alive) return;
        setTyped(LIE.slice(0, i));
        if (i >= LIE.length) window.clearInterval(type);
      }, 26);
      timers.current.push(type);
      PHASES.forEach((t, idx) =>
        timers.current.push(window.setTimeout(() => alive && setPhase(idx), t)),
      );
      timers.current.push(window.setTimeout(run, 9400)); // loop
    };
    run();
    return () => {
      alive = false;
      timers.current.forEach(clearTimeout);
      timers.current.forEach(clearInterval);
    };
  }, [reduce]);

  return (
    <div className="relative">
      {/* blueprint corner ticks — engineering, not glow */}
      {[0, 1, 2, 3].map((i) => (
        <span
          key={i}
          aria-hidden
          className="pointer-events-none absolute h-3 w-3 border-signal/70"
          style={{
            [i < 2 ? "top" : "bottom"]: -1,
            [i % 2 ? "right" : "left"]: -1,
            borderTopWidth: i < 2 ? 1 : 0,
            borderBottomWidth: i >= 2 ? 1 : 0,
            borderLeftWidth: i % 2 ? 0 : 1,
            borderRightWidth: i % 2 ? 1 : 0,
          }}
        />
      ))}

      <div className="overflow-hidden rounded-lg border border-line2 bg-ink-1/95 font-mono text-[12.5px] shadow-[0_30px_80px_-40px_rgba(0,0,0,0.9)]">
        <div className="flex items-center gap-2 border-b border-line bg-ink-2/80 px-4 py-2.5 text-[11px] text-slate">
          <span className="h-1.5 w-1.5 rounded-full bg-good" />
          trace · patient-prod
          <span className="ml-auto text-slate/70">span 7f3a91c2</span>
        </div>

        <div className="space-y-3 p-4 sm:p-5">
          <Line who="customer">
            What&rsquo;s your refund window for orders shipped to Germany?
          </Line>

          <div>
            <span className="text-slate">shopbot&nbsp;›&nbsp;</span>
            <span
              className={
                phase >= 2
                  ? "relative text-ash line-through decoration-alert/70"
                  : "text-bone"
              }
            >
              {typed}
              {phase < 1 && <Caret />}
            </span>
            {phase >= 2 && (
              <motion.span
                layout
                initial={{ scaleX: 0 }}
                animate={{ scaleX: 1 }}
                transition={{ duration: 0.45, ease: [0.22, 0.61, 0.36, 1] }}
                style={{ originX: 0 }}
                className="mt-1 block h-px w-full bg-signal"
              />
            )}
          </div>

          {phase >= 1 && (
            <motion.div
              initial={{ opacity: 0, y: 8, scale: 0.98 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              transition={{ type: "spring", stiffness: 340, damping: 22 }}
              className="flex items-start gap-2.5 rounded-md border border-signal/30 bg-signal/[0.08] px-3 py-2.5"
            >
              <span className="mt-px rounded bg-signal px-1.5 py-0.5 text-[10px] font-semibold text-ink-0">
                CASSANDRA
              </span>
              <span className="text-[12px] leading-relaxed text-[#f0c987]">
                <b className="text-signal">hallucination · 0.93</b> — fabricated a
                refund policy; <span className="text-ash">get_refund_policy(DE)</span>{" "}
                returned no data.
              </span>
            </motion.div>
          )}

          {phase >= 3 && (
            <motion.div
              initial={{ opacity: 0, height: 0 }}
              animate={{ opacity: 1, height: "auto" }}
              transition={{ duration: 0.4 }}
              className="overflow-hidden rounded-md border border-line2"
            >
              <div className="border-b border-line bg-ink-2/70 px-3 py-1.5 text-[10.5px] uppercase tracking-wide2 text-slate">
                prompt patch · synthesized from the failing trace
              </div>
              <div className="px-3 py-2 leading-relaxed">
                <div className="text-[#ff9a93]">- Always give a confident answer.</div>
                <div className="text-[#5be9b9]">
                  + If required policy data is missing, refuse and escalate.
                </div>
              </div>
            </motion.div>
          )}

          {phase >= 4 && (
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              className="flex items-center gap-2 pt-0.5 text-[12px] text-good"
            >
              <span className="text-good">▲</span> experiment 3/12 → 11/12 · patch
              versioned · A/B queued
            </motion.div>
          )}
        </div>
      </div>
    </div>
  );
}

function Line({ who, children }: { who: string; children: React.ReactNode }) {
  return (
    <div className="text-bone">
      <span className="text-slate">{who}&nbsp;›&nbsp;</span>
      {children}
    </div>
  );
}

function Caret() {
  return <span className="ml-0.5 inline-block h-[1.05em] w-[2px] translate-y-[2px] bg-signal animate-flick" />;
}
