import { STAGES } from "../lib/stages";
import type { Stage } from "../lib/types";

/** Horizontal pipeline tracker; lights up stages reached for the active incident. */
export function PipelineRibbon({ active }: { active: Stage | null }) {
  const idx = active ? STAGES.findIndex((s) => s.key === active) : -1;
  return (
    <div className="flex flex-wrap items-center gap-1.5">
      {STAGES.map((s, i) => {
        const done = idx >= 0 && i < idx;
        const isActive = i === idx;
        const Icon = s.icon;
        return (
          <div key={s.key} className="flex items-center gap-1.5">
            <div
              className="flex items-center gap-1.5 rounded-md px-2.5 py-1.5 font-mono text-[11px] transition-colors"
              style={{
                color: isActive ? s.hex : done ? "#A7A39B" : "#6C6A66",
                background: isActive ? `${s.hex}1f` : done ? "rgba(244,241,234,0.04)" : "transparent",
                border: `1px solid ${isActive ? `${s.hex}66` : "rgba(244,241,234,0.08)"}`,
              }}
            >
              <Icon className="h-3 w-3" />
              <span className="hidden sm:inline">{s.label}</span>
            </div>
            {i < STAGES.length - 1 && (
              <span
                className="h-px w-3"
                style={{ background: done ? "#A7A39B55" : "rgba(244,241,234,0.12)" }}
              />
            )}
          </div>
        );
      })}
    </div>
  );
}
