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
      <span className="text-xs font-semibold uppercase tracking-wide text-black/70">{label}</span>
      <input
        value={value[key]}
        onChange={(e) => onChange({ ...value, [key]: e.target.value })}
        placeholder={placeholder}
        className="w-full rounded-2xl border border-line/50 bg-[#E8E8E8] px-4 py-3 text-sm text-black outline-none ring-accent/20 placeholder:text-black/35 focus:ring-2"
      />
      <span className="text-xs text-black/55">{helper}</span>
    </label>
  );

  return (
    <div className="rounded-3xl border border-line/40 bg-[#E8E8E8] p-6 backdrop-blur">
      <div className="grid gap-4 md:grid-cols-4">
        {input("Occasion", "occasion", "e.g. work presentation", "Examples: date night, casual brunch")}
        {input("Weather", "weather", "e.g. cold rain", "Examples: mild clear, hot humid")}
        {input("Vibe", "vibe", "e.g. quiet luxury", "Examples: streetwear, classic")}
        {input("Preference", "preference", "e.g. no loud logos", "Optional: fit notes, colors to avoid")}
      </div>
    </div>
  );
}

