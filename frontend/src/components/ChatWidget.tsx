import { useMemo, useState } from "react";
import type { ChatTurn, RecommendOutfitResponse } from "@/types";

export function ChatWidget({ recommendation }: { recommendation: RecommendOutfitResponse | null }) {
  const [open, setOpen] = useState(false);
  const [input, setInput] = useState("What should I tweak if it rains after work?");
  const [turns, setTurns] = useState<ChatTurn[]>([]);

  const starter = useMemo(
    () =>
      recommendation
        ? `I’d anchor on: ${recommendation.outfit_items.map((i) => i.role).join(", ")}. Want a safer shoe swap or a warmer mid-layer?`
        : "Upload a wardrobe and generate an outfit. Then ask me to tweak it for weather, vibe, or formality.",
    [recommendation],
  );

  const send = () => {
    const trimmed = input.trim();
    if (!trimmed) return;
    const user: ChatTurn = { id: crypto.randomUUID(), role: "user", content: trimmed, ts: new Date().toISOString() };
    const assistant: ChatTurn = {
      id: crypto.randomUUID(),
      role: "assistant",
      content:
        "For rain: add a water-resistant outer layer, swap to shoes with traction, and keep the palette tight (2–3 hues). If you’ll be indoors, a light mid-layer keeps you comfortable without bulk.",
      ts: new Date().toISOString(),
    };
    setTurns((prev) => [...prev, user, assistant]);
    setInput("");
  };

  return (
    <div className="fixed bottom-6 right-6 z-50">
      {open ? (
        <div className="w-[340px] overflow-hidden rounded-3xl border border-line bg-ink-900/80 shadow-2xl backdrop-blur">
          <div className="flex items-center justify-between border-b border-line px-5 py-4">
            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.22em] text-accent">Stylist</p>
              <p className="mt-1 text-xs text-mist/60">Quick outfit help</p>
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
              <span className="font-semibold text-mist">Stylist:</span> {starter}
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
                <p className="mt-1">{t.content}</p>
              </div>
            ))}
          </div>

          <div className="border-t border-line p-4">
            <div className="flex gap-2">
              <input
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter") send();
                }}
                className="flex-1 rounded-2xl border border-line bg-ink-950 px-4 py-3 text-sm text-mist outline-none ring-accent/20 placeholder:text-mist/35 focus:ring-2"
                placeholder="Ask the stylist…"
              />
              <button
                type="button"
                onClick={send}
                className="rounded-2xl bg-mist px-4 py-3 text-sm font-semibold text-ink-950"
              >
                Send
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

