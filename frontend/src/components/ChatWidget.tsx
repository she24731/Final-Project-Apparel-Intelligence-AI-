import { useMemo, useState } from "react";
import type { AssistantTurnResponse, ChatContextPayload, ChatTurn } from "@/types";
import { ApiError, apiPostJson } from "@/lib/api";

export function ChatWidget({
  context,
  onApplyResult,
}: {
  context: ChatContextPayload;
  onApplyResult: (res: AssistantTurnResponse) => void;
}) {
  const [open, setOpen] = useState(false);
  const [input, setInput] = useState("Recommend an outfit for a rainy work day.");
  const [turns, setTurns] = useState<ChatTurn[]>([]);
  const [busy, setBusy] = useState(false);

  const starter = useMemo(
    () =>
      "Ask for outfits, social scripts (LinkedIn / Instagram / TikTok), reel copy, or video. Example: “Write a TikTok script for this outfit” or “Generate video”.",
    [],
  );

  const send = async () => {
    const trimmed = input.trim();
    if (!trimmed || busy) return;
    setBusy(true);
    const user: ChatTurn = { id: crypto.randomUUID(), role: "user", content: trimmed, ts: new Date().toISOString() };
    setTurns((prev) => [...prev, user]);
    setInput("");
    try {
      const res = await apiPostJson<AssistantTurnResponse>("/assistant/turn", {
        message: trimmed,
        context: {
          occasion: context.occasion,
          weather: context.weather,
          vibe: context.vibe,
          preference: context.preference,
          wardrobe_item_ids: context.wardrobe_item_ids,
          outfit_summary: context.outfit_summary,
          face_anchor_path: context.face_anchor_path,
        },
      });
      onApplyResult(res);
      const assistant: ChatTurn = {
        id: crypto.randomUUID(),
        role: "assistant",
        content: res.reply,
        ts: new Date().toISOString(),
      };
      setTurns((prev) => [...prev, assistant]);
    } catch (e) {
      const msg =
        e instanceof ApiError
          ? `Assistant error (${e.status}). ${e.body}`
          : "Couldn’t reach the assistant. Is the backend running on port 8000?";
      const assistant: ChatTurn = {
        id: crypto.randomUUID(),
        role: "assistant",
        content: msg,
        ts: new Date().toISOString(),
      };
      setTurns((prev) => [...prev, assistant]);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="fixed bottom-6 right-6 z-50">
      {open ? (
        <div className="w-[min(100vw-2rem,380px)] overflow-hidden rounded-3xl border border-line bg-ink-900/80 shadow-2xl backdrop-blur">
          <div className="flex items-center justify-between border-b border-line px-5 py-4">
            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.22em] text-accent">Concierge</p>
              <p className="mt-1 text-xs text-mist/60">Full app control via chat</p>
            </div>
            <button
              type="button"
              onClick={() => setOpen(false)}
              className="rounded-xl border border-line bg-ink-950 px-3 py-1.5 text-xs font-semibold text-mist/80 hover:border-accent/40"
            >
              Close
            </button>
          </div>

          <div className="max-h-72 space-y-3 overflow-auto px-5 py-4">
            <div className="rounded-2xl border border-line bg-ink-950/40 px-4 py-3 text-sm text-mist/80">
              <span className="font-semibold text-mist">Tip:</span> {starter}
            </div>
            {turns.map((t) => (
              <div
                key={t.id}
                className={[
                  "rounded-2xl border px-4 py-3 text-sm",
                  t.role === "user" ? "border-line bg-ink-950 text-mist/90" : "border-accent/20 bg-ink-900 text-mist/85",
                ].join(" ")}
              >
                <p className="text-[10px] font-semibold uppercase tracking-wide text-mist/40">{t.role}</p>
                <p className="mt-1 whitespace-pre-wrap">{t.content}</p>
              </div>
            ))}
          </div>

          <div className="border-t border-line p-4">
            <div className="flex gap-2">
              <input
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" && !e.shiftKey) void send();
                }}
                className="flex-1 rounded-2xl border border-line bg-ink-950 px-4 py-3 text-sm text-mist outline-none ring-accent/20 placeholder:text-mist/35 focus:ring-2"
                placeholder="Ask the concierge…"
              />
              <button
                type="button"
                disabled={busy}
                onClick={() => void send()}
                className="rounded-2xl bg-mist px-4 py-3 text-sm font-semibold text-ink-950 disabled:opacity-40"
              >
                {busy ? "…" : "Send"}
              </button>
            </div>
          </div>
        </div>
      ) : (
        <button
          type="button"
          onClick={() => setOpen(true)}
          className="rounded-full bg-mist px-5 py-3 text-sm font-semibold text-ink-950 shadow-lg"
        >
          Chat
        </button>
      )}
    </div>
  );
}
