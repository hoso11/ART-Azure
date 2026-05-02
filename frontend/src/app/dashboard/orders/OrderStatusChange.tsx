"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { StatusBadge } from "@/components/ui/StatusBadge";

const ALLOWED_STATUSES = ["draft", "confirmed", "completed"] as const;

// Active labels + read-only historical labels so the confirmation banner
// renders Armenian text when an order is rescued from a deprecated status.
const STATUS_LABELS: Record<string, string> = {
  draft: "Սևագիր",
  confirmed: "Հաստատված",
  completed: "Ավարտված",
  in_production: "Արտադրության մեջ",
  shipped: "Առաքված",
  cancelled: "Չեղարկված",
};

export function OrderStatusChange({
  orderId,
  currentStatus,
  blockComplete = false,
  blockCompleteReason,
}: {
  orderId: number;
  currentStatus: string;
  /** True when stock is insufficient — prevents the `completed` button from firing.
   * Backend remains the source of truth; this is a UX hint only. */
  blockComplete?: boolean;
  blockCompleteReason?: string;
}) {
  const router = useRouter();
  const [confirming, setConfirming] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  // Source can be any value (including deprecated). Targets are the three
  // allowed statuses minus the current one.
  const allowed = ALLOWED_STATUSES.filter((s) => s !== currentStatus);
  if (allowed.length === 0) return null;

  const handleChange = async (newStatus: string) => {
    setLoading(true);
    setError("");
    try {
      const res = await fetch(`/api/v1/orders/${orderId}/status`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({ status: newStatus }),
      });
      if (!res.ok) {
        const data = await res.json();
        setError(data.detail || "Failed to update status");
        setConfirming(null);
        return;
      }
      setConfirming(null);
      router.refresh();
    } catch {
      setError("Connection error");
      setConfirming(null);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="mt-3">
      {error && (
        <p className="text-xs text-red-600 mb-2 whitespace-pre-wrap">{error}</p>
      )}

      {confirming ? (
        <div className="bg-amber-50 border border-amber-200 rounded-lg p-3">
          <p className="text-sm text-amber-800 mb-2">
            Change status from <strong>{STATUS_LABELS[currentStatus]}</strong> to{" "}
            <strong>{STATUS_LABELS[confirming]}</strong>? This cannot be undone.
          </p>
          <div className="flex gap-2">
            <button
              onClick={() => handleChange(confirming)}
              disabled={loading}
              className="px-3 py-1 text-xs font-medium bg-brand-800 text-white rounded hover:bg-brand-900 disabled:opacity-50"
            >
              {loading ? "Թարմացնում..." : "Հաստատել"}
            </button>
            <button
              onClick={() => { setConfirming(null); setError(""); }}
              disabled={loading}
              className="px-3 py-1 text-xs font-medium bg-gray-100 text-gray-700 rounded hover:bg-gray-200"
            >
              Չեղարկել
            </button>
          </div>
        </div>
      ) : (
        <div className="flex flex-wrap gap-2">
          {allowed.map((s) => {
            const isComplete = s === "completed";
            const disabled = isComplete && blockComplete;
            return (
              <button
                key={s}
                onClick={() => !disabled && setConfirming(s)}
                disabled={disabled}
                title={disabled ? blockCompleteReason : undefined}
                className={`px-3 py-1 text-xs font-medium rounded border transition-colors border-brand-200 text-brand-700 hover:bg-brand-50 disabled:opacity-50 disabled:cursor-not-allowed disabled:hover:bg-transparent`}
              >
                {STATUS_LABELS[s]}
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}
