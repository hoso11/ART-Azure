"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Card, CardContent, CardHeader } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { FormField, Input, Select, Textarea } from "@/components/ui/FormField";
import { Order } from "@/types";
import { showToast } from "@/lib/toast";

const ALL_STATUSES = ["draft", "confirmed", "in_production", "completed", "shipped", "cancelled"];

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

  const allowedNext = TRANSITIONS[order.status] || [];
  const statusOptions = [order.status, ...allowedNext];

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
              <Select value={status} onChange={(e) => setStatus(e.target.value)} required>
                {ALL_STATUSES.map((s) => (
                  <option key={s} value={s} disabled={!statusOptions.includes(s)}>
                    {STATUS_LABELS[s] || s}
                    {s === order.status ? " (ընթացիկ)" : ""}
                  </option>
                ))}
              </Select>
              {allowedNext.length === 0 && (
                <p className="text-xs text-gray-500 mt-1">
                  Այս կարգավիճակից փոփոխություն հնարավոր չէ
                </p>
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
