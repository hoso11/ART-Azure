"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { showToast } from "@/lib/toast";
import { clientFetch } from "@/lib/api.client";

const ERROR_MESSAGES: Record<string, string> = {
  insufficient_permissions: "Չունեք իրավասություն ուժով ջնջելու պատվերը:",
  not_found: "Պատվերը արդեն ջնջված է:",
};

const FORCE_PHRASE = "FORCE DELETE";

export function ForceDeleteOrderButton({ orderId }: { orderId: number }) {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [forceInput, setForceInput] = useState("");

  const reset = () => {
    setOpen(false);
    setForceInput("");
  };

  const handleForceDelete = async () => {
    if (forceInput.trim() !== FORCE_PHRASE) return;
    setSubmitting(true);
    try {
      const res = await clientFetch(`/orders/${orderId}/force`, {
        method: "DELETE",
      });
      if (res.status === 204) {
        showToast("Պատվերը ուժով ջնջվեց", "success");
        reset();
        router.refresh();
        return;
      }
      const data = await res.json().catch(() => ({}));
      const code = (data?.code as string) || "";
      const msg =
        ERROR_MESSAGES[code] ||
        (data?.detail as string) ||
        "Չհաջողվեց ուժով ջնջել պատվերը";
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
        className="text-red-800 hover:underline text-sm whitespace-nowrap"
        title="Ուժով ջնջել (չի վերականգնվում)"
      >
        Ուժով ջնջել
      </button>
      {open && (
        <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center px-4">
          <div className="bg-white rounded-lg shadow-lg border-2 border-red-600 p-6 max-w-lg w-full">
            <div className="flex items-center gap-2 mb-3">
              <span
                aria-hidden="true"
                className="inline-flex items-center justify-center w-8 h-8 rounded-full bg-red-100 text-red-700 font-bold"
              >
                !
              </span>
              <h3 className="text-lg font-semibold text-red-700">
                Ուժով ջնջել պատվեր #{orderId}՞
              </h3>
            </div>
            <p className="text-sm text-gray-800">
              Ուժով ջնջումը կիրականացնի հետևյալը.
            </p>
            <ul className="text-sm text-gray-800 list-disc pl-5 mt-2 space-y-1">
              <li>
                Պատվերի գրառումը <strong>ընդմիշտ</strong> կջնջվի:
              </li>
              <li>
                Պատվերի տողերը, արտադրության փուլերը և լոգերը կջնջվեն:
              </li>
              <li>
                Պահեստի շարժերի պատմությունը կպահպանվի (
                <code className="bg-gray-100 px-1 py-0.5 rounded font-mono">
                  order_id
                </code>{" "}
                դարձվում է NULL):
              </li>
              <li>
                Հաշվետվությունները կարող են <strong>այլևս չհամընկնել</strong>:
              </li>
              <li>
                Գործողությունը <strong>անդարձելի</strong> է:
              </li>
            </ul>
            <p className="text-xs text-gray-500 mt-3">
              Եթե սովորական ջնջումը հնարավոր է, օգտագործեք այն:
            </p>
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
