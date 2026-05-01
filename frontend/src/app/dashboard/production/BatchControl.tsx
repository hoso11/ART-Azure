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
  quantityToProduce,
}: {
  batchId: number;
  currentStage: string;
  currentStatus: string;
  stockAdded: boolean;
  quantityToProduce: number;
}) {
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  const [good, setGood] = useState<string>(String(quantityToProduce));
  const [damaged, setDamaged] = useState<string>("0");
  const [reason, setReason] = useState<string>("");

  const isTerminal = currentStatus === "completed" || stockAdded;

  const goodNum = Number.parseInt(good, 10);
  const damagedNum = Number.parseInt(damaged, 10);
  const goodValid = Number.isFinite(goodNum) && goodNum >= 0;
  const damagedValid = Number.isFinite(damagedNum) && damagedNum >= 0;
  const sumValid = goodValid && damagedValid && goodNum + damagedNum === quantityToProduce;

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
    if (!sumValid) {
      showToast(
        `Լավ + Խոտան պետք է հավասար լինի ${quantityToProduce}-ի`,
        "error",
      );
      return;
    }
    setBusy(true);
    try {
      const res = await clientFetch(`/production/batches/${batchId}/complete`, {
        method: "PATCH",
        body: JSON.stringify({
          good_quantity: goodNum,
          damaged_quantity: damagedNum,
          defect_reason: damagedNum > 0 ? (reason.trim() || null) : null,
        }),
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

  const setAllGood = () => {
    setGood(String(quantityToProduce));
    setDamaged("0");
  };
  const setAllDamaged = () => {
    setGood("0");
    setDamaged(String(quantityToProduce));
  };

  return (
    <div className="flex flex-col items-end gap-2 whitespace-nowrap">
      <div className="flex items-center gap-2">
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
      </div>

      {!isTerminal && (
        <div className="flex items-center gap-2">
          <label className="text-xs text-gray-600">Լավ</label>
          <input
            type="number"
            min={0}
            max={quantityToProduce}
            value={good}
            onChange={(e) => setGood(e.target.value)}
            disabled={busy}
            className="w-14 text-xs rounded border border-gray-300 px-2 py-1 bg-white focus:border-brand-500 focus:ring-1 focus:ring-brand-500 disabled:opacity-60"
          />
          <label className="text-xs text-gray-600">Խոտան</label>
          <input
            type="number"
            min={0}
            max={quantityToProduce}
            value={damaged}
            onChange={(e) => setDamaged(e.target.value)}
            disabled={busy}
            className="w-14 text-xs rounded border border-gray-300 px-2 py-1 bg-white focus:border-brand-500 focus:ring-1 focus:ring-brand-500 disabled:opacity-60"
          />
          <button
            type="button"
            onClick={setAllGood}
            disabled={busy}
            className="text-xs text-gray-500 hover:text-gray-800 underline disabled:opacity-60"
            title={`Բոլորը լավ (${quantityToProduce})`}
          >
            Բոլորը լավ
          </button>
          <button
            type="button"
            onClick={setAllDamaged}
            disabled={busy}
            className="text-xs text-gray-500 hover:text-gray-800 underline disabled:opacity-60"
            title={`Բոլորը Խոտան (${quantityToProduce})`}
          >
            Բոլորը Խոտան
          </button>
        </div>
      )}

      {!isTerminal && damagedNum > 0 && (
        <input
          type="text"
          value={reason}
          onChange={(e) => setReason(e.target.value)}
          placeholder="Խոտանի պատճառ (ոչ պարտադիր)"
          disabled={busy}
          className="w-full text-xs rounded border border-gray-300 px-2 py-1 bg-white focus:border-brand-500 focus:ring-1 focus:ring-brand-500 disabled:opacity-60"
        />
      )}

      {!isTerminal && (
        <div className="flex items-center gap-2">
          {!sumValid && (
            <span className="text-xs text-red-600">
              Գումարը պետք է լինի {quantityToProduce}
            </span>
          )}
          <button
            type="button"
            onClick={handleComplete}
            disabled={busy || !sumValid}
            className="text-xs px-3 py-1 rounded bg-green-600 text-white hover:bg-green-700 disabled:opacity-60 disabled:cursor-not-allowed"
          >
            Ավարտել
          </button>
        </div>
      )}
    </div>
  );
}
