import {
  Eye,
  AlertTriangle,
  Search,
  Database,
  BarChart3,
  Wrench,
  RotateCcw,
  Crosshair,
  type LucideIcon,
} from "lucide-react";
import type { Stage } from "./types";

export interface StageMeta {
  key: Stage;
  label: string;
  icon: LucideIcon;
  /** tailwind text color class */
  tone: string;
  /** raw hex for borders / inline accents */
  hex: string;
}

export const STAGES: StageMeta[] = [
  { key: "watched", label: "Watched", icon: Eye, tone: "text-steel", hex: "#5A6B82" },
  { key: "diagnosed", label: "Diagnosed", icon: AlertTriangle, tone: "text-alert", hex: "#F0443E" },
  { key: "root_caused", label: "Root cause", icon: Search, tone: "text-signal", hex: "#F2A93B" },
  { key: "synthesized", label: "Synthesized", icon: Database, tone: "text-bone", hex: "#F4F1EA" },
  { key: "evaluated", label: "Evaluated", icon: BarChart3, tone: "text-steel", hex: "#7C8DA6" },
  { key: "patched", label: "Patched", icon: Wrench, tone: "text-good", hex: "#21C07A" },
  { key: "replayed", label: "Replayed", icon: RotateCcw, tone: "text-signal", hex: "#F2A93B" },
  { key: "red_teamed", label: "Red-team", icon: Crosshair, tone: "text-alert", hex: "#F0443E" },
];

export const STAGE_MAP: Record<Stage, StageMeta> = Object.fromEntries(
  STAGES.map((s) => [s.key, s]),
) as Record<Stage, StageMeta>;
