import { AgentChatPanel } from "@/components/AgentChatPanel";
import type { RecommendOutfitResponse } from "@/types";

export function ChatPage({ recommendation }: { recommendation: RecommendOutfitResponse | null }) {
  return (
    <div className="space-y-10">
      <section>
        <h2 className="text-2xl font-semibold tracking-tight text-mist md:text-3xl">Chat</h2>
        <p className="mt-2 text-sm text-mist/65">Ask the stylist anything—what to wear, what to tweak, what to skip.</p>
      </section>
      <AgentChatPanel recommendation={recommendation} />
    </div>
  );
}

