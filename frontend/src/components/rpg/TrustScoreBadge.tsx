import { ShieldCheck } from "lucide-react";

type TrustScoreBadgeProps = {
  score?: number | null;
  size?: "sm" | "md";
};

const SIZE_STYLES = {
  sm: {
    shell: "px-2.5 py-1 text-[10px]",
    icon: 12,
  },
  md: {
    shell: "px-3 py-1.5 text-xs",
    icon: 14,
  },
} as const;

export default function TrustScoreBadge({ score, size = "md" }: TrustScoreBadgeProps) {
  const styles = SIZE_STYLES[size];
  const hasScore = typeof score === "number";
  const normalizedScore = hasScore ? Math.max(0, Math.min(1, score)) : null;
  const percent = normalizedScore === null ? null : Math.round(normalizedScore * 100);

  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full border ${styles.shell} ${
        percent === null
          ? "border-stone-600/50 bg-stone-500/10 text-stone-300"
          : percent >= 85
            ? "border-emerald-500/30 bg-emerald-500/10 text-emerald-200"
            : percent >= 60
              ? "border-sky-500/30 bg-sky-500/10 text-sky-200"
              : "border-amber-500/30 bg-amber-500/10 text-amber-200"
      }`}
    >
      <ShieldCheck size={styles.icon} />
      {percent === null ? "Новый профиль" : `Trust ${percent}`}
    </span>
  );
}