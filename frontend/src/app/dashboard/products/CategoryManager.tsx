"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { ProductCategory } from "@/types";
import { showToast } from "@/lib/toast";
import { clientFetch } from "@/lib/api.client";
import { ForceDeleteCategoryButton } from "./ForceDeleteCategoryButton";

const CATEGORY_DELETE_ERRORS: Record<string, string> = {
  category_has_products:
    "Հնարավոր չէ ջնջել. կատեգորիան կապված է ապրանքների հետ:",
  insufficient_permissions: "Չունեք իրավասություն ջնջելու կատեգորիան:",
  not_found: "Կատեգորիան արդեն ջնջվել է:",
};

export function CategoryManagerButton({
  categories,
}: {
  categories: ProductCategory[];
}) {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [creating, setCreating] = useState(false);
  const [newName, setNewName] = useState("");
  const [busyId, setBusyId] = useState<number | null>(null);

  const handleCreate = async () => {
    const name = newName.trim();
    if (!name) return;
    setCreating(true);
    try {
      const res = await clientFetch("/categories", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name }),
      });
      if (res.status === 201) {
        showToast("Կատեգորիան ստեղծվեց", "success");
        setNewName("");
        router.refresh();
        return;
      }
      const data = await res.json().catch(() => ({}));
      showToast(
        (data?.detail as string) || "Չհաջողվեց ստեղծել կատեգորիան",
        "error",
      );
    } finally {
      setCreating(false);
    }
  };

  const handleNormalDelete = async (catId: number) => {
    setBusyId(catId);
    try {
      const res = await clientFetch(`/categories/${catId}`, {
        method: "DELETE",
      });
      if (res.status === 204) {
        showToast("Կատեգորիան ջնջվեց", "success");
        router.refresh();
        return;
      }
      const data = await res.json().catch(() => ({}));
      const code = (data?.code as string) || "";
      const msg =
        CATEGORY_DELETE_ERRORS[code] ||
        (data?.detail as string) ||
        "Չհաջողվեց ջնջել կատեգորիան";
      showToast(msg, "error");
    } finally {
      setBusyId(null);
    }
  };

  return (
    <>
      <button
        type="button"
        onClick={() => setOpen(true)}
        className="px-3 py-1.5 text-sm rounded-lg border border-gray-300 text-gray-700 hover:bg-gray-50 whitespace-nowrap"
      >
        Կատեգորիաներ
      </button>
      {open && (
        <div className="fixed inset-0 bg-black/40 z-40 flex items-center justify-center px-4">
          <div className="bg-white rounded-lg shadow-lg p-6 max-w-xl w-full">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-lg font-semibold text-gray-900">
                Կատեգորիաների կառավարում
              </h3>
              <button
                type="button"
                onClick={() => setOpen(false)}
                className="text-gray-400 hover:text-gray-600 text-2xl leading-none"
                aria-label="Փակել"
              >
                ×
              </button>
            </div>

            {/* Create new */}
            <div className="flex items-end gap-2 mb-4 pb-4 border-b border-gray-200">
              <div className="flex-1">
                <label className="block text-xs text-gray-500 font-medium mb-1">
                  Նոր կատեգորիա
                </label>
                <input
                  type="text"
                  value={newName}
                  onChange={(e) => setNewName(e.target.value)}
                  placeholder="Անվանում"
                  className="w-full text-sm border border-gray-300 rounded px-2 py-1.5 focus:outline-none focus:ring-1 focus:ring-brand-500"
                />
              </div>
              <button
                type="button"
                onClick={handleCreate}
                disabled={creating || !newName.trim()}
                className="text-sm px-3 py-1.5 bg-brand-800 text-white rounded hover:bg-brand-900 disabled:opacity-50 disabled:cursor-not-allowed whitespace-nowrap"
              >
                {creating ? "..." : "+ Ավելացնել"}
              </button>
            </div>

            {/* List */}
            <div className="max-h-96 overflow-y-auto">
              <table className="min-w-full divide-y divide-gray-200 text-sm">
                <thead className="bg-gray-50 sticky top-0">
                  <tr>
                    <th className="px-3 py-2 text-left text-xs font-medium text-gray-500 uppercase">
                      Անվանում
                    </th>
                    <th className="px-3 py-2 text-left text-xs font-medium text-gray-500 uppercase">
                      Ապրանքներ
                    </th>
                    <th className="px-3 py-2"></th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100">
                  {categories.length === 0 && (
                    <tr>
                      <td
                        colSpan={3}
                        className="px-3 py-6 text-center text-gray-400"
                      >
                        Կատեգորիաներ չկան
                      </td>
                    </tr>
                  )}
                  {categories.map((c) => {
                    const count = c.product_count ?? 0;
                    const blocked = count > 0;
                    return (
                      <tr key={c.id} className="hover:bg-gray-50 align-top">
                        <td className="px-3 py-2 text-sm text-gray-900">
                          {c.name}
                        </td>
                        <td className="px-3 py-2 text-sm text-gray-600">
                          {count}
                        </td>
                        <td className="px-3 py-2 text-right whitespace-nowrap">
                          <div className="flex items-center justify-end gap-3">
                            {blocked ? (
                              <>
                                <span className="text-xs text-amber-700">
                                  Կապված է {count} ապրանքի հետ
                                </span>
                                <ForceDeleteCategoryButton
                                  categoryId={c.id}
                                  categoryName={c.name}
                                  productCount={count}
                                  onDeleted={() => setOpen(false)}
                                />
                              </>
                            ) : (
                              <button
                                type="button"
                                onClick={() => handleNormalDelete(c.id)}
                                disabled={busyId === c.id}
                                className="text-red-700 hover:underline text-xs font-medium disabled:opacity-50"
                              >
                                {busyId === c.id ? "..." : "Ջնջել"}
                              </button>
                            )}
                          </div>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>

            <div className="mt-5 flex justify-end">
              <button
                type="button"
                onClick={() => setOpen(false)}
                className="px-3 py-1.5 text-sm rounded border border-gray-300 text-gray-700 hover:bg-gray-50"
              >
                Փակել
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
