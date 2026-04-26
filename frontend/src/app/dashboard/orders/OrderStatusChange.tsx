"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { StatusBadge } from "@/components/ui/StatusBadge";

const TRANSITIONS: Record<string, string[]> = {
  draft: ["confirmed", "cancelled"],
  confirmed: ["in_production", "cancelled"],
  in_production: ["completed", "cancelled"],
  completed: [],
  shipped: [],
  cancelled: [],
};

const STATUS_LABELS: Record<string, string> = {
  draft: "Սևագիր",
  confirmed: "Հաստատված",
  in_production: "Արտադրության մեջ",
  completed: "Ավարտված",
  shipped: "Shipped",
  cancelled: "Չեղարկված",
};

export function OrderStatusChange({ orderId, currentStatus }: { orderId: number; currentStatus: string }) {
  const router = useRouter();
  const [confirming, setConfirming] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const allowed = TRANSITIONS[currentStatus] || [];
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
        <p className="text-xs text-red-600 mb-2">{error}</p>
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
          {allowed.map((s) => (
            <button
              key={s}
              onClick={() => setConfirming(s)}
              className={`px-3 py-1 text-xs font-medium rounded border transition-colors ${
                s === "cancelled"
                  ? "border-red-200 text-red-700 hover:bg-red-50"
                  : "border-brand-200 text-brand-700 hover:bg-brand-50"
              }`}
            >
              {STATUS_LABELS[s]}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
