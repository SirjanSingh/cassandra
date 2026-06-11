import { useState } from "react";
import { Loader2, Send } from "lucide-react";
import { drivePatient } from "../lib/useEvents";

export function DriveBox() {
  // The canonical on-camera trap: Germany has no policy data -> guaranteed hallucination.
  const [msg, setMsg] = useState(
    "Hi, what's your refund window for orders shipped to Germany?",
  );
  const [reply, setReply] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function send() {
    setBusy(true);
    setReply(null);
    try {
      setReply(await drivePatient(msg));
    } catch (e) {
      setReply(`request failed: ${(e as Error).message}`);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="panel p-5">
      <label
        htmlFor="drive"
        className="eyebrow mb-3 flex items-center gap-2"
      >
        <Send className="h-3 w-3" /> Drive the Patient (ShopBot)
      </label>
      <textarea
        id="drive"
        value={msg}
        onChange={(e) => setMsg(e.target.value)}
        className="h-24 w-full resize-y rounded-lg border border-line2 bg-ink-2 px-3 py-2.5 text-[13px] leading-relaxed text-bone outline-none transition focus:border-signal focus:bg-ink-3"
      />
      <button
        onClick={send}
        disabled={busy}
        className="mt-3 flex min-h-[44px] w-full items-center justify-center gap-2 rounded-lg bg-signal font-mono text-sm font-semibold text-ink-0 transition hover:bg-signal-deep disabled:cursor-progress disabled:opacity-60"
      >
        {busy ? (
          <>
            <Loader2 className="h-4 w-4 animate-spin" /> Sending…
          </>
        ) : (
          <>Send customer message</>
        )}
      </button>
      <div className="mt-3 min-h-[54px] whitespace-pre-wrap rounded-lg border border-line border-l-[3px] border-l-steel bg-ink-2 px-3 py-2.5 text-[12.5px] text-ash">
        {reply ?? <span className="text-slate">— awaiting response —</span>}
      </div>
    </div>
  );
}
