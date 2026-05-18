// Mirrors cassandra.models.PipelineEvent (backend SSE payload).
export type Stage =
  | "watched"
  | "diagnosed"
  | "root_caused"
  | "synthesized"
  | "evaluated"
  | "patched"
  | "replayed"
  | "red_teamed";

export interface PipelineEvent {
  incident_id: string;
  stage: Stage;
  at: string;
  title: string;
  detail?: string;
  phoenix_url?: string | null;
  payload?: {
    diff?: string;
    causal_chain?: string[];
    contributing_factors?: string[];
    fix_strategy?: string;
    before?: string;
    after?: string;
    fixed?: boolean;
    rows?: { attack: string; before_pass: boolean; after_pass: boolean }[];
    examples?: unknown[];
    annotated?: boolean;
  };
}

export type ConnState = "connecting" | "live" | "lost";
