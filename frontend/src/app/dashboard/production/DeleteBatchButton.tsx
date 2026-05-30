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
  batch_legacy_no_movement_link:
    "Այս արտադրությունը ստեղծվել է մինչ v38: ետ հաշվարկը ձեռքով է:",
  insufficient_permissions:
    "Չունեք իրավասություն ջնջելու արտադրությունը:",
  not_found: "Արտադրությունը արդեն ջնջվել է:",
};

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
  const [open, setOpen] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  const handleConfirm = async () => {
    setSubmitting(true);
    try {
      const res = await clientFetch(`/production/batches/${batchId}`, {
        method: "DELETE",
      });
      if (res.status === 204) {
        showToast("Արտադրությունը ջնջվեց և պաշարը վերականգնվեց", "success");
        setOpen(false);
        router.refresh();
        return;
      }
      const data = await res.json().catch(() => ({}));
      const code = (data?.code as string) || "";
      const msg =
        ERROR_MESSAGES[code] ||
        (data?.detail as string) ||
        "Չհաջողվեց ջնջել արտադրությունը";
      showToast(msg, "error");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <>
      <button
        type="button"
        onClick={() => setOpen(true)}
        className="text-red-700 hover:underline text-sm whitespace-nowrap"
      >
        Ջնջել
      </button>
      {open && (
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
                onClick={() => setOpen(false)}
                disabled={submitting}
                className="px-3 py-1.5 text-sm rounded border border-gray-300 text-gray-700 hover:bg-gray-50 disabled:opacity-50"
              >
                Չեղարկել
              </button>
              <button
                type="button"
                onClick={handleConfirm}
                disabled={submitting}
                className="px-3 py-1.5 text-sm rounded bg-red-600 text-white hover:bg-red-700 disabled:opacity-50"
              >
                {submitting ? "Ջնջվում է…" : "Ջնջել"}
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
