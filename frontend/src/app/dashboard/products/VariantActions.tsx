"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { ProductVariant } from "@/types";
import { Button } from "@/components/ui/Button";
import { FormField, Input } from "@/components/ui/FormField";
import { formatCurrency } from "@/lib/utils";

function VariantForm({
  productId,
  variant,
  onClose,
}: {
  productId: number;
  variant?: ProductVariant;
  onClose: () => void;
}) {
  const router = useRouter();
  const [size, setSize] = useState(variant?.size || "");
  const [color, setColor] = useState(variant?.color || "");
  const [price, setPrice] = useState(variant?.price?.toString() || "0");
  const [stock, setStock] = useState(variant?.stock_quantity?.toString() || "0");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const isEdit = !!variant;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError("");

    const url = isEdit
      ? `/api/v1/products/variants/${variant.id}`
      : `/api/v1/products/${productId}/variants`;

    try {
      const res = await fetch(url, {
        method: isEdit ? "PATCH" : "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({
          size,
          color,
          price: parseFloat(price),
          stock_quantity: parseInt(stock),
        }),
      });
      if (!res.ok) {
        const data = await res.json();
        setError(data.detail || "Failed to save variant");
        return;
      }
      onClose();
      router.refresh();
    } catch {
      setError("Connection error");
    } finally {
      setLoading(false);
    }
  };

  return (
    <form onSubmit={handleSubmit} className="bg-gray-50 border rounded-lg p-4 mb-4">
      <h4 className="text-sm font-semibold mb-3">{isEdit ? "Խմբագրել տարբերակ" : "Ավելացնել տարբերակ"}</h4>
      {error && <p className="text-xs text-red-600 mb-2">{error}</p>}
      <div className="grid grid-cols-2 gap-3">
        <FormField label="Չափս">
          <Input value={size} onChange={(e) => setSize(e.target.value)} required />
        </FormField>
        <FormField label="Գույն">
          <Input value={color} onChange={(e) => setColor(e.target.value)} required />
        </FormField>
        <FormField label="Գին">
          <Input type="number" step="0.01" min="0" value={price} onChange={(e) => setPrice(e.target.value)} required />
        </FormField>
        <FormField label="Մնացորդ">
          <Input type="number" min="0" value={stock} onChange={(e) => setStock(e.target.value)} required />
        </FormField>
      </div>
      <div className="flex gap-2 mt-3">
        <Button type="submit" size="sm" loading={loading}>{isEdit ? "Պահպանել" : "Ավելացնել"}</Button>
        <Button type="button" size="sm" variant="secondary" onClick={onClose}>Չեղարկել</Button>
      </div>
    </form>
  );
}

export function VariantManager({ productId, variants }: { productId: number; variants: ProductVariant[] }) {
  const router = useRouter();
  const [showAdd, setShowAdd] = useState(false);
  const [editId, setEditId] = useState<number | null>(null);
  const [deleteId, setDeleteId] = useState<number | null>(null);
  const [deleting, setDeleting] = useState(false);

  const handleDelete = async (variantId: number) => {
    setDeleting(true);
    try {
      const res = await fetch(`/api/v1/products/variants/${variantId}`, {
        method: "DELETE",
        credentials: "include",
      });
      if (res.ok || res.status === 204) {
        setDeleteId(null);
        router.refresh();
      }
    } catch {
      // ignore
    } finally {
      setDeleting(false);
    }
  };

  return (
    <>
      <div className="flex items-center justify-between">
        <h3 className="font-semibold">Տարբերակներ</h3>
        <button
          type="button"
          onClick={() => { setShowAdd(true); setEditId(null); }}
          className="text-xs font-medium text-brand-700 hover:text-brand-900"
        >
          + Add Variant
        </button>
      </div>

      {showAdd && (
        <div className="px-4 pt-4">
          <VariantForm productId={productId} onClose={() => setShowAdd(false)} />
        </div>
      )}

      <div className="p-0">
        <table className="min-w-full divide-y divide-gray-200">
          <thead className="bg-gray-50">
            <tr>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Չափս</th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Գույն</th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Գին</th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Մնացորդ</th>
              <th className="px-6 py-3 w-20"></th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-200">
            {variants.length === 0 && (
              <tr><td colSpan={5} className="px-6 py-8 text-center text-gray-500 text-sm">Տարբերակներ չկան</td></tr>
            )}
            {variants.map((v) => (
              <tr key={v.id}>
                {editId === v.id ? (
                  <td colSpan={5} className="p-4">
                    <VariantForm productId={productId} variant={v} onClose={() => setEditId(null)} />
                  </td>
                ) : (
                  <>
                    <td className="px-6 py-4 text-sm">{v.size}</td>
                    <td className="px-6 py-4 text-sm">{v.color}</td>
                    <td className="px-6 py-4 text-sm">{formatCurrency(v.price)}</td>
                    <td className="px-6 py-4 text-sm">{v.stock_quantity}</td>
                    <td className="px-6 py-4 text-right">
                      {deleteId === v.id ? (
                        <span className="flex items-center gap-1 justify-end">
                          <button
                            onClick={() => handleDelete(v.id)}
                            disabled={deleting}
                            className="text-xs text-red-600 font-medium hover:text-red-800 disabled:opacity-50"
                          >
                            {deleting ? "..." : "Confirm"}
                          </button>
                          <button
                            onClick={() => setDeleteId(null)}
                            className="text-xs text-gray-500 hover:text-gray-700"
                          >
                            Cancel
                          </button>
                        </span>
                      ) : (
                        <span className="flex items-center gap-2 justify-end">
                          <button
                            onClick={() => { setEditId(v.id); setShowAdd(false); }}
                            className="text-gray-400 hover:text-brand-700"
                            title="Edit"
                          >
                            <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                              <path strokeLinecap="round" strokeLinejoin="round" d="M16.862 4.487l1.687-1.688a1.875 1.875 0 112.652 2.652L10.582 16.07a4.5 4.5 0 01-1.897 1.13L6 18l.8-2.685a4.5 4.5 0 011.13-1.897l8.932-8.931z" />
                            </svg>
                          </button>
                          <button
                            onClick={() => setDeleteId(v.id)}
                            className="text-gray-400 hover:text-red-600"
                            title="Delete"
                          >
                            <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                              <path strokeLinecap="round" strokeLinejoin="round" d="M14.74 9l-.346 9m-4.788 0L9.26 9m9.968-3.21c.342.052.682.107 1.022.166m-1.022-.165L18.16 19.673a2.25 2.25 0 01-2.244 2.077H8.084a2.25 2.25 0 01-2.244-2.077L4.772 5.79m14.456 0a48.108 48.108 0 00-3.478-.397m-12 .562c.34-.059.68-.114 1.022-.165m0 0a48.11 48.11 0 013.478-.397m7.5 0v-.916c0-1.18-.91-2.164-2.09-2.201a51.964 51.964 0 00-3.32 0c-1.18.037-2.09 1.022-2.09 2.201v.916m7.5 0a48.667 48.667 0 00-7.5 0" />
                            </svg>
                          </button>
                        </span>
                      )}
                    </td>
                  </>
                )}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}
