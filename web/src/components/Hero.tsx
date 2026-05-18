import { motion, useScroll, useTransform } from "framer-motion";
import { useRef } from "react";
import { ArrowDown } from "lucide-react";
import { TraceCanvas } from "./TraceCanvas";

export function Hero() {
  const ref = useRef<HTMLElement>(null);
  const { scrollYProgress } = useScroll({
    target: ref,
    offset: ["start start", "end start"],
  });
  const bgY = useTransform(scrollYProgress, [0, 1], ["0%", "26%"]);
  const fade = useTransform(scrollYProgress, [0, 0.8], [1, 0]);
  const lift = useTransform(scrollYProgress, [0, 1], [0, -90]);

  return (
    <section
      ref={ref}
      className="grain relative flex h-screen min-h-[680px] items-center overflow-hidden"
    >
      <motion.div
        style={{ y: bgY }}
        className="absolute inset-0 -z-10 bg-cover bg-center"
      >
        <img
          src="/img/hero.jpg"
          alt=""
          className="h-full w-full object-cover opacity-[0.22] [filter:grayscale(1)_contrast(1.05)]"
        />
        <div className="absolute inset-0 bg-[radial-gradient(120%_90%_at_70%_0%,transparent,#070707_72%)]" />
      </motion.div>
      <TraceCanvas />

      <motion.div
        style={{ opacity: fade, y: lift }}
        className="relative mx-auto w-full max-w-6xl px-6"
      >
        <div className="eyebrow mb-6 flex items-center gap-3">
          <span className="inline-block h-1.5 w-1.5 rounded-full bg-signal animate-flick" />
          Arize Phoenix track · Google Cloud Rapid Agent Hackathon
        </div>
        <h1 className="max-w-4xl font-display text-[clamp(2.6rem,7vw,6rem)] font-bold leading-[0.98] tracking-tightish">
          Your agents fail
          <br />
          <span className="text-signal">silently.</span> Cassandra
          <br />
          doesn&rsquo;t blink.
        </h1>
        <p className="mt-7 max-w-xl text-lg leading-relaxed text-ash">
          A meta-agent that watches your production agents through Arize Phoenix —
          catching hallucinations, proving the fix with a real experiment, and shipping
          an A/B-ready prompt patch. Autonomously. In seconds.
        </p>
        <div className="mt-10 flex flex-wrap items-center gap-4">
          <a
            href="#cockpit"
            className="group inline-flex items-center gap-2 rounded-lg bg-signal px-6 py-3.5 font-mono text-sm font-semibold text-ink-0 transition hover:bg-signal-deep"
          >
            Enter the cockpit
            <ArrowDown className="h-4 w-4 transition group-hover:translate-y-0.5" />
          </a>
          <a
            href="#how"
            className="rounded-lg border border-line2 px-6 py-3.5 font-mono text-sm text-bone transition hover:border-signal hover:text-signal"
          >
            How it works
          </a>
        </div>
      </motion.div>

      <div className="absolute bottom-7 left-1/2 -translate-x-1/2 text-slate">
        <ArrowDown className="h-5 w-5 animate-bounce" />
      </div>
    </section>
  );
}
