import { useMemo, useState } from "react";
import { Card } from "@/components/ui/Card";
import type { ChatTurn, RecommendOutfitResponse } from "@/types";

export function AgentChatPanel({ recommendation }: { recommendation: RecommendOutfitResponse | null }) {
  const [input, setInput] = useState("What should I tweak if it rains after work?");
  const [turns, setTurns] = useState<ChatTurn[]>([]);

  const starter = useMemo(
    () =>
      recommendation
        ? `I’d anchor on: ${recommendation.outfit_items
            .map((i) => i.role)
            .join(", ")}. Want a safer shoe swap or a warmer mid-layer?`
        : "Upload a wardrobe and generate an outfit—I'll reason over the same context window as the stylist agent in the backend MVP.",
    [recommendation],
  );

  return (
    <Card title="Stylist chat" subtitle="Ask for alternatives, tweaks, or a second opinion.">
      <div className="mb-4 rounded-xl border border-line bg-ink-950/40 p-4 text-sm text-mist/75">
        <span className="font-semibold text-mist">Stylist:</span> {starter}
      </div>

      <div className="max-h-64 space-y-3 overflow-auto pr-1">
        {turns.length === 0 ? (
          <p className="text-xs text-mist/45">No messages yet.</p>
        ) : (
          turns.map((t) => (
            <div key={t.id} className={`rounded-xl border px-3 py-2 text-sm ${t.role === "user" ? "border-line bg-ink-950" : "border-accent/25 bg-ink-900"}`}>
              <p className="text-[10px] font-semibold uppercase tracking-wide text-mist/40">{t.role}</p>
              <p className="mt-1 text-mist/85">{t.content}</p>
            </div>
          ))
        )}
      </div>

      <div className="mt-4 flex gap-2">
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          className="flex-1 rounded-xl border border-line bg-ink-950 px-3 py-2 text-sm text-mist outline-none ring-accent/30 focus:ring-2"
          placeholder="Ask the stylist…"
        />
        <button
          type="button"
          onClick={() => {
            const user: ChatTurn = {
              id: crypto.randomUUID(),
              role: "user",
              content: input,
              ts: new Date().toISOString(),
            };
            const assistant: ChatTurn = {
              id: crypto.randomUUID(),
              role: "assistant",
              content:
                "Mock reply: I’d keep the palette at three hues, swap to a water-resistant shoe if precipitation >40%, and let one texture (wool or leather) carry the story.",
              ts: new Date().toISOString(),
            };
            setTurns((prev) => [...prev, user, assistant]);
          }}
          className="rounded-xl bg-mist px-4 py-2 text-sm font-semibold text-ink-950"
        >
          Send
        </button>
      </div>
    </Card>
  );
}
