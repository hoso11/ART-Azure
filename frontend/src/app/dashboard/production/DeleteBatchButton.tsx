"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { showToast } from "@/lib/toast";
import { clientFetch } from "@/lib/api.client";

const ERROR_MESSAGES: Record<string, string> = {
  batch_not_completed:
    "Կարելի է ջնջել միայն ավարտված արտադրությունները:",
  batch_rollback_would_underflow:
    "Հնարավոր չէ ետ վերցնել պաշարը. մի մասը արդեն վաճառվել կամ սպառվել է:",
  batch_has_linked_movements:
    "Այս արտադրությունը ունի կապակցված շարժեր. օգտագործեք սովորական ջնջումը:",
  insufficient_permissions:
    "Չունեք իրավասություն ջնջելու արտադրությունը:",
  not_found: "Արտադրությունը արդեն ջնջվել է:",
};

const FORCE_PHRASE = "FORCE DELETE";

type Phase = "idle" | "confirm" | "legacy_force";

export function DeleteBatchButton({
  batchId,
  good,
  damaged,
}: {
  batchId: number;
  good: number;
  damaged: number;
}) {
  const router = useRouter();
  const [phase, setPhase] = useState<Phase>("idle");
  const [submitting, setSubmitting] = useState(false);
  const [forceInput, setForceInput] = useState("");

  const reset = () => {
    setPhase("idle");
    setForceInput("");
  };

  const handleSafeDelete = async () => {
    setSubmitting(true);
    try {
      const res = await clientFetch(`/production/batches/${batchId}`, {
        method: "DELETE",
      });
      if (res.status === 204) {
        showToast("Արտադրությունը ջնջվեց և պաշարը վերականգնվեց", "success");
        reset();
        router.refresh();
        return;
      }
      const data = await res.json().catch(() => ({}));
      const code = (data?.code as string) || "";
      // Legacy batch — escalate to force-delete confirmation instead of a
      // generic toast. Admin must type FORCE DELETE to proceed.
      if (code === "batch_legacy_no_movement_link") {
        setPhase("legacy_force");
        return;
      }
      const msg =
        ERROR_MESSAGES[code] ||
        (data?.detail as string) ||
        "Չհաջողվեց ջնջել արտադրությունը";
      showToast(msg, "error");
    } finally {
      setSubmitting(false);
    }
  };

  const handleForceDelete = async () => {
    if (forceInput.trim() !== FORCE_PHRASE) return;
    setSubmitting(true);
    try {
      const res = await clientFetch(`/production/batches/${batchId}/force`, {
        method: "DELETE",
      });
      if (res.status === 204) {
        showToast(
          "Արտադրությունը ուժով ջնջվեց: պաշարը չի փոփոխվել:",
          "success",
        );
        reset();
        router.refresh();
        return;
      }
      const data = await res.json().catch(() => ({}));
      const code = (data?.code as string) || "";
      const msg =
        ERROR_MESSAGES[code] ||
        (data?.detail as string) ||
        "Չհաջողվեց ուժով ջնջել արտադրությունը";
      showToast(msg, "error");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <>
      <button
        type="button"
        onClick={() => setPhase("confirm")}
        className="text-red-700 hover:underline text-sm whitespace-nowrap"
      >
        Ջնջել
      </button>

      {phase === "confirm" && (
        <div className="fixed inset-0 bg-black/40 z-50 flex items-center justify-center px-4">
          <div className="bg-white rounded-lg shadow-lg p-6 max-w-md w-full">
            <h3 className="text-lg font-semibold text-gray-900 mb-2">
              Ջնջել արտադրությունը՞
            </h3>
            <p className="text-sm text-gray-700">
              Արտադրությունը կհեռացվի, իսկ պաշարը կվերականգնվի.
            </p>
            <ul className="text-sm text-gray-700 list-disc pl-5 mt-2 space-y-1">
              <li>Հումքը կվերադարձվի պահեստ</li>
              {good > 0 && (
                <li>
                  Վաճառվող պաշարը կնվազեցվի <strong>{good}</strong> միավորով
                </li>
              )}
              {damaged > 0 && (
                <li>
                  Խոտանի պաշարը կնվազեցվի <strong>{damaged}</strong> միավորով
                </li>
              )}
            </ul>
            <p className="text-xs text-gray-500 mt-3">
              Եթե պաշարը արդեն վաճառվել կամ սպառվել է, ջնջումը կարգելափակվի:
            </p>
            <div className="mt-5 flex justify-end gap-2">
              <button
                type="button"
                onClick={reset}
                disabled={submitting}
                className="px-3 py-1.5 text-sm rounded border border-gray-300 text-gray-700 hover:bg-gray-50 disabled:opacity-50"
              >
                Չեղարկել
              </button>
              <button
                type="button"
                onClick={handleSafeDelete}
                disabled={submitting}
                className="px-3 py-1.5 text-sm rounded bg-red-600 text-white hover:bg-red-700 disabled:opacity-50"
              >
                {submitting ? "Ջնջվում է…" : "Ջնջել"}
              </button>
            </div>
          </div>
        </div>
      )}

      {phase === "legacy_force" && (
        <div className="fixed inset-0 bg-black/40 z-50 flex items-center justify-center px-4">
          <div className="bg-white rounded-lg shadow-lg border-2 border-red-600 p-6 max-w-lg w-full">
            <div className="flex items-center gap-2 mb-3">
              <span
                aria-hidden="true"
                className="inline-flex items-center justify-center w-8 h-8 rounded-full bg-red-100 text-red-700 font-bold"
              >
                !
              </span>
              <h3 className="text-lg font-semibold text-red-700">
                Ուժով ջնջել հին արտադրությունը՞
              </h3>
            </div>
            <p className="text-sm text-gray-800">
              Այս արտադրությունը ստեղծվել է մինչ v38: պաշարի շարժերը կապ չունեն
              այս արտադրության հետ, ուստի ավտոմատ ետ հաշվարկը հնարավոր չէ:
            </p>
            <p className="text-sm text-red-700 font-semibold mt-3">
              Ուժով ջնջումը կկատարի հետևյալը.
            </p>
            <ul className="text-sm text-gray-800 list-disc pl-5 mt-1 space-y-1">
              <li>Կհեռացվի միայն արտադրության գրառումը:</li>
              <li>
                Հումքի պաշարը <strong>ՉԻ</strong> վերականգնվի:
              </li>
              <li>
                Վաճառվող պաշարը <strong>ՉԻ</strong> փոփոխվի:
              </li>
              <li>
                Խոտանի պաշարը <strong>ՉԻ</strong> փոփոխվի:
              </li>
              <li>Հաշվետվությունները հնարավոր է այլևս չհամընկնեն:</li>
              <li>
                Գործողությունը <strong>անդարձելի</strong> է:
              </li>
            </ul>
            <p className="text-sm text-gray-800 mt-4">
              Շարունակելու համար մուտքագրեք{" "}
              <code className="bg-gray-100 px-1.5 py-0.5 rounded text-red-700 font-mono">
                FORCE DELETE
              </code>
              ։
            </p>
            <input
              type="text"
              value={forceInput}
              onChange={(e) => setForceInput(e.target.value)}
              placeholder="FORCE DELETE"
              autoComplete="off"
              spellCheck={false}
              className="mt-2 w-full rounded border border-gray-300 px-3 py-1.5 text-sm font-mono focus:outline-none focus:ring-2 focus:ring-red-500"
              disabled={submitting}
            />
            <div className="mt-5 flex justify-end gap-2">
              <button
                type="button"
                onClick={reset}
                disabled={submitting}
                className="px-3 py-1.5 text-sm rounded border border-gray-300 text-gray-700 hover:bg-gray-50 disabled:opacity-50"
              >
                Չեղարկել
              </button>
              <button
                type="button"
                onClick={handleForceDelete}
                disabled={submitting || forceInput.trim() !== FORCE_PHRASE}
                className="px-3 py-1.5 text-sm rounded bg-red-700 text-white hover:bg-red-800 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {submitting ? "Ջնջվում է…" : "Ուժով ջնջել"}
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
