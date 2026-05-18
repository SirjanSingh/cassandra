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
      <header className="fixed inset-x-0 top-0 z-50 border-b border-line bg-ink-0/70 backdrop-blur-md">
        <div className="mx-auto flex max-w-7xl items-center gap-3 px-6 py-3.5">
          <div className="grid h-8 w-8 place-items-center rounded-lg bg-signal">
            <span className="font-display text-sm font-bold text-ink-0">C</span>
          </div>
          <span className="font-display text-sm font-semibold tracking-tightish">
            Cassandra
          </span>
          <span className="hidden font-mono text-[11px] text-slate sm:inline">
            / meta-agent observability
          </span>
          <nav className="ml-auto flex items-center gap-6 font-mono text-xs text-ash">
            <a href="#how" className="transition hover:text-bone">
              How
            </a>
            <a href="#cockpit" className="transition hover:text-bone">
              Cockpit
            </a>
            <a
              href="https://github.com/SirjanSingh/cassandra"
              target="_blank"
              rel="noopener noreferrer"
              className="rounded-md border border-line2 px-3 py-1.5 transition hover:border-signal hover:text-signal"
            >
              GitHub
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
