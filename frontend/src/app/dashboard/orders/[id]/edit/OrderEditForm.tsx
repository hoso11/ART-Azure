"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Card, CardContent, CardHeader } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { FormField, Input, Select, Textarea } from "@/components/ui/FormField";
import { Order } from "@/types";
import { showToast } from "@/lib/toast";

// Three active statuses. Source can be any value (including a deprecated
// historical status); targets are restricted to the three active ones.
const ALL_STATUSES = ["draft", "confirmed", "completed"];

// Active labels + read-only historical labels so a row stuck at a deprecated
// status renders Armenian text in the "current" option.
const STATUS_LABELS: Record<string, string> = {
  draft: "Սևագիր",
  confirmed: "Հաստատված",
  completed: "Ավարտված",
  in_production: "Արտադրության մեջ",
  shipped: "Առաքված",
  cancelled: "Չեղարկված",
};

function toDateInputValue(iso: string | null): string {
  if (!iso) return "";
  const d = new Date(iso);
  if (isNaN(d.getTime())) return "";
  const yyyy = d.getFullYear();
  const mm = String(d.getMonth() + 1).padStart(2, "0");
  const dd = String(d.getDate()).padStart(2, "0");
  return `${yyyy}-${mm}-${dd}`;
}

export function OrderEditForm({ order }: { order: Order }) {
  const router = useRouter();
  const [status, setStatus] = useState(order.status);
  const [priority, setPriority] = useState(order.priority);
  const [deadline, setDeadline] = useState(toDateInputValue(order.deadline));
  const [notes, setNotes] = useState(order.notes || "");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  // Allowed targets = the three active statuses minus the current status.
  // If the current status is one of the deprecated values, the dropdown lets
  // admin rescue the order into any of the three.
  const allowedNext = ALL_STATUSES.filter((s) => s !== order.status);
  const statusOptions = [order.status, ...allowedNext];

  // Per-order stock check — disables the `completed` option when sellable
  // stock is short and stock_deducted is still false. Backend remains the
  // source of truth (422 insufficient_stock); this is a UX gate.
  const anyShortage = order.items.some(
    (i) => i.quantity > (i.product_variant?.stock_quantity ?? 0),
  );
  const blockComplete = anyShortage && !order.stock_deducted;
  const blockReason = "Անբավարար մնացորդ — ավարտել հնարավոր չէ";

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");

    // Client-side validation: priority must be a known value; deadline (if given) must parse.
    if (!["low", "normal", "high", "urgent"].includes(priority)) {
      setError("Անվավեր առաջնահերթություն");
      return;
    }
    if (deadline && isNaN(new Date(deadline).getTime())) {
      setError("Անվավեր վերջնաժամկետ");
      return;
    }
    // Block completed when stock is short and not yet deducted.
    if (status === "completed" && status !== order.status && blockComplete) {
      setError(blockReason);
      showToast(blockReason, "error");
      return;
    }

    setLoading(true);
    try {
      // Only include status if it actually changed — backend rejects no-op transitions.
      const body: Record<string, unknown> = {
        priority,
        deadline: deadline ? new Date(deadline).toISOString() : null,
        notes: notes || null,
      };
      if (status !== order.status) {
        body.status = status;
      }

      const res = await fetch(`/api/v1/orders/${order.id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify(body),
      });

      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        const msg = data.detail || "Չհաջողվեց պահպանել փոփոխությունները";
        setError(msg);
        showToast(msg, "error");
        return;
      }

      showToast(`Պատվեր #${order.id} թարմացվեց`, "success");
      router.push(`/dashboard/orders/${order.id}`);
      router.refresh();
    } catch {
      setError("Կապի սխալ");
      showToast("Կապի սխալ", "error");
    } finally {
      setLoading(false);
    }
  };

  return (
    <form onSubmit={handleSubmit}>
      {error && (
        <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700">
          {error}
        </div>
      )}

      <Card className="mb-6">
        <CardHeader>
          <h3 className="font-semibold">Պատվերի մանրամասներ</h3>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-2 gap-4">
            <FormField label="Կարգավիճակ" required>
              <Select
                value={status}
                onChange={(e) => setStatus(e.target.value)}
                required
                title={blockComplete ? blockReason : undefined}
              >
                {/* Render current + allowed targets (deduplicated). When the
                    order is on a deprecated status the current option still
                    shows up first so admin can see what they're rescuing from.
                    The `completed` option is disabled when stock is short
                    and not yet deducted. */}
                {Array.from(new Set(statusOptions)).map((s) => {
                  const isComplete = s === "completed";
                  const isCurrent = s === order.status;
                  const disabled = isComplete && !isCurrent && blockComplete;
                  return (
                    <option key={s} value={s} disabled={disabled}>
                      {STATUS_LABELS[s] || s}
                      {isCurrent ? " (ընթացիկ)" : ""}
                      {disabled ? " ✕" : ""}
                    </option>
                  );
                })}
              </Select>
              {blockComplete && (
                <p className="text-xs text-red-600 mt-1">{blockReason}</p>
              )}
            </FormField>

            <FormField label="Առաջնահերթություն" required>
              <Select value={priority} onChange={(e) => setPriority(e.target.value)} required>
                <option value="low">Ցածր</option>
                <option value="normal">Սովորական</option>
                <option value="high">Բարձր</option>
                <option value="urgent">Շտապ</option>
              </Select>
            </FormField>

            <FormField label="Վերջնաժամկետ">
              <Input type="date" value={deadline} onChange={(e) => setDeadline(e.target.value)} />
            </FormField>
          </div>

          <FormField label="Նշումներ">
            <Textarea
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              placeholder="Պատվերի նշումներ..."
            />
          </FormField>
        </CardContent>
      </Card>

      <div className="flex gap-3">
        <Button type="submit" loading={loading}>Պահպանել</Button>
        <Button type="button" variant="secondary" onClick={() => router.back()}>Չեղարկել</Button>
      </div>
    </form>
  );
}
