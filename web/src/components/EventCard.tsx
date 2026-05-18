import { motion, useReducedMotion } from "framer-motion";
import { ExternalLink } from "lucide-react";
import type { PipelineEvent } from "../lib/types";
import { STAGE_MAP } from "../lib/stages";
import { DiffView, RedTeamTable, ReplayView, RootCauseChain } from "./views";

function Sub({ ev }: { ev: PipelineEvent }) {
  if (ev.stage === "patched" && ev.payload?.diff) return <DiffView diff={ev.payload.diff} />;
  if (ev.stage === "root_caused") return <RootCauseChain ev={ev} />;
  if (ev.stage === "replayed") return <ReplayView ev={ev} />;
  if (ev.stage === "red_teamed") return <RedTeamTable ev={ev} />;
  return null;
}

export function EventCard({ ev }: { ev: PipelineEvent }) {
  const reduce = useReducedMotion();
  const meta = STAGE_MAP[ev.stage];
  const Icon = meta?.icon;
  const alert = ev.stage === "diagnosed";
  const time = (() => {
    try {
      return new Date(ev.at).toLocaleTimeString([], { hour12: false });
    } catch {
      return "";
    }
  })();

  return (
    <motion.article
      initial={reduce ? false : { opacity: 0, y: 14 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4, ease: [0.22, 0.61, 0.36, 1] }}
      className="rounded-xl border bg-ink-1 p-4 sm:p-5"
      style={{
        borderColor: alert ? "rgba(240,68,62,0.45)" : "rgba(244,241,234,0.08)",
        borderLeft: `3px solid ${meta?.hex ?? "#F2A93B"}`,
        boxShadow: alert ? "0 0 26px -10px rgba(240,68,62,0.5)" : undefined,
      }}
    >
      <div className="flex items-center gap-2.5">
        <span
          className="inline-flex items-center gap-1.5 rounded-md border px-2 py-1 font-mono text-[10.5px] font-semibold uppercase tracking-wide2"
          style={{
            color: meta?.hex,
            borderColor: `${meta?.hex}55`,
            background: `${meta?.hex}1f`,
          }}
        >
          {Icon && <Icon className="h-3 w-3" />}
          {meta?.label ?? ev.stage}
        </span>
        <span className="font-mono text-[11px] text-slate">{ev.incident_id}</span>
        <span className="ml-auto font-mono text-[11px] text-slate">{time}</span>
      </div>
      <h3 className="mt-2.5 font-display text-[15px] font-semibold leading-snug">
        {ev.title}
      </h3>
      {ev.detail && <p className="mt-1.5 text-[13px] leading-relaxed text-ash">{ev.detail}</p>}
      {ev.phoenix_url && (
        <a
          href={ev.phoenix_url}
          target="_blank"
          rel="noopener noreferrer"
          className="mt-3 inline-flex items-center gap-1.5 rounded-lg border border-line2 bg-ink-2 px-3 py-1.5 text-[11.5px] text-ash transition hover:border-signal hover:text-bone"
        >
          <ExternalLink className="h-3 w-3 text-signal" />
          open in Phoenix
        </a>
      )}
      <Sub ev={ev} />
    </motion.article>
  );
}
