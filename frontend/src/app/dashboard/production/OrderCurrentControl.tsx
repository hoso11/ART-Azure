"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { showToast } from "@/lib/toast";
import { clientFetch } from "@/lib/api.client";

const STAGE_OPTIONS = [
  "cutting",
  "sewing",
  "quality_control",
  "packaging",
  "ready_for_shipment",
] as const;

const STAGE_LABELS: Record<string, string> = {
  cutting: "Կտրում",
  sewing: "Մշակում",
  quality_control: "Որակի վերահսկում",
  packaging: "Փաթեթավորում",
  ready_for_shipment: "Պատրաստ է առաքման",
};

const STATUS_OPTIONS = ["pending", "in_progress", "completed"] as const;

const STATUS_LABELS: Record<string, string> = {
  pending: "Սպասման մեջ",
  in_progress: "Ընթացքում",
  completed: "Ավարտված",
};

export function OrderCurrentControl({
  orderId,
  currentStage,
  currentStatus,
}: {
  orderId: number;
  currentStage: string;
  currentStatus: string;
}) {
  const router = useRouter();
  const [busy, setBusy] = useState(false);

  const patch = async (next: { current_stage: string; current_status: string }) => {
    setBusy(true);
    try {
      const res = await clientFetch(`/production/orders/${orderId}/current`, {
        method: "PATCH",
        body: JSON.stringify(next),
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

  return (
    <div className="flex items-center gap-2 whitespace-nowrap">
      <select
        value={currentStage}
        disabled={busy}
        onChange={(e) =>
          patch({ current_stage: e.target.value, current_status: currentStatus })
        }
        className="text-xs rounded border border-gray-300 px-2 py-1 bg-white focus:border-brand-500 focus:ring-1 focus:ring-brand-500 disabled:opacity-60 disabled:cursor-not-allowed"
        title="Փոխել փուլը"
      >
        {STAGE_OPTIONS.map((s) => (
          <option key={s} value={s}>
            {STAGE_LABELS[s]}
          </option>
        ))}
      </select>

      <select
        value={currentStatus}
        disabled={busy}
        onChange={(e) =>
          patch({ current_stage: currentStage, current_status: e.target.value })
        }
        className="text-xs rounded border border-gray-300 px-2 py-1 bg-white focus:border-brand-500 focus:ring-1 focus:ring-brand-500 disabled:opacity-60 disabled:cursor-not-allowed"
        title="Փոխել կարգավիճակը"
      >
        {STATUS_OPTIONS.map((s) => (
          <option key={s} value={s}>
            {STATUS_LABELS[s]}
          </option>
        ))}
      </select>
    </div>
  );
}
