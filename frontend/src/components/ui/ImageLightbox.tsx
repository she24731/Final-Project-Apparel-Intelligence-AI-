import { createContext, useContext, useMemo, useState } from "react";

type LightboxState = { src: string; alt?: string } | null;

const Ctx = createContext<{ open: (src: string, alt?: string) => void } | null>(null);

export function ImageLightboxProvider({ children }: { children: React.ReactNode }) {
  const [state, setState] = useState<LightboxState>(null);

  const api = useMemo(
    () => ({
      open: (src: string, alt?: string) => setState({ src, alt }),
    }),
    [],
  );

  return (
    <Ctx.Provider value={api}>
      {children}
      {state ? (
        <div
          className="fixed inset-0 z-[80] flex items-center justify-center bg-black/70 p-6 backdrop-blur"
          role="dialog"
          aria-modal="true"
          onClick={() => setState(null)}
        >
          <div className="w-full max-w-4xl">
            {/\.(mp4|webm)(\?|#|$)/i.test(state.src) ? (
              <video
                src={state.src}
                controls
                playsInline
                className="max-h-[82vh] w-full rounded-3xl border border-line bg-ink-950 object-contain shadow-2xl"
                onClick={(e) => e.stopPropagation()}
              />
            ) : (
              <img
                src={state.src}
                alt={state.alt ?? "Image preview"}
                className="max-h-[82vh] w-full rounded-3xl border border-line bg-ink-950 object-contain shadow-2xl"
                onClick={(e) => e.stopPropagation()}
              />
            )}
            <button
              type="button"
              onClick={() => setState(null)}
              className="mt-4 w-full rounded-2xl border border-line bg-ink-950/60 px-4 py-3 text-sm font-semibold text-mist hover:border-accent/50"
            >
              Close
            </button>
          </div>
        </div>
      ) : null}
    </Ctx.Provider>
  );
}

export function useImageLightbox() {
  const v = useContext(Ctx);
  if (!v) throw new Error("useImageLightbox must be used within ImageLightboxProvider");
  return v;
}

