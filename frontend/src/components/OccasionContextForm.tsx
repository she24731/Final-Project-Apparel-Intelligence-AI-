import { Card } from "@/components/ui/Card";

export type OccasionContext = {
  occasion: string;
  weather: string;
  vibe: string;
  preference: string;
};

export function OccasionContextForm({
  value,
  onChange,
  onSubmit,
  busy,
}: {
  value: OccasionContext;
  onChange: (next: OccasionContext) => void;
  onSubmit: () => Promise<void>;
  busy: boolean;
}) {
  const field = (label: string, key: keyof OccasionContext, placeholder: string) => (
    <label className="block space-y-2">
      <span className="text-xs font-medium text-black/70">{label}</span>
      <input
        value={value[key]}
        onChange={(e) => onChange({ ...value, [key]: e.target.value })}
        placeholder={placeholder}
        className="w-full rounded-xl border border-line bg-[#F5F5F5] px-3 py-2 text-sm text-black outline-none ring-accent/30 placeholder:text-black/35 focus:ring-2"
      />
    </label>
  );

  return (
    <Card title="Occasion & context" subtitle="Weather, vibe, and intent shape retrieval + styling agents.">
      <div className="grid gap-4 md:grid-cols-2">
        {field("Occasion", "occasion", "work_presentation")}
        {field("Weather", "weather", "cold_rain")}
        {field("Vibe", "vibe", "quiet_luxury")}
        {field("Style preference", "preference", "no loud logos")}
      </div>
      <div className="mt-5 flex justify-end">
        <button
          type="button"
          disabled={busy}
          onClick={() => void onSubmit()}
          className="rounded-xl bg-accent px-5 py-2 text-sm font-semibold text-ink-950 transition hover:opacity-95 disabled:cursor-not-allowed disabled:opacity-40"
        >
          {busy ? "Reasoning…" : "Recommend outfit"}
        </button>
      </div>
    </Card>
  );
}
