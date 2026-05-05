import { useEffect, useMemo, useRef, useState } from "react";
import type { AssistantTurnResponse, ChatContextPayload, ChatTurn } from "@/types";
import { ApiError, apiPostJson, apiPostMultipart } from "@/lib/api";

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
  const fileRef = useRef<HTMLInputElement | null>(null);
  const [files, setFiles] = useState<File[]>([]);
  const filesRef = useRef<File[]>([]);
  const [dragOver, setDragOver] = useState(false);
  const pendingAutoSendRef = useRef(false);

  const starter = useMemo(
    () =>
      "Ask for outfits, social scripts (LinkedIn / Instagram / TikTok), reel copy, or video. Example: “Write a TikTok script for this outfit” or “Generate video”.",
    [],
  );

  const hasDraggedFiles = (e: React.DragEvent) => {
    const dt = e.dataTransfer;
    if (!dt) return false;
    // Many browsers only populate `types` during dragenter/dragover; `files` is often empty until drop.
    if (dt.types && Array.from(dt.types).includes("Files")) return true;
    if (dt.types && Array.from(dt.types).includes("text/uri-list")) return true;
    if (dt.files && dt.files.length > 0) return true;
    if (dt.items && dt.items.length > 0) return Array.from(dt.items).some((it) => it.kind === "file");
    return false;
  };

  const isLikelyImageFile = (f: File) => {
    if (f.type && f.type.startsWith("image/")) return true;
    const name = (f.name || "").toLowerCase();
    return /\.(jpe?g|png|webp|gif|bmp|tiff?|heic|heif|avif)$/.test(name);
  };

  const addDroppedFiles = (incoming: File[]) => {
    const imgs = incoming.filter(isLikelyImageFile);
    if (!imgs.length) return;
    setFiles((prev) => {
      const next = [...prev, ...imgs].slice(0, 12);
      filesRef.current = next;
      return next;
    });
  };

  const tryFetchImageUrlAsFile = async (url: string): Promise<File | null> => {
    try {
      const res = await fetch(url, { mode: "cors" });
      if (!res.ok) return null;
      const blob = await res.blob();
      if (!blob.type.startsWith("image/")) return null;
      const ext = blob.type.split("/")[1] || "png";
      return new File([blob], `dropped.${ext}`, { type: blob.type });
    } catch {
      return null;
    }
  };

  useEffect(() => {
    filesRef.current = files;
  }, [files]);

  // If we queued an auto-send while busy, flush it once idle.
  useEffect(() => {
    if (busy) return;
    if (!pendingAutoSendRef.current) return;
    if (filesRef.current.length === 0) {
      pendingAutoSendRef.current = false;
      return;
    }
    pendingAutoSendRef.current = false;
    void send();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [busy]);

  // Browser-level drag/drop guard is installed in `src/main.tsx`.

  const send = async () => {
    const trimmed = input.trim();
    if ((!trimmed && filesRef.current.length === 0) || busy) return;
    setBusy(true);
    const messageText = trimmed || (filesRef.current.length ? "Uploaded attachments." : "");
    const user: ChatTurn = { id: crypto.randomUUID(), role: "user", content: messageText, ts: new Date().toISOString() };
    setTurns((prev) => [...prev, user]);
    setInput("");
    try {
      const ctx = {
        occasion: context.occasion,
        weather: context.weather,
        vibe: context.vibe,
        preference: context.preference,
        wardrobe_item_ids: context.wardrobe_item_ids,
        outfit_summary: context.outfit_summary,
        face_anchor_path: context.face_anchor_path,
      };

      const res =
        filesRef.current.length > 0
          ? await apiPostMultipart<AssistantTurnResponse>("/assistant/turn-multipart", (() => {
              const fd = new FormData();
              fd.append("message", messageText);
              fd.append("context_json", JSON.stringify(ctx));
              fd.append("history_json", JSON.stringify(turns.slice(-12)));
              for (const f of filesRef.current) fd.append("files", f);
              return fd;
            })())
          : await apiPostJson<AssistantTurnResponse>("/assistant/turn", { message: trimmed, context: ctx, history: turns.slice(-12) });

      onApplyResult(res);
      const assistant: ChatTurn = {
        id: crypto.randomUUID(),
        role: "assistant",
        content: res.reply,
        ts: new Date().toISOString(),
      };
      setTurns((prev) => [...prev, assistant]);
      setFiles([]);
      filesRef.current = [];
      if (fileRef.current) fileRef.current.value = "";
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
    <div
      className="fixed bottom-6 right-6 z-50"
      onDragEnter={(e) => {
        if (!hasDraggedFiles(e)) return;
        e.preventDefault();
        e.dataTransfer.dropEffect = "copy";
        setDragOver(true);
        if (!open) setOpen(true);
      }}
      onDragOver={(e) => {
        if (!hasDraggedFiles(e)) return;
        e.preventDefault();
        e.dataTransfer.dropEffect = "copy";
        setDragOver(true);
      }}
      onDragLeave={(e) => {
        e.preventDefault();
        // Only clear when leaving the widget container (not when moving between children).
        if (e.currentTarget.contains(e.relatedTarget as Node | null)) return;
        setDragOver(false);
      }}
      onDrop={(e) => {
        e.preventDefault();
        setDragOver(false);
        const dt = e.dataTransfer;
        const next = Array.from(dt?.files ?? []);
        const imgs = next.filter(isLikelyImageFile);

        const uri = (dt?.getData("text/uri-list") || "").trim();

        const doSendSoon = () => {
          if (busy) {
            pendingAutoSendRef.current = true;
            return;
          }
          // Give React a tick to apply filesRef updates, then send.
          setTimeout(() => void send(), 0);
        };

        if (imgs.length) {
          // Visible confirmation that the drop handler fired.
          setTurns((prev) => [
            ...prev,
            {
              id: crypto.randomUUID(),
              role: "assistant",
              content: `Uploading ${imgs.length} image${imgs.length === 1 ? "" : "s"} from drag & drop…`,
              ts: new Date().toISOString(),
            },
          ]);
          addDroppedFiles(imgs);
          doSendSoon();
          return;
        }

        // If the user drags an image from a web page, Chrome often provides a URL (not a File).
        // Best-effort: try to fetch it and upload as a File (may fail due to CORS).
        if (uri) {
          void (async () => {
            const f = await tryFetchImageUrlAsFile(uri);
            if (!f) {
              setTurns((prev) => [
                ...prev,
                {
                  id: crypto.randomUUID(),
                  role: "assistant",
                  content:
                    "I can’t upload that drag source (likely blocked by the website). Please drag the image from Finder/Desktop or use the + button.",
                  ts: new Date().toISOString(),
                },
              ]);
              return;
            }
            setTurns((prev) => [
              ...prev,
              {
                id: crypto.randomUUID(),
                role: "assistant",
                content: "Uploading 1 image from drag & drop…",
                ts: new Date().toISOString(),
              },
            ]);
            addDroppedFiles([f]);
            doSendSoon();
          })();
          return;
        }

        // No usable payload.
        setTurns((prev) => [
          ...prev,
          {
            id: crypto.randomUUID(),
            role: "assistant",
            content:
              "I didn’t receive an image file from that drag action. Try dragging the file from Finder/Desktop, or use the + button.",
            ts: new Date().toISOString(),
          },
        ]);
      }}
    >
      {open ? (
        <div className="relative w-[min(100vw-2rem,380px)] overflow-hidden rounded-3xl border border-line bg-[#F8F6F3] shadow-2xl backdrop-blur">
          {dragOver ? (
            <div className="pointer-events-none absolute inset-0 z-10 grid place-items-center bg-black/10">
              <div className="rounded-2xl border border-accent/40 bg-[#F8F6F3]/95 px-5 py-4 text-center shadow-xl">
                <p className="text-xs font-semibold uppercase tracking-[0.22em] text-accent">Drop to attach</p>
                <p className="mt-1 text-sm font-semibold text-black/80">Images only</p>
                <p className="mt-1 text-xs text-black/55">Then hit Send</p>
              </div>
            </div>
          ) : null}
          <div className="flex items-center justify-between border-b border-line px-5 py-4">
            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.22em] text-accent">Concierge</p>
              <p className="mt-1 text-xs text-black/60">Full app control via chat • drag & drop enabled</p>
            </div>
            <button
              type="button"
              onClick={() => setOpen(false)}
              className="rounded-xl border border-line bg-[#E8E8E8] px-3 py-1.5 text-xs font-semibold text-black/80 hover:border-accent/40"
            >
              Close
            </button>
          </div>

          <div className="max-h-72 space-y-3 overflow-auto px-5 py-4">
            <div className="rounded-2xl border border-line bg-[#E8E8E8] px-4 py-3 text-sm text-black">
              <span className="font-semibold text-black">Tip:</span> {starter}
            </div>
            {turns.map((t) => (
              <div
                key={t.id}
                className={[
                  "rounded-2xl border px-4 py-3 text-sm",
                  t.role === "user" ? "border-line bg-[#E8E8E8] text-black/90" : "border-accent/20 bg-[#F5F5F5] text-black/85",
                ].join(" ")}
              >
                <p className="text-[10px] font-semibold uppercase tracking-wide text-black/40">{t.role}</p>
                <p className="mt-1 whitespace-pre-wrap">{t.content}</p>
              </div>
            ))}
          </div>

          <div className="border-t border-line p-4">
            {files.length > 0 ? (
              <div className="mb-2 flex flex-wrap items-center gap-2">
                {files.slice(0, 6).map((f, idx) => (
                  <button
                    key={`${f.name}-${idx}`}
                    type="button"
                    disabled={busy}
                    onClick={() => setFiles((prev) => prev.filter((_, i) => i !== idx))}
                    className="rounded-full border border-line bg-[#E8E8E8] px-3 py-1.5 text-[11px] font-semibold text-black/75 hover:border-accent/40 disabled:opacity-40"
                    title="Remove attachment"
                  >
                    {f.name.length > 18 ? `${f.name.slice(0, 8)}…${f.name.slice(-7)}` : f.name} ×
                  </button>
                ))}
                {files.length > 6 ? (
                  <span className="text-[11px] font-semibold text-black/45">+{files.length - 6} more</span>
                ) : null}
                <button
                  type="button"
                  disabled={busy}
                  onClick={() => {
                    setFiles([]);
                    if (fileRef.current) fileRef.current.value = "";
                  }}
                  className="ml-auto rounded-full border border-line bg-[#E8E8E8] px-3 py-1.5 text-[11px] font-semibold text-black/60 hover:border-accent/40 disabled:opacity-40"
                  title="Clear all attachments"
                >
                  Clear
                </button>
              </div>
            ) : null}
            <div className="flex gap-2">
              <input
                ref={fileRef}
                type="file"
                accept="image/*"
                multiple
                className="hidden"
                onChange={(e) => {
                  const next = Array.from(e.target.files ?? []);
                  addDroppedFiles(next);
                }}
              />
              <button
                type="button"
                disabled={busy}
                onClick={() => fileRef.current?.click()}
                className="rounded-2xl border border-line bg-[#E8E8E8] px-4 py-3 text-base font-semibold text-black/85 hover:border-accent/40 disabled:opacity-40"
                title="Add images (selfie first, then clothing)"
              >
                +
              </button>
              <input
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" && !e.shiftKey) void send();
                }}
                className="flex-1 rounded-2xl border border-line bg-[#F5F5F5] px-4 py-3 text-sm text-black outline-none ring-accent/20 placeholder:text-black/35 focus:ring-2"
                placeholder="Ask the concierge…"
              />
              <button
                type="button"
                disabled={busy}
                onClick={() => void send()}
                className="rounded-2xl bg-[#C8A96A] px-4 py-3 text-sm font-semibold text-black disabled:opacity-40"
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
