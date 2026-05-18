import { useEffect } from "react";
import Lenis from "lenis";
import { Hero } from "./components/Hero";
import { Manifesto } from "./components/Manifesto";
import { Cockpit } from "./components/Cockpit";

export default function App() {
  useEffect(() => {
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    const lenis = new Lenis({ duration: 1.1, smoothWheel: true });
    let raf = 0;
    const loop = (t: number) => {
      lenis.raf(t);
      raf = requestAnimationFrame(loop);
    };
    raf = requestAnimationFrame(loop);
    return () => {
      cancelAnimationFrame(raf);
      lenis.destroy();
    };
  }, []);

  return (
    <>
      <header className="fixed inset-x-0 top-0 z-50 border-b border-line bg-ink-0/80 backdrop-blur-md">
        <div className="mx-auto flex h-12 max-w-7xl items-center gap-4 px-6">
          <span className="font-display text-[13px] font-semibold tracking-tightish">
            Cassandra
          </span>
          <span className="hidden items-center gap-2 font-mono text-[11px] text-slate md:flex">
            <span className="h-1.5 w-1.5 rounded-full bg-good" />
            supervising · patient-prod
          </span>
          <nav className="ml-auto flex items-center gap-7 font-mono text-[11px] text-slate">
            <a href="#how" className="transition-colors hover:text-bone">
              how
            </a>
            <a href="#cockpit" className="transition-colors hover:text-bone">
              cockpit
            </a>
            <a
              href="https://github.com/SirjanSingh/cassandra"
              target="_blank"
              rel="noopener noreferrer"
              className="text-ash underline-offset-4 transition-colors hover:text-signal hover:underline"
            >
              github ↗
            </a>
          </nav>
        </div>
      </header>

      <main>
        <Hero />
        <Manifesto />
        <Cockpit />
      </main>

      <footer className="border-t border-line bg-ink-0 py-10">
        <div className="mx-auto flex max-w-7xl flex-col gap-2 px-6 font-mono text-xs text-slate sm:flex-row sm:items-center sm:justify-between">
          <span>Cassandra — an agent that babysits agents.</span>
          <span>
            Gemini 3 · Google Cloud Agent Builder · Arize Phoenix MCP · Apache-2.0
          </span>
        </div>
      </footer>
    </>
  );
}
