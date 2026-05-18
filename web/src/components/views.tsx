import { CheckCircle2, XCircle } from "lucide-react";
import type { PipelineEvent } from "../lib/types";

export function DiffView({ diff }: { diff: string }) {
  const lines = diff.split("\n");
  return (
    <div className="mt-4 overflow-hidden rounded-lg border border-line2">
      <div className="border-b border-line bg-ink-2 px-3 py-2 font-mono text-[11px] uppercase tracking-wide2 text-slate">
        prompt patch · unified diff
      </div>
      <div className="max-h-72 overflow-auto font-mono text-xs leading-relaxed">
        {lines.map((l, i) => {
          const add = l.startsWith("+") && !l.startsWith("+++");
          const del = l.startsWith("-") && !l.startsWith("---");
          const hd = l.startsWith("@@") || l.startsWith("+++") || l.startsWith("---");
          const cls = add
            ? "bg-good/10 text-[#5be9b9]"
            : del
              ? "bg-alert/10 text-[#ff9a93]"
              : hd
                ? "bg-signal/10 text-signal"
                : "text-ash";
          return (
            <div key={i} className={`flex px-3 ${cls}`}>
              <span className="w-4 select-none text-slate">
                {add ? "+" : del ? "-" : " "}
              </span>
              <span className="whitespace-pre-wrap break-words">
                {add || del ? l.slice(1) : l || " "}
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}

export function RootCauseChain({ ev }: { ev: PipelineEvent }) {
  const chain = ev.payload?.causal_chain ?? [];
  const fix = ev.payload?.fix_strategy;
  return (
    <div className="mt-4">
      <div className="flex flex-col">
        {chain.map((s, i) => (
          <div key={i} className="relative flex gap-3 pb-3 last:pb-0">
            {i < chain.length - 1 && (
              <span className="absolute left-[11px] top-6 bottom-0 w-px bg-line2" />
            )}
            <span className="z-[1] grid h-[22px] w-[22px] flex-none place-items-center rounded-full border border-line2 bg-ink-2 font-mono text-[10px] text-ash">
              {i + 1}
            </span>
            <span className="pt-0.5 text-sm text-ash">{s}</span>
          </div>
        ))}
      </div>
      {fix && (
        <div className="mt-4 rounded-lg border border-signal/25 bg-signal/[0.07] px-3 py-3 text-sm text-[#f0c987]">
          <b className="font-semibold text-signal">Fix strategy · </b>
          {fix}
        </div>
      )}
    </div>
  );
}

export function ReplayView({ ev }: { ev: PipelineEvent }) {
  const p = ev.payload ?? {};
  const fixed = !!p.fixed;
  return (
    <div className="mt-4">
      <span
        className={`inline-flex items-center gap-1.5 rounded-full border px-3 py-1 font-mono text-[11px] font-semibold ${
          fixed
            ? "border-good/40 bg-good/15 text-[#5be9b9]"
            : "border-alert/40 bg-alert/15 text-[#ff9a93]"
        }`}
      >
        {fixed ? <CheckCircle2 className="h-3.5 w-3.5" /> : <XCircle className="h-3.5 w-3.5" />}
        {fixed ? "FIXED" : "STILL BROKEN"}
      </span>
      <div className="mt-3 grid gap-3 sm:grid-cols-2">
        <div className="overflow-hidden rounded-lg border border-line2">
          <div className="bg-alert/15 px-3 py-2 font-mono text-[11px] uppercase tracking-wide2 text-[#ff9a93]">
            Before · original
          </div>
          <div className="max-h-44 overflow-auto whitespace-pre-wrap bg-ink-2 px-3 py-3 text-xs text-ash">
            {p.before}
          </div>
        </div>
        <div className="overflow-hidden rounded-lg border border-line2">
          <div className="bg-good/15 px-3 py-2 font-mono text-[11px] uppercase tracking-wide2 text-[#5be9b9]">
            After · patched
          </div>
          <div className="max-h-44 overflow-auto whitespace-pre-wrap bg-ink-2 px-3 py-3 text-xs text-ash">
            {p.after}
          </div>
        </div>
      </div>
    </div>
  );
}

export function RedTeamTable({ ev }: { ev: PipelineEvent }) {
  const rows = ev.payload?.rows ?? [];
  const Tag = ({ ok }: { ok: boolean }) => (
    <span
      className={`inline-flex items-center rounded px-2 py-0.5 font-mono text-[10.5px] font-semibold ${
        ok ? "bg-good/15 text-[#5be9b9]" : "bg-alert/15 text-[#ff9a93]"
      }`}
    >
      {ok ? "PASS" : "FAIL"}
    </span>
  );
  return (
    <div className="mt-4 overflow-hidden rounded-lg border border-line2">
      <table className="w-full border-collapse text-xs">
        <thead>
          <tr className="bg-ink-2 text-left font-mono text-[10.5px] uppercase tracking-wide2 text-slate">
            <th className="px-3 py-2 font-semibold">adversarial probe</th>
            <th className="px-3 py-2 font-semibold">current</th>
            <th className="px-3 py-2 font-semibold">patched</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r, i) => (
            <tr key={i} className="border-t border-line">
              <td className="px-3 py-2 text-bone">{r.attack}</td>
              <td className="px-3 py-2">
                <Tag ok={r.before_pass} />
              </td>
              <td className="px-3 py-2">
                <Tag ok={r.after_pass} />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
