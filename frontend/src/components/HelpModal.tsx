import type { ReactNode } from "react";

export function HelpModal({
  open,
  title = "How to use Apparel Intelligence",
  onClose,
  children,
}: {
  open: boolean;
  title?: string;
  onClose: () => void;
  children: ReactNode;
}) {
  if (!open) return null;
  return (
    <div className="fixed inset-0 z-[60]">
      <div className="absolute inset-0 bg-black/60" onClick={onClose} />
      <div className="absolute left-1/2 top-1/2 w-[92vw] max-w-2xl -translate-x-1/2 -translate-y-1/2 rounded-3xl border border-line bg-[#F8F6F3] shadow-2xl backdrop-blur">
        <div className="flex items-start justify-between gap-4 border-b border-line px-6 py-5">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.22em] text-accent">Help</p>
            <h3 className="mt-2 text-xl font-semibold tracking-tight text-black">{title}</h3>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="rounded-xl border border-line bg-[#E8E8E8] px-3 py-2 text-sm font-semibold text-black/80 hover:border-accent/40"
          >
            Close
          </button>
        </div>
        <div className="px-6 py-6">{children}</div>
      </div>
    </div>
  );
}

