"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { showToast } from "@/lib/toast";

const STATUS_OPTIONS = ["pending", "in_progress", "completed"] as const;

const STATUS_LABELS: Record<string, string> = {
  pending: "Սպասման մեջ",
  in_progress: "Ընթացքում",
  completed: "Ավարտված",
};

const TRANSITIONS: Record<string, string[]> = {
  pending: ["in_progress"],
  in_progress: ["completed"],
  completed: [],
  skipped: [],
};

export function StageStatusChange({
  stageId,
  currentStatus,
}: {
  stageId: number;
  currentStatus: string;
}) {
  const router = useRouter();
  const [busy, setBusy] = useState(false);

  const allowedNext = TRANSITIONS[currentStatus] || [];
  const isTerminal = allowedNext.length === 0;

  const handleChange = async (newStatus: string) => {
    if (!newStatus || newStatus === currentStatus) return;
    setBusy(true);
    try {
      const res = await fetch(`/api/v1/production/${stageId}/stage-status`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({ status: newStatus }),
      });
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        showToast(data.detail || "Չհաջողվեց փոխել կարգավիճակը", "error");
        return;
      }
      showToast(`Կարգավիճակը փոխվել է՝ ${STATUS_LABELS[newStatus] || newStatus}`, "success");
      router.refresh();
    } catch {
      showToast("Կապի սխալ", "error");
    } finally {
      setBusy(false);
    }
  };

  return (
    <select
      value={currentStatus}
      disabled={busy || isTerminal}
      onChange={(e) => handleChange(e.target.value)}
      className="text-xs rounded border border-gray-300 px-2 py-1 bg-white focus:border-brand-500 focus:ring-1 focus:ring-brand-500 disabled:opacity-60 disabled:cursor-not-allowed"
      title={isTerminal ? "Այս կարգավիճակից փոփոխություն անհնար է" : "Փոխել կարգավիճակը"}
    >
      <option value={currentStatus}>
        {STATUS_LABELS[currentStatus] || currentStatus}
      </option>
      {STATUS_OPTIONS.filter((s) => s !== currentStatus).map((s) => (
        <option key={s} value={s} disabled={!allowedNext.includes(s)}>
          → {STATUS_LABELS[s]}
        </option>
      ))}
    </select>
  );
}
