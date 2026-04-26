"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { ConfirmModal } from "@/components/ui/ConfirmModal";
import { showToast } from "@/lib/toast";

const ALL_STATUSES = [
  "draft",
  "confirmed",
  "in_production",
  "completed",
  "shipped",
  "cancelled",
] as const;

const STATUS_LABELS: Record<string, string> = {
  draft: "Սևագիր",
  confirmed: "Հաստատված",
  in_production: "Արտադրության մեջ",
  completed: "Ավարտված",
  shipped: "Shipped",
  cancelled: "Չեղարկված",
};

const TRANSITIONS: Record<string, string[]> = {
  draft: ["confirmed", "cancelled"],
  confirmed: ["in_production", "cancelled"],
  in_production: ["completed", "cancelled"],
  completed: [],
  shipped: [],
  cancelled: [],
};

export function OrderRowActions({
  orderId,
  currentStatus,
}: {
  orderId: number;
  currentStatus: string;
}) {
  const router = useRouter();
  const [statusBusy, setStatusBusy] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [deleteBusy, setDeleteBusy] = useState(false);

  const allowedNext = TRANSITIONS[currentStatus] || [];

  const handleStatusChange = async (newStatus: string) => {
    if (!newStatus || newStatus === currentStatus) return;
    setStatusBusy(true);
    try {
      const res = await fetch(`/api/v1/orders/${orderId}/status`, {
        method: "PATCH",
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
      setStatusBusy(false);
    }
  };

  const handleDelete = async () => {
    setDeleteBusy(true);
    try {
      const res = await fetch(`/api/v1/orders/${orderId}`, {
        method: "DELETE",
        credentials: "include",
      });
      if (!res.ok && res.status !== 204) {
        const data = await res.json().catch(() => ({}));
        showToast(data.detail || "Չհաջողվեց ջնջել", "error");
        return;
      }
      showToast(`Պատվեր #${orderId} ջնջվեց`, "success");
      setConfirmDelete(false);
      router.refresh();
    } catch {
      showToast("Կապի սխալ", "error");
    } finally {
      setDeleteBusy(false);
    }
  };

  return (
    <div className="flex items-center justify-end gap-3 whitespace-nowrap">
      <select
        value={currentStatus}
        disabled={statusBusy || allowedNext.length === 0}
        onChange={(e) => handleStatusChange(e.target.value)}
        className="text-xs rounded border border-gray-300 px-2 py-1 bg-white focus:border-brand-500 focus:ring-1 focus:ring-brand-500 disabled:opacity-60 disabled:cursor-not-allowed"
        title={allowedNext.length === 0 ? "Այս կարգավիճակից փոփոխություն անհնար է" : "Փոխել կարգավիճակը"}
      >
        {/* current is always selectable; only valid next states are enabled */}
        <option value={currentStatus}>{STATUS_LABELS[currentStatus] || currentStatus}</option>
        {ALL_STATUSES.filter((s) => s !== currentStatus).map((s) => (
          <option key={s} value={s} disabled={!allowedNext.includes(s)}>
            → {STATUS_LABELS[s] || s}
          </option>
        ))}
      </select>

      <Link
        href={`/dashboard/orders/${orderId}/edit`}
        className="text-brand-700 hover:underline text-sm"
      >
        Խմբագրել
      </Link>

      <Link
        href={`/dashboard/orders/${orderId}`}
        className="text-brand-700 hover:underline text-sm"
      >
        Դիտել
      </Link>

      <button
        type="button"
        onClick={() => setConfirmDelete(true)}
        className="text-red-600 hover:text-red-800 text-sm"
      >
        Ջնջել
      </button>

      <ConfirmModal
        open={confirmDelete}
        onClose={() => setConfirmDelete(false)}
        onConfirm={handleDelete}
        title="Ջնջել պատվերը"
        message={`Համոզվա՞ծ եք, որ ցանկանում եք ջնջել պատվեր #${orderId}: Այս գործողությունը անդարձելի է:`}
        confirmLabel="Ջնջել"
        loading={deleteBusy}
      />
    </div>
  );
}
