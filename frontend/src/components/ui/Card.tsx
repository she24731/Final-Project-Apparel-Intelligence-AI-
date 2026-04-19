import type { PropsWithChildren, ReactNode } from "react";

export function Card({
  title,
  subtitle,
  right,
  children,
}: PropsWithChildren<{ title: string; subtitle?: string; right?: ReactNode }>) {
  return (
    <section className="rounded-2xl border border-line bg-ink-900/60 shadow-[0_0_0_1px_rgba(255,255,255,0.02)] backdrop-blur">
      <header className="flex items-start justify-between gap-4 border-b border-line px-6 py-5">
        <div>
          <h2 className="text-sm font-semibold tracking-wide text-mist">{title}</h2>
          {subtitle ? <p className="mt-1 text-xs text-mist/60">{subtitle}</p> : null}
        </div>
        {right}
      </header>
      <div className="px-6 py-5">{children}</div>
    </section>
  );
}
