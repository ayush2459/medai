interface KpiCardProps {
  label: string;
  value: string;
  sublabel?: string;
  accent?: "primary" | "accent" | "danger" | "success";
}

const ACCENT_BORDER: Record<string, string> = {
  primary: "border-l-primary",
  accent: "border-l-accent",
  danger: "border-l-danger",
  success: "border-l-success",
};

export function KpiCard({ label, value, sublabel, accent = "primary" }: KpiCardProps) {
  return (
    <div
      className={`rounded-xl border border-border border-l-4 bg-surface p-4 shadow-sm ${ACCENT_BORDER[accent]}`}
    >
      <div className="text-xs font-medium uppercase tracking-wide text-ink-muted">{label}</div>
      <div className="tabular-figures mt-1 text-2xl font-semibold text-ink">{value}</div>
      {sublabel && <div className="mt-1 text-xs text-ink-muted">{sublabel}</div>}
    </div>
  );
}
