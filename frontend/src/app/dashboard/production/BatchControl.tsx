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
  goodSoFar,
  damagedSoFar,
}: {
  batchId: number;
  currentStage: string;
  currentStatus: string;
  stockAdded: boolean;
  quantityToProduce: number;
  goodSoFar: number;
  damagedSoFar: number;
}) {
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  // Delta inputs — admin types how much to add NOW, not totals.
  const [good, setGood] = useState<string>("0");
  const [damaged, setDamaged] = useState<string>("0");
  const [reason, setReason] = useState<string>("");

  const isTerminal = currentStatus === "completed" || stockAdded;
  const remaining = Math.max(0, quantityToProduce - goodSoFar - damagedSoFar);

  const goodNum = Number.parseInt(good, 10);
  const damagedNum = Number.parseInt(damaged, 10);
  const goodValid = Number.isFinite(goodNum) && goodNum >= 0;
  const damagedValid = Number.isFinite(damagedNum) && damagedNum >= 0;
  const deltaTotal = (goodValid ? goodNum : 0) + (damagedValid ? damagedNum : 0);
  const deltaPositive = deltaTotal > 0;
  const deltaWithinRemaining = deltaTotal <= remaining;
  const deltaValid = goodValid && damagedValid && deltaPositive && deltaWithinRemaining;

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

  const handleApply = async () => {
    if (!deltaValid) {
      if (!deltaPositive) {
        showToast("Մուտքագրեք գոնե մեկ քանակ", "error");
      } else if (!deltaWithinRemaining) {
        showToast(
          `Մուտքագրված քանակը (${deltaTotal}) գերազանցում է մնացածը (${remaining})`,
          "error",
        );
      }
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
        showToast(data.detail || "Չհաջողվեց պահպանել", "error");
        return;
      }
      const body = await res.json().catch(() => ({}));
      if (body && body.stock_added) {
        showToast("Արտադրությունն ավարտված է", "success");
      } else {
        showToast(
          `Ավելացված է ${goodNum} լավ + ${damagedNum} Խոտան`,
          "success",
        );
      }
      // Reset inputs for the next partial save.
      setGood("0");
      setDamaged("0");
      setReason("");
      router.refresh();
    } catch {
      showToast("Կապի սխալ", "error");
    } finally {
      setBusy(false);
    }
  };

  const fillRemainingGood = () => {
    setGood(String(remaining));
    setDamaged("0");
  };
  const fillRemainingDamaged = () => {
    setGood("0");
    setDamaged(String(remaining));
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
        <div className="text-xs text-gray-600 whitespace-nowrap">
          Մնացած՝ <span className="font-semibold text-gray-900">{remaining}</span>
          {" / "}
          {quantityToProduce}
          {" "}
          <span className="text-gray-500">
            (լավ՝ {goodSoFar}, Խոտան՝ {damagedSoFar})
          </span>
        </div>
      )}

      {!isTerminal && (
        <div className="flex items-center gap-2">
          <label className="text-xs text-gray-600" title="Ավելացնել հիմա">Լավ</label>
          <input
            type="number"
            min={0}
            max={remaining}
            value={good}
            onChange={(e) => setGood(e.target.value)}
            disabled={busy}
            className="w-14 text-xs rounded border border-gray-300 px-2 py-1 bg-white focus:border-brand-500 focus:ring-1 focus:ring-brand-500 disabled:opacity-60"
          />
          <label className="text-xs text-gray-600" title="Ավելացնել հիմա">Խոտան</label>
          <input
            type="number"
            min={0}
            max={remaining}
            value={damaged}
            onChange={(e) => setDamaged(e.target.value)}
            disabled={busy}
            className="w-14 text-xs rounded border border-gray-300 px-2 py-1 bg-white focus:border-brand-500 focus:ring-1 focus:ring-brand-500 disabled:opacity-60"
          />
          <button
            type="button"
            onClick={fillRemainingGood}
            disabled={busy || remaining === 0}
            className="text-xs text-gray-500 hover:text-gray-800 underline disabled:opacity-60 disabled:no-underline"
            title={`Բոլոր մնացածը (${remaining}) որպես լավ`}
          >
            Բոլոր մնացածը լավ
          </button>
          <button
            type="button"
            onClick={fillRemainingDamaged}
            disabled={busy || remaining === 0}
            className="text-xs text-gray-500 hover:text-gray-800 underline disabled:opacity-60 disabled:no-underline"
            title={`Բոլոր մնացածը (${remaining}) որպես Խոտան`}
          >
            Բոլոր մնացածը Խոտան
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
          {deltaPositive && !deltaWithinRemaining && (
            <span className="text-xs text-red-600">
              Մուտքագրված քանակը գերազանցում է մնացածը ({remaining})
            </span>
          )}
          <button
            type="button"
            onClick={handleApply}
            disabled={busy || !deltaValid}
            className="text-xs px-3 py-1 rounded bg-green-600 text-white hover:bg-green-700 disabled:opacity-60 disabled:cursor-not-allowed"
            title={
              deltaTotal === remaining && deltaPositive
                ? "Ավարտել մնացածը"
                : "Ավելացնել մաս"
            }
          >
            {deltaTotal === remaining && deltaPositive ? "Ավարտել" : "Ավելացնել"}
          </button>
        </div>
      )}
    </div>
  );
}
