import React from "react";

export type SignalChipTone =
  | "gold"
  | "purple"
  | "cyan"
  | "emerald"
  | "amber"
  | "red"
  | "slate"
  | "ops";

interface SignalChipProps {
  children: React.ReactNode;
  tone?: SignalChipTone;
  className?: string;
}

const toneStyles: Record<SignalChipTone, string> = {
  gold: "border-amber-400/30 bg-amber-500/10 text-amber-200",
  purple: "border-violet-400/30 bg-violet-500/10 text-violet-200",
  cyan: "border-cyan-400/30 bg-cyan-500/10 text-cyan-200",
  emerald: "border-emerald-400/30 bg-emerald-500/10 text-emerald-200",
  amber: "border-orange-400/30 bg-orange-500/10 text-orange-200",
  red: "border-red-400/30 bg-red-500/10 text-red-200",
  slate: "border-white/10 bg-white/[0.04] text-stone-300",
  ops: "border-sky-400/25 bg-sky-400/10 text-sky-100",
};

export default function SignalChip({
  children,
  tone = "slate",
  className = "",
}: SignalChipProps) {
  return (
    <span
      className={`inline-flex items-center rounded-full border px-3 py-1 text-[10px] font-mono uppercase tracking-[0.24em] ${toneStyles[tone]} ${className}`}
    >
      {children}
    </span>
  );
}