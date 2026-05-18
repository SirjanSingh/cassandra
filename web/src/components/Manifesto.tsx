import { motion, useScroll, useTransform } from "framer-motion";
import { useRef } from "react";
import { Reveal } from "./Reveal";

const STEPS = [
  ["01", "Watch", "Polls Phoenix spans on a schedule — no sampling by hand."],
  ["02", "Diagnose", "Gemini-3 LLM-as-judge classifies the failure, annotates the span."],
  ["03", "Root-cause", "Reconstructs the causal chain from trigger to bad output."],
  ["04", "Synthesize", "Turns one failure into a 12-case adversarial dataset."],
  ["05", "Prove", "Phoenix experiment: current vs candidate prompt, scored."],
  ["06", "Patch", "Versioned prompt fix, A/B queued — never auto-shipped."],
];

export function Manifesto() {
  const ref = useRef<HTMLElement>(null);
  const { scrollYProgress } = useScroll({
    target: ref,
    offset: ["start end", "end start"],
  });
  const imgY = useTransform(scrollYProgress, [0, 1], ["-12%", "12%"]);

  return (
    <section id="how" ref={ref} className="relative border-t border-line bg-ink-0">
      <div className="mx-auto max-w-6xl px-6 py-28">
        <Reveal>
          <div className="eyebrow mb-5">The problem nobody watches</div>
          <h2 className="max-w-3xl font-display text-[clamp(2rem,4.4vw,3.6rem)] font-bold leading-tight tracking-tightish">
            Every team running LLM agents in production catches failures with{" "}
            <span className="text-ash">human eyeballs.</span> It does not scale.
          </h2>
        </Reveal>

        <div className="mt-16 grid gap-10 md:grid-cols-[1.05fr_1fr] md:items-center">
          <Reveal className="relative overflow-hidden rounded-2xl border border-line">
            <div className="grain relative aspect-[4/3]">
              <motion.img
                style={{ y: imgY }}
                src="/img/manifesto.jpg"
                alt="Operations control surface at low light"
                className="absolute inset-0 h-[124%] w-full object-cover opacity-30 [filter:grayscale(1)]"
              />
              <div className="absolute inset-0 bg-gradient-to-t from-ink-0 via-ink-0/40 to-transparent" />
              <div className="scanline" />
              <div className="absolute bottom-6 left-6 right-6">
                <div className="font-mono text-xs text-slate">incident · inc-7f3a91c2</div>
                <div className="mt-2 font-display text-2xl font-semibold text-bone">
                  &ldquo;Sure — Germany gets a full 90-day cash refund.&rdquo;
                </div>
                <div className="mt-1 font-mono text-xs text-alert">
                  fabricated · the refund tool returned nothing
                </div>
              </div>
            </div>
          </Reveal>

          <div className="grid grid-cols-2 gap-px overflow-hidden rounded-2xl border border-line bg-line">
            {STEPS.map(([n, t, d], i) => (
              <Reveal key={n} delay={i * 0.05} className="bg-ink-1 p-6">
                <div className="font-mono text-xs text-signal">{n}</div>
                <div className="mt-3 font-display text-lg font-semibold">{t}</div>
                <div className="mt-1.5 text-sm leading-relaxed text-ash">{d}</div>
              </Reveal>
            ))}
          </div>
        </div>
      </div>
    </section>
  );
}
