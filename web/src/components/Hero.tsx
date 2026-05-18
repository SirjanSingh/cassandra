import { motion, useReducedMotion, useScroll, useTransform } from "framer-motion";
import { useRef } from "react";
import { ArrowRight } from "lucide-react";
import { IncidentTape } from "./IncidentTape";

const SPECS = [
  ["model", "gemini-3"],
  ["latency", "<10s"],
  ["track", "arize · phoenix"],
  ["license", "apache-2.0"],
];

export function Hero() {
  const ref = useRef<HTMLElement>(null);
  const reduce = useReducedMotion();
  const { scrollYProgress } = useScroll({
    target: ref,
    offset: ["start start", "end start"],
  });
  const artY = useTransform(scrollYProgress, [0, 1], [0, reduce ? 0 : -56]);

  return (
    <section
      ref={ref}
      className="relative mx-auto grid min-h-screen max-w-7xl items-center gap-14 px-6 pt-28 pb-20 lg:grid-cols-[1.04fr_1fr] lg:gap-10"
    >
      {/* faint blueprint grid — engineering substrate, not particles */}
      <div
        aria-hidden
        className="pointer-events-none absolute inset-0 -z-10 opacity-[0.5]"
        style={{
          backgroundImage:
            "linear-gradient(rgba(244,241,234,0.028) 1px,transparent 1px),linear-gradient(90deg,rgba(244,241,234,0.028) 1px,transparent 1px)",
          backgroundSize: "64px 64px",
          maskImage: "radial-gradient(120% 80% at 30% 30%,#000,transparent 78%)",
        }}
      />

      <div>
        <div className="mb-7 flex items-center gap-3 font-mono text-[11px] uppercase tracking-wide2 text-slate">
          <span className="h-px w-9 bg-signal" />
          <span className="text-signal">Meta-agent observability</span>
        </div>

        <h1 className="font-display text-[clamp(2.2rem,4.5vw,3.7rem)] font-bold leading-[1.06] tracking-tightish text-bone">
          Production agents lie.
          <br />
          Cassandra is the engineer
          <br />
          who <span className="text-signal">catches it</span> — at 3am,
          <br />
          without you.
        </h1>

        <p className="mt-7 max-w-md text-[15px] leading-relaxed text-ash">
          A meta-agent that supervises your agents through Arize Phoenix: it
          diagnoses the failure, proves a fix with a real experiment, and ships an
          A/B-ready prompt patch — on its own.
        </p>

        <div className="mt-9 flex items-center gap-6">
          <a
            href="#cockpit"
            className="group inline-flex items-center gap-2.5 border-b-2 border-signal pb-1 font-mono text-sm font-semibold text-bone transition-colors hover:text-signal"
          >
            See it catch a lie
            <ArrowRight className="h-4 w-4 text-signal transition-transform duration-200 group-hover:translate-x-1" />
          </a>
          <a
            href="#how"
            className="font-mono text-sm text-slate underline-offset-4 transition-colors hover:text-ash hover:underline"
          >
            how it works
          </a>
        </div>

        <dl className="mt-14 grid max-w-md grid-cols-2 gap-px overflow-hidden rounded-md border border-line bg-line sm:grid-cols-4">
          {SPECS.map(([k, v]) => (
            <div key={k} className="bg-ink-0 px-3 py-3">
              <dt className="font-mono text-[10px] uppercase tracking-wide2 text-slate">
                {k}
              </dt>
              <dd className="mt-1 font-mono text-[12px] text-bone">{v}</dd>
            </div>
          ))}
        </dl>
      </div>

      <motion.div
        style={{ y: artY }}
        initial={reduce ? false : { opacity: 0, y: 24 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.7, ease: [0.22, 0.61, 0.36, 1] }}
      >
        <IncidentTape />
        <div className="mt-3 text-right font-mono text-[10.5px] text-slate">
          live dramatisation · the cockpit below is the real thing ↓
        </div>
      </motion.div>
    </section>
  );
}
