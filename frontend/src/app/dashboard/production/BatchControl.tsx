"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { showToast } from "@/lib/toast";
import { clientFetch } from "@/lib/api.client";

const STAGE_OPTIONS = [
  "cutting",
  "processing",
  "quality_control",
  "packaging",
  "warehousing",
  "ready_for_shipment",
] as const;

const STAGE_LABELS: Record<string, string> = {
  cutting: "Կտրում",
  processing: "Մշակում",
  quality_control: "Որակի վերահսկում",
  packaging: "Փաթեթավորում",
  warehousing: "Պահեստավորում",
  ready_for_shipment: "Պատրաստ է առաքման",
};

const STATUS_OPTIONS = ["pending", "in_progress"] as const;

const STATUS_LABELS: Record<string, string> = {
  pending: "Սպասման մեջ",
  in_progress: "Ընթացքի մեջ",
  completed: "Ավարտված",
};

export function BatchControl({
  batchId,
  currentStage,
  currentStatus,
  stockAdded,
}: {
  batchId: number;
  currentStage: string;
  currentStatus: string;
  stockAdded: boolean;
}) {
  const router = useRouter();
  const [busy, setBusy] = useState(false);

  const isTerminal = currentStatus === "completed" || stockAdded;

  const patch = async (body: { current_stage?: string; stage_status?: string }) => {
    setBusy(true);
    try {
      const res = await clientFetch(`/production/batches/${batchId}`, {
        method: "PATCH",
        body: JSON.stringify(body),
      });
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        showToast(data.detail || "Չհաջողվեց փոխել", "error");
        return;
      }
      router.refresh();
    } catch {
      showToast("Կապի սխալ", "error");
    } finally {
      setBusy(false);
    }
  };

  const handleComplete = async () => {
    setBusy(true);
    try {
      const res = await clientFetch(`/production/batches/${batchId}/complete`, {
        method: "PATCH",
      });
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        showToast(data.detail || "Չհաջողվեց ավարտել", "error");
        return;
      }
      showToast("Արտադրությունն ավարտված է", "success");
      router.refresh();
    } catch {
      showToast("Կապի սխալ", "error");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="flex items-center gap-2 whitespace-nowrap">
      <select
        value={currentStage}
        disabled={busy || isTerminal}
        onChange={(e) => patch({ current_stage: e.target.value })}
        className="text-xs rounded border border-gray-300 px-2 py-1 bg-white focus:border-brand-500 focus:ring-1 focus:ring-brand-500 disabled:opacity-60 disabled:cursor-not-allowed"
        title={isTerminal ? "Ավարտված" : "Փոխել փուլը"}
      >
        {STAGE_OPTIONS.map((s) => (
          <option key={s} value={s}>
            {STAGE_LABELS[s]}
          </option>
        ))}
      </select>

      <select
        value={currentStatus}
        disabled={busy || isTerminal}
        onChange={(e) => patch({ stage_status: e.target.value })}
        className="text-xs rounded border border-gray-300 px-2 py-1 bg-white focus:border-brand-500 focus:ring-1 focus:ring-brand-500 disabled:opacity-60 disabled:cursor-not-allowed"
        title={isTerminal ? "Ավարտված" : "Փոխել կարգավիճակը"}
      >
        {isTerminal ? (
          <option value="completed">{STATUS_LABELS.completed}</option>
        ) : (
          STATUS_OPTIONS.map((s) => (
            <option key={s} value={s}>
              {STATUS_LABELS[s]}
            </option>
          ))
        )}
      </select>

      {!isTerminal && (
        <button
          type="button"
          onClick={handleComplete}
          disabled={busy}
          className="text-xs px-2 py-1 rounded bg-green-600 text-white hover:bg-green-700 disabled:opacity-60 disabled:cursor-not-allowed"
        >
          Ավարտել
        </button>
      )}
    </div>
  );
}
