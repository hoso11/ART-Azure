"use client";

import React, { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { ProductVariant, Material, ProductSizeMaterialRequirement } from "@/types";
import { Button } from "@/components/ui/Button";
import { FormField, Input } from "@/components/ui/FormField";
import { formatCurrency, formatNumber } from "@/lib/utils";
import { showToast } from "@/lib/toast";
import { ForceDeleteVariantButton } from "./ForceDeleteVariantButton";

const VARIANT_DELETE_ERRORS: Record<string, string> = {
  variant_has_orders: "Հնարավոր չէ ջնջել. տարբերակը կապված է պատվերների հետ:",
  variant_has_production_batches:
    "Հնարավոր չէ ջնջել. տարբերակը կապված է արտադրության հետ:",
  variant_in_use:
    "Հնարավոր չէ ջնջել. տարբերակը կապակցված է այլ գրառումների հետ:",
  insufficient_permissions: "Չունեք իրավասություն ջնջելու տարբերակը:",
  not_found: "Տարբերակը արդեն ջնջված է:",
};

// ── Variant form (add / edit) ─────────────────────────

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
        body: JSON.stringify({ size, color, price: parseFloat(price), stock_quantity: parseInt(stock) }),
      });
      if (!res.ok) {
        const d = await res.json();
        setError(d.detail || "Failed to save variant");
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
      <h4 className="text-sm font-semibold mb-3">
        {isEdit ? "Խմբագրել տարբերակ" : "Ավելացնել տարբերակ"}
      </h4>
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

// ── Material requirements row (inline edit) ───────────

function RequirementRow({
  req,
  onSave,
  onDelete,
}: {
  req: ProductSizeMaterialRequirement;
  onSave: (reqId: number, qty: string) => void;
  onDelete: (reqId: number) => void;
}) {
  const [editing, setEditing] = useState(false);
  const [qty, setQty] = useState(req.quantity_per_item.toString());

  return (
    <tr className="hover:bg-gray-50">
      <td className="px-4 py-2 text-sm">{req.material?.name ?? `#${req.material_id}`}</td>
      <td className="px-4 py-2 text-sm">{req.size}</td>
      <td className="px-4 py-2 text-sm">
        {editing ? (
          <input
            type="number"
            step="0.001"
            min="0.001"
            value={qty}
            onChange={(e) => setQty(e.target.value)}
            className="w-24 border border-gray-300 rounded px-1.5 py-0.5 text-sm"
            autoFocus
          />
        ) : (
          formatNumber(req.quantity_per_item)
        )}
      </td>
      <td className="px-4 py-2 text-sm text-gray-500">{req.material?.unit ?? ""}</td>
      <td className="px-4 py-2 text-right">
        {editing ? (
          <span className="flex items-center gap-2 justify-end text-xs">
            <button
              onClick={() => { onSave(req.id, qty); setEditing(false); }}
              className="text-brand-700 font-medium hover:text-brand-900"
            >
              Save
            </button>
            <button
              onClick={() => { setEditing(false); setQty(req.quantity_per_item.toString()); }}
              className="text-gray-400 hover:text-gray-600"
            >
              Cancel
            </button>
          </span>
        ) : (
          <span className="flex items-center gap-2 justify-end">
            <button onClick={() => setEditing(true)} className="text-gray-400 hover:text-brand-700" title="Edit">
              <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M16.862 4.487l1.687-1.688a1.875 1.875 0 112.652 2.652L10.582 16.07a4.5 4.5 0 01-1.897 1.13L6 18l.8-2.685a4.5 4.5 0 011.13-1.897l8.932-8.931z" />
              </svg>
            </button>
            <button onClick={() => onDelete(req.id)} className="text-gray-400 hover:text-red-600" title="Delete">
              <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M14.74 9l-.346 9m-4.788 0L9.26 9m9.968-3.21c.342.052.682.107 1.022.166m-1.022-.165L18.16 19.673a2.25 2.25 0 01-2.244 2.077H8.084a2.25 2.25 0 01-2.244-2.077L4.772 5.79m14.456 0a48.108 48.108 0 00-3.478-.397m-12 .562c.34-.059.68-.114 1.022-.165m0 0a48.11 48.11 0 013.478-.397m7.5 0v-.916c0-1.18-.91-2.164-2.09-2.201a51.964 51.964 0 00-3.32 0c-1.18.037-2.09 1.022-2.09 2.201v.916m7.5 0a48.667 48.667 0 00-7.5 0" />
              </svg>
            </button>
          </span>
        )}
      </td>
    </tr>
  );
}

// ── Product-level material requirements panel ─────────
// Columns: Material (Նyut) | Size (Չafss) | Qty/item | Unit | Actions

function ProductMaterialRequirementsPanel({
  productId,
  variantSizes,
}: {
  productId: number;
  variantSizes: string[];
}) {
  const [requirements, setRequirements] = useState<ProductSizeMaterialRequirement[]>([]);
  const [materials, setMaterials] = useState<Material[]>([]);
  const [loading, setLoading] = useState(true);
  const [addMaterialId, setAddMaterialId] = useState("");
  const [addSize, setAddSize] = useState("");
  const [addQty, setAddQty] = useState("1");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  const selectedMaterial = materials.find((m) => m.id === parseInt(addMaterialId));

  useEffect(() => {
    Promise.all([
      fetch(`/api/v1/products/${productId}/size-requirements`, { credentials: "include" }).then((r) => r.json()),
      fetch(`/api/v1/inventory/materials?limit=100`, { credentials: "include" }).then((r) => r.json()),
    ])
      .then(([reqs, mats]) => {
        setRequirements(Array.isArray(reqs) ? reqs : []);
        setMaterials(mats?.items || []);
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [productId]);

  const handleAdd = async () => {
    if (!addMaterialId || !addSize || !addQty) return;
    setSaving(true);
    setError("");
    try {
      const res = await fetch(`/api/v1/products/${productId}/size-requirements`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({
          material_id: parseInt(addMaterialId),
          size: addSize,
          quantity_per_item: parseFloat(addQty),
        }),
      });
      if (res.ok) {
        const newReq: ProductSizeMaterialRequirement = await res.json();
        setRequirements((prev) =>
          [...prev, newReq].sort((a, b) => a.size.localeCompare(b.size) || (a.material?.name ?? "").localeCompare(b.material?.name ?? ""))
        );
        setAddMaterialId("");
        setAddSize("");
        setAddQty("1");
      } else {
        const d = await res.json();
        setError(d.detail || "Failed to add requirement");
      }
    } catch {
      setError("Connection error");
    } finally {
      setSaving(false);
    }
  };

  const handleSave = async (reqId: number, qty: string) => {
    const parsed = parseFloat(qty);
    if (isNaN(parsed) || parsed <= 0) return;
    const req = requirements.find((r) => r.id === reqId);
    if (!req) return;
    const res = await fetch(`/api/v1/products/${productId}/size-requirements/${reqId}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      credentials: "include",
      body: JSON.stringify({ quantity_per_item: parsed }),
    });
    if (res.ok) {
      const updated: ProductSizeMaterialRequirement = await res.json();
      setRequirements((prev) => prev.map((r) => (r.id === reqId ? updated : r)));
    }
  };

  const handleDelete = async (reqId: number) => {
    try {
      const res = await fetch(`/api/v1/products/${productId}/size-requirements/${reqId}`, {
        method: "DELETE",
        credentials: "include",
      });
      if (res.status === 204 || res.ok) {
        setRequirements((prev) => prev.filter((r) => r.id !== reqId));
        showToast("Պահանջը հեռացվեց", "success");
        return;
      }
      const data = await res.json().catch(() => ({}));
      showToast(data?.detail || "Չհաջողվեց հեռացնել պահանջը", "error");
    } catch {
      showToast("Կապի սխալ. չհաջողվեց հեռացնել պահանջը", "error");
    }
  };

  return (
    <div className="mt-6 pt-5 border-t border-gray-200">
      <h3 className="font-semibold text-gray-900 mb-3">Նյութական պահանջներ</h3>
      <p className="text-xs text-gray-400 mb-3">
        Սահմանում է, թե յուրաքանչյուր չափսի մեկ պատրաստի արտադրանքի համար որքան նյութ է օգտագործվում։ Պահեստը ավտոմատ նվազեցվում է, երբ տարբերակի մնացորդը ավելացվում է։
      </p>

      {loading ? (
        <p className="text-sm text-gray-400">Loading...</p>
      ) : (
        <>
          <div className="overflow-x-auto rounded-lg border border-gray-200">
            <table className="min-w-full divide-y divide-gray-200">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Նյութ</th>
                  <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Չափս</th>
                  <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Քանակ / մեկ հատի համար</th>
                  <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Չափման միավոր</th>
                  <th className="px-4 py-2 w-20"></th>
                </tr>
              </thead>
              <tbody className="bg-white divide-y divide-gray-100">
                {requirements.length === 0 ? (
                  <tr>
                    <td colSpan={5} className="px-4 py-6 text-center text-sm text-gray-400">
                      Պահանջներ չկան — ավելացրեք ստորև
                    </td>
                  </tr>
                ) : (
                  requirements.map((req) => (
                    <RequirementRow key={req.id} req={req} onSave={handleSave} onDelete={handleDelete} />
                  ))
                )}
              </tbody>
            </table>
          </div>

          {/* Add row form */}
          <div className="mt-3 flex flex-wrap gap-2 items-end">
            {/* Material select — only from existing inventory */}
            <div className="flex flex-col gap-1 flex-1 min-w-[180px]">
              <label className="text-xs text-gray-500 font-medium">Նյութ</label>
              <select
                value={addMaterialId}
                onChange={(e) => setAddMaterialId(e.target.value)}
                className="text-sm border border-gray-300 rounded-md px-2 py-1.5 bg-white focus:outline-none focus:ring-1 focus:ring-brand-500"
              >
                <option value="">Ընտրել նյութ...</option>
                {materials.map((m) => (
                  <option key={m.id} value={m.id}>
                    {m.name} ({m.unit}){m.inventory ? ` — ${formatNumber(m.inventory.quantity_on_hand)} on hand` : ""}
                  </option>
                ))}
              </select>
            </div>

            {/* Size select — from existing variant sizes */}
            <div className="flex flex-col gap-1 min-w-[120px]">
              <label className="text-xs text-gray-500 font-medium">Չափս</label>
              <select
                value={addSize}
                onChange={(e) => setAddSize(e.target.value)}
                className="text-sm border border-gray-300 rounded-md px-2 py-1.5 bg-white focus:outline-none focus:ring-1 focus:ring-brand-500"
              >
                <option value="">Ընտրել չափս...</option>
                {variantSizes.map((s) => (
                  <option key={s} value={s}>{s}</option>
                ))}
              </select>
            </div>

            {/* Qty/item */}
            <div className="flex flex-col gap-1 w-28">
              <label className="text-xs text-gray-500 font-medium">
                Քանակ / մեկ հատի համար{selectedMaterial ? ` (${selectedMaterial.unit})` : ""}
              </label>
              <input
                type="number"
                step="0.001"
                min="0.001"
                value={addQty}
                onChange={(e) => setAddQty(e.target.value)}
                className="text-sm border border-gray-300 rounded-md px-2 py-1.5 focus:outline-none focus:ring-1 focus:ring-brand-500"
              />
            </div>

            <div className="flex flex-col justify-end">
              <button
                onClick={handleAdd}
                disabled={saving || !addMaterialId || !addSize || !addQty}
                className="text-sm px-4 py-1.5 bg-brand-800 text-white rounded-md hover:bg-brand-900 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {saving ? "..." : "+ Ավելացնել"}
              </button>
            </div>
          </div>

          {error && <p className="text-xs text-red-600 mt-2">{error}</p>}

          {variantSizes.length === 0 && (
            <p className="text-xs text-amber-600 mt-2">
              Նախ ստեղծեք գոնե մեկ տարբերակ — չափսերը գալիս են գոյություն ունեցող տarberakat-ներից։
            </p>
          )}
        </>
      )}
    </div>
  );
}

// ── Main VariantManager ───────────────────────────────────

export function VariantManager({ productId, variants, isAdmin = false }: { productId: number; variants: ProductVariant[]; isAdmin?: boolean }) {
  const router = useRouter();
  const [showAdd, setShowAdd] = useState(false);
  const [editId, setEditId] = useState<number | null>(null);
  const [deleteId, setDeleteId] = useState<number | null>(null);
  const [deleting, setDeleting] = useState(false);

  const variantSizes = Array.from(new Set(variants.map((v) => v.size))).sort();

  const handleDelete = async (variantId: number) => {
    setDeleting(true);
    try {
      const res = await fetch(`/api/v1/products/variants/${variantId}`, {
        method: "DELETE",
        credentials: "include",
      });
      if (res.status === 204 || res.ok) {
        setDeleteId(null);
        showToast("Տարբերակը ջնջվեց", "success");
        router.refresh();
        return;
      }
      const data = await res.json().catch(() => ({}));
      const code = (data?.code as string) || "";
      const msg =
        VARIANT_DELETE_ERRORS[code] ||
        (data?.detail as string) ||
        "Չհաջողվեց ջնջել տարբերակը";
      showToast(msg, "error");
      // Reset the inline Confirm/Cancel UI so the row stops looking stuck.
      setDeleteId(null);
    } catch {
      showToast("Կապի սխալ. չհաջողվեց ջնջել տարբերակը", "error");
      setDeleteId(null);
    } finally {
      setDeleting(false);
    }
  };

  return (
    <>
      <div className="flex items-center justify-between">
        <h3 className="font-semibold">Տարբերակատ-ներ</h3>
        <button
          type="button"
          onClick={() => { setShowAdd(true); setEditId(null); }}
          className="text-xs font-medium text-brand-700 hover:text-brand-900"
        >
          + Ավելացնել տարբերակ
        </button>
      </div>

      {showAdd && (
        <div className="pt-4">
          <VariantForm productId={productId} onClose={() => setShowAdd(false)} />
        </div>
      )}

      <div className="mt-2">
        <table className="min-w-full divide-y divide-gray-200">
          <thead className="bg-gray-50">
            <tr>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Չափս</th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Գույն</th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Գին</th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Մնացորդ</th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Խոտան</th>
              <th className="px-6 py-3 w-24"></th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-200">
            {variants.length === 0 && (
              <tr><td colSpan={6} className="px-6 py-8 text-center text-gray-500 text-sm">Տարբերակատ-ներ չկան</td></tr>
            )}
            {variants.map((v) => {
              const orderCount = v.order_items_count ?? 0;
              const batchCount = v.production_batches_count ?? 0;
              const hasBlockers = orderCount > 0 || batchCount > 0;
              return (
              <React.Fragment key={v.id}>
                <tr>
                  {editId === v.id ? (
                    <td colSpan={6} className="p-4">
                      <VariantForm productId={productId} variant={v} onClose={() => setEditId(null)} />
                    </td>
                  ) : (
                    <>
                      <td className="px-6 py-4 text-sm">{v.size}</td>
                      <td className="px-6 py-4 text-sm">{v.color}</td>
                      <td className="px-6 py-4 text-sm">{formatCurrency(v.price)}</td>
                      <td className="px-6 py-4 text-sm">{formatNumber(v.stock_quantity)}</td>
                      <td className={`px-6 py-4 text-sm ${v.damaged_stock_quantity > 0 ? "text-red-700 font-medium" : "text-gray-400"}`}>{formatNumber(v.damaged_stock_quantity)}</td>
                      <td className="px-6 py-4 text-right">
                        {deleteId === v.id ? (
                          <span className="flex items-center gap-1 justify-end text-xs">
                            <button
                              onClick={() => handleDelete(v.id)}
                              disabled={deleting}
                              className="text-red-600 font-medium hover:text-red-800 disabled:opacity-50"
                            >
                              {deleting ? "..." : "Confirm"}
                            </button>
                            <button onClick={() => setDeleteId(null)} className="text-gray-500 hover:text-gray-700">
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
                {hasBlockers && editId !== v.id && (
                  <tr className="bg-amber-50">
                    <td colSpan={6} className="px-6 py-2 text-xs text-amber-900">
                      <div className="flex items-center justify-between gap-3 flex-wrap">
                        <span>
                          <span className="font-medium">Չի կարող ջնջվել՝</span>{" "}
                          {orderCount > 0 && (
                            <span>
                              կապված է <strong>{orderCount}</strong> պատվերի հետ
                            </span>
                          )}
                          {orderCount > 0 && batchCount > 0 && <span>, </span>}
                          {batchCount > 0 && (
                            <span>
                              կապված է <strong>{batchCount}</strong> արտադրության հետ
                            </span>
                          )}
                          :
                        </span>
                        {isAdmin && (
                          <ForceDeleteVariantButton
                            variantId={v.id}
                            variantLabel={`${v.size} / ${v.color || "—"}`}
                            orderItemsCount={orderCount}
                            batchesCount={batchCount}
                          />
                        )}
                      </div>
                    </td>
                  </tr>
                )}
              </React.Fragment>
              );
            })}
          </tbody>
        </table>
      </div>

      {/* Product-level material requirements — one table for all sizes */}
      <ProductMaterialRequirementsPanel productId={productId} variantSizes={variantSizes} />
    </>
  );
}
