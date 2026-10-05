import React from "react";

interface ScoreBadgeProps {
  score: number;
  size?: "sm" | "md" | "lg";
}

export function ScoreBadge({ score, size = "md" }: ScoreBadgeProps) {
  const percentage = Math.round(score * 100);

  let colorClasses = "bg-emerald-50 text-emerald-700 border-emerald-200";
  let label = "High";

  if (score < 0.6) {
    colorClasses = "bg-slate-100 text-slate-700 border-slate-200";
    label = "Low";
  } else if (score < 0.8) {
    colorClasses = "bg-amber-50 text-amber-700 border-amber-200";
    label = "Med";
  }

  const sizeClasses = {
    sm: "px-2 py-0.5 text-xs font-semibold",
    md: "px-2.5 py-1 text-xs font-bold",
    lg: "px-3.5 py-1.5 text-sm font-extrabold",
  }[size];

  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full border ${colorClasses} ${sizeClasses}`}
      title={`Priority Score: ${score.toFixed(2)} (${label} Priority)`}
    >
      <span className="w-1.5 h-1.5 rounded-full bg-current"></span>
      <span>{percentage}%</span>
      <span className="opacity-70 text-[10px] font-normal uppercase tracking-wider">{label}</span>
    </span>
  );
}
