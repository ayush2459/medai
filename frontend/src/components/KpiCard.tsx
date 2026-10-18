interface KpiCardProps {
  label: string;
  value: string;
  sublabel?: string;
  accent?: "primary" | "accent" | "danger" | "success";
  icon?: string;
}

const ACCENTS = {
  primary: {
    iconBg: "rgba(8, 127, 140, 0.10)",
    iconColor: "var(--color-primary)",
    bar: "var(--color-primary)",
  },
  accent: {
    iconBg: "rgba(217, 154, 66, 0.14)",
    iconColor: "#b7791f",
    bar: "#d99a42",
  },
  danger: {
    iconBg: "rgba(220, 70, 70, 0.10)",
    iconColor: "#c53d48",
    bar: "#d94b55",
  },
  success: {
    iconBg: "rgba(22, 163, 106, 0.10)",
    iconColor: "#16865c",
    bar: "#16a36a",
  },
};

export function KpiCard({
  label,
  value,
  sublabel,
  accent = "primary",
  icon = "◈",
}: KpiCardProps) {
  const colors = ACCENTS[accent];

  return (
    <article className="group relative overflow-hidden rounded-2xl border border-border bg-surface p-5 shadow-sm transition-all duration-200 hover:-translate-y-0.5 hover:shadow-md">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="text-xs font-semibold uppercase tracking-wider text-ink-muted">
            {label}
          </p>
          <p className="tabular-figures mt-3 text-3xl font-semibold tracking-tight text-ink">
            {value}
          </p>
        </div>

        <div
          className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl text-xl"
          style={{ background: colors.iconBg, color: colors.iconColor }}
          aria-hidden="true"
        >
          {icon}
        </div>
      </div>

      {sublabel && (
        <p className="mt-3 text-xs leading-5 text-ink-muted">{sublabel}</p>
      )}

      <div
        className="absolute bottom-0 left-0 h-[3px] w-12 rounded-r-full transition-all duration-200 group-hover:w-20"
        style={{ background: colors.bar }}
      />
    </article>
  );
}
