import type { PropsWithChildren, ReactNode } from "react";

export function Card({
  title,
  subtitle,
  right,
  children,
}: PropsWithChildren<{ title: string; subtitle?: string; right?: ReactNode }>) {
  return (
    <section className="rounded-2xl border border-line/40 bg-[#E8E8E8] shadow-[0_4px_12px_rgba(0,0,0,0.08)] backdrop-blur">
      <header className="flex items-start justify-between gap-4 border-b border-line/30 px-6 py-5">
        <div>
          <h2 className="text-sm font-semibold tracking-wide text-black">{title}</h2>
          {subtitle ? <p className="mt-1 text-xs text-black/60">{subtitle}</p> : null}
        </div>
        {right}
      </header>
      <div className="px-6 py-5">{children}</div>
    </section>
  );
}
