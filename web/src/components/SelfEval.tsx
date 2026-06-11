import { useState } from "react";
import { Brain, Loader2 } from "lucide-react";

interface PerClass {
  [label: string]: { total: number; correct: number };
}
interface Scorecard {
  total: number;
  correct: number;
  accuracy: number;
  per_class: PerClass;
  error?: string;
}

/** Cassandra grading its OWN diagnostic accuracy against the labeled trap library
 *  (POST /selfeval — runs the live Patient + Diagnostician; takes a minute or two). */
export function SelfEval() {
  const [card, setCard] = useState<Scorecard | null>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  async function run() {
    setBusy(true);
    setErr(null);
    try {
      const r = await fetch("/selfeval", { method: "POST" });
      const j = (await r.json()) as Scorecard;
      if (j.error) setErr(j.error);
      else setCard(j);
    } catch (e) {
      setErr(`request failed: ${(e as Error).message}`);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="panel p-5">
      <div className="eyebrow mb-3 flex items-center gap-2">
        <Brain className="h-3 w-3" /> Self-evaluation · diagnostic accuracy
      </div>
      <button
        onClick={run}
        disabled={busy}
        className="flex min-h-[40px] w-full items-center justify-center gap-2 rounded-lg border border-line2 bg-ink-2 font-mono text-[12.5px] font-semibold text-ash transition hover:border-signal hover:text-bone disabled:cursor-progress disabled:opacity-60"
      >
        {busy ? (
          <>
            <Loader2 className="h-3.5 w-3.5 animate-spin" /> Grading 11 traps… (~1–2 min)
          </>
        ) : (
          <>Grade my own diagnoses</>
        )}
      </button>
      {err && (
        <p className="mt-3 rounded-lg border border-alert/40 bg-ink-2 px-3 py-2 text-[12px] text-alert">
          {err}
        </p>
      )}
      {card && (
        <div className="mt-3">
          <div className="flex items-baseline gap-2">
            <span className="font-mono text-2xl font-semibold text-good">
              {Math.round(card.accuracy * 100)}%
            </span>
            <span className="font-mono text-[11px] text-slate">
              {card.correct}/{card.total} traps correct
            </span>
          </div>
          <div className="mt-2 flex flex-col gap-1">
            {Object.entries(card.per_class).map(([label, c]) => (
              <div
                key={label}
                className="flex items-center justify-between font-mono text-[11px]"
              >
                <span className="text-ash">{label}</span>
                <span className={c.correct === c.total ? "text-good" : "text-signal"}>
                  {c.correct}/{c.total}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}
      {!card && !err && (
        <p className="mt-3 text-[12px] leading-relaxed text-slate">
          The watcher, watching itself: Cassandra fires its hand-labeled trap library at
          the live Patient and scores its own verdicts against ground truth.
        </p>
      )}
    </div>
  );
}
