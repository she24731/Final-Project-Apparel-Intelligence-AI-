export type StyleContext = {
  occasion: string;
  weather: string;
  vibe: string;
  preference: string;
};

export function StyleContextBar({
  value,
  onChange,
}: {
  value: StyleContext;
  onChange: (v: StyleContext) => void;
}) {
  const input = (
    label: string,
    key: keyof StyleContext,
    placeholder: string,
    helper: string,
  ) => (
    <label className="flex flex-col gap-2">
      <span className="text-xs font-semibold uppercase tracking-wide text-mist/50">{label}</span>
      <input
        value={value[key]}
        onChange={(e) => onChange({ ...value, [key]: e.target.value })}
        placeholder={placeholder}
        className="w-full rounded-2xl border border-line bg-ink-950 px-4 py-3 text-sm text-mist outline-none ring-accent/20 placeholder:text-mist/35 focus:ring-2"
      />
      <span className="text-xs text-mist/45">{helper}</span>
    </label>
  );

  return (
    <div className="rounded-3xl border border-line bg-ink-900/50 p-6 backdrop-blur">
      <div className="grid gap-4 md:grid-cols-4">
        {input("Occasion", "occasion", "e.g. work_presentation", "Examples: date_night, casual_brunch")}
        {input("Weather", "weather", "e.g. cold_rain", "Examples: mild_clear, hot_humid")}
        {input("Vibe", "vibe", "e.g. quiet_luxury", "Examples: streetwear, classic")}
        {input("Preference", "preference", "e.g. no loud logos", "Optional: fit notes, colors to avoid")}
      </div>
    </div>
  );
}

