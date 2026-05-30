"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { ConfirmModal } from "@/components/ui/ConfirmModal";
import { showToast } from "@/lib/toast";
import { ForceDeleteOrderButton } from "./ForceDeleteOrderButton";

// Three active statuses. Admin moves freely between any two of these.
// Historical rows stuck at a deprecated status (in_production / shipped /
// cancelled) render their badge via StatusBadge but the row dropdown only
// offers the allowed targets, which lets admin rescue them into the active
// set.
const ALL_STATUSES = ["draft", "confirmed", "completed"] as const;

// Active labels + read-only historical labels so a row stuck at a deprecated
// status displays Armenian text in the dropdown's "current" option instead of
// the raw enum value.
const STATUS_LABELS: Record<string, string> = {
  draft: "Սևագիր",
  confirmed: "Հաստատված",
  completed: "Ավարտված",
  in_production: "Արտադրության մեջ",
  shipped: "Առաքված",
  cancelled: "Չեղարկված",
};

type RowItem = {
  quantity: number;
  product_variant: { stock_quantity: number } | null;
};

export function OrderRowActions({
  orderId,
  currentStatus,
  items,
  stockDeducted,
}: {
  orderId: number;
  currentStatus: string;
  items: RowItem[];
  stockDeducted: boolean;
}) {
  const router = useRouter();
  const [statusBusy, setStatusBusy] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [deleteBusy, setDeleteBusy] = useState(false);

  // All allowed targets that aren't the current status. Source can be any
  // value (including a deprecated one); only the target is gated.
  const allowedNext = ALL_STATUSES.filter((s) => s !== currentStatus);

  // Per-row stock check — backend remains source of truth, but we hide the
  // `Ավարտված` option in the dropdown when stock is short and not yet
  // deducted, so admin can't even pick it. If stock_deducted is already true,
  // re-completing is a no-op and is allowed.
  const anyShortage = items.some(
    (i) => i.quantity > (i.product_variant?.stock_quantity ?? 0),
  );
  const blockComplete = anyShortage && !stockDeducted;
  const blockReason = "Անբավարար մնացորդ — ավարտել հնարավոր չէ";

  const handleStatusChange = async (newStatus: string) => {
    if (!newStatus || newStatus === currentStatus) return;
    if (newStatus === "completed" && blockComplete) {
      showToast(blockReason, "error");
      return;
    }
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
        disabled={statusBusy}
        onChange={(e) => handleStatusChange(e.target.value)}
        className="text-xs rounded border border-gray-300 px-2 py-1 bg-white focus:border-brand-500 focus:ring-1 focus:ring-brand-500 disabled:opacity-60 disabled:cursor-not-allowed"
        title={blockComplete ? blockReason : "Փոխել կարգավիճակը"}
      >
        <option value={currentStatus}>{STATUS_LABELS[currentStatus] || currentStatus}</option>
        {allowedNext.map((s) => {
          const isComplete = s === "completed";
          const disabled = isComplete && blockComplete;
          return (
            <option key={s} value={s} disabled={disabled}>
              → {STATUS_LABELS[s]}{disabled ? " ✕" : ""}
            </option>
          );
        })}
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

      <ForceDeleteOrderButton orderId={orderId} />

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
