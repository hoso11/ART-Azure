"use client";

import React, { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { ProductVariant, Material, VariantMaterialRequirement } from "@/types";
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
      <h4 className="text-sm font-semibold mb-3">
        {isEdit ? "Խmbed-agrel տarberakat" : "Avelee tarberakat"}
      </h4>
      {error && <p className="text-xs text-red-600 mb-2">{error}</p>}
      <div className="grid grid-cols-2 gap-3">
        <FormField label="Չafss">
          <Input value={size} onChange={(e) => setSize(e.target.value)} required />
        </FormField>
        <FormField label="Guyyn">
          <Input value={color} onChange={(e) => setColor(e.target.value)} required />
        </FormField>
        <FormField label="Gin">
          <Input type="number" step="0.01" min="0" value={price} onChange={(e) => setPrice(e.target.value)} required />
        </FormField>
        <FormField label="Mnatsord">
          <Input type="number" min="0" value={stock} onChange={(e) => setStock(e.target.value)} required />
        </FormField>
      </div>
      <div className="flex gap-2 mt-3">
        <Button type="submit" size="sm" loading={loading}>{isEdit ? "Pahpanel" : "Aveletstanel"}</Button>
        <Button type="button" size="sm" variant="secondary" onClick={onClose}>Chegharkel</Button>
      </div>
    </form>
  );
}

// ── Material requirements inline panel ───────────────────

function RequirementRow({
  req,
  onUpdateQty,
  onDelete,
}: {
  req: VariantMaterialRequirement;
  onUpdateQty: (reqId: number, variantId: number, qty: string) => void;
  onDelete: (reqId: number, variantId: number) => void;
}) {
  const [editing, setEditing] = useState(false);
  const [qty, setQty] = useState(req.quantity_per_item.toString());

  return (
    <div className="flex items-center gap-3 text-xs py-1">
      <span className="flex-1 font-medium text-gray-700">
        {req.material?.name || `Material #${req.material_id}`}
      </span>
      {editing ? (
        <>
          <input
            type="number"
            step="0.001"
            min="0.001"
            value={qty}
            onChange={(e) => setQty(e.target.value)}
            className="w-20 border border-gray-300 rounded px-1.5 py-0.5 text-xs"
            autoFocus
          />
          <span className="text-gray-400">{req.material?.unit || ""}</span>
          <button
            onClick={() => { onUpdateQty(req.id, req.variant_id, qty); setEditing(false); }}
            className="text-brand-700 hover:text-brand-900 font-medium"
          >
            Save
          </button>
          <button
            onClick={() => { setEditing(false); setQty(req.quantity_per_item.toString()); }}
            className="text-gray-400 hover:text-gray-600"
          >
            Cancel
          </button>
        </>
      ) : (
        <>
          <span className="text-gray-500">
            {req.quantity_per_item} {req.material?.unit || ""}
          </span>
          <button onClick={() => setEditing(true)} className="text-gray-400 hover:text-brand-700" title="Edit">
            <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M16.862 4.487l1.687-1.688a1.875 1.875 0 112.652 2.652L10.582 16.07a4.5 4.5 0 01-1.897 1.13L6 18l.8-2.685a4.5 4.5 0 011.13-1.897l8.932-8.931z" />
            </svg>
          </button>
          <button onClick={() => onDelete(req.id, req.variant_id)} className="text-gray-400 hover:text-red-600" title="Remove">
            <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </>
      )}
    </div>
  );
}

function VariantMaterialPanel({ variantId }: { variantId: number }) {
  const [requirements, setRequirements] = useState<VariantMaterialRequirement[]>([]);
  const [materials, setMaterials] = useState<Material[]>([]);
  const [loading, setLoading] = useState(true);
  const [addMaterialId, setAddMaterialId] = useState("");
  const [addQty, setAddQty] = useState("1");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    Promise.all([
      fetch(`/api/v1/products/variants/${variantId}/materials`, { credentials: "include" }).then((r) => r.json()),
      fetch(`/api/v1/inventory/materials?limit=100`, { credentials: "include" }).then((r) => r.json()),
    ])
      .then(([reqs, mats]) => {
        setRequirements(Array.isArray(reqs) ? reqs : []);
        setMaterials(mats?.items || []);
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [variantId]);

  const handleAdd = async () => {
    if (!addMaterialId || !addQty) return;
    setSaving(true);
    setError("");
    try {
      const res = await fetch(`/api/v1/products/variants/${variantId}/materials`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({ material_id: parseInt(addMaterialId), quantity_per_item: parseFloat(addQty) }),
      });
      if (res.ok) {
        const newReq: VariantMaterialRequirement = await res.json();
        setRequirements((prev) => [...prev, newReq]);
        setAddMaterialId("");
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

  const handleUpdateQty = async (reqId: number, varId: number, qty: string) => {
    const parsed = parseFloat(qty);
    if (isNaN(parsed) || parsed <= 0) return;
    const res = await fetch(`/api/v1/products/variants/${varId}/materials/${reqId}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      credentials: "include",
      body: JSON.stringify({ quantity_per_item: parsed }),
    });
    if (res.ok) {
      const updated: VariantMaterialRequirement = await res.json();
      setRequirements((prev) => prev.map((r) => (r.id === reqId ? updated : r)));
    }
  };

  const handleDelete = async (reqId: number, varId: number) => {
    const res = await fetch(`/api/v1/products/variants/${varId}/materials/${reqId}`, {
      method: "DELETE",
      credentials: "include",
    });
    if (res.ok || res.status === 204) {
      setRequirements((prev) => prev.filter((r) => r.id !== reqId));
    }
  };

  const availableMaterials = materials.filter((m) => !requirements.find((r) => r.material_id === m.id));

  return (
    <div className="px-6 py-4 bg-brand-50 border-t border-brand-100">
      <h5 className="text-xs font-semibold text-gray-700 mb-2">
        Nyut&apos;akan pahanjner{" "}
        <span className="font-normal text-gray-400">(qty/item — deducted from inventory on stock increase)</span>
      </h5>

      {loading ? (
        <p className="text-xs text-gray-400">Loading...</p>
      ) : (
        <>
          {error && <p className="text-xs text-red-600 mb-2">{error}</p>}

          {requirements.length === 0 ? (
            <p className="text-xs text-gray-400 mb-3">Voch mi nyut ch&apos;e nshvats</p>
          ) : (
            <div className="divide-y divide-brand-100 mb-3">
              {requirements.map((req) => (
                <RequirementRow
                  key={req.id}
                  req={req}
                  onUpdateQty={handleUpdateQty}
                  onDelete={handleDelete}
                />
              ))}
            </div>
          )}

          {availableMaterials.length > 0 && (
            <div className="flex gap-2 items-center flex-wrap pt-2">
              <select
                value={addMaterialId}
                onChange={(e) => setAddMaterialId(e.target.value)}
                className="flex-1 min-w-[160px] text-xs border border-gray-300 rounded-md px-2 py-1.5 bg-white focus:outline-none focus:ring-1 focus:ring-brand-500"
              >
                <option value="">Entrel nyut...</option>
                {availableMaterials.map((m) => (
                  <option key={m.id} value={m.id}>
                    {m.name} ({m.unit}){m.inventory ? ` — ${m.inventory.quantity_on_hand} on hand` : ""}
                  </option>
                ))}
              </select>
              <input
                type="number"
                step="0.001"
                min="0.001"
                value={addQty}
                onChange={(e) => setAddQty(e.target.value)}
                className="w-24 text-xs border border-gray-300 rounded-md px-2 py-1.5 focus:outline-none focus:ring-1 focus:ring-brand-500"
                placeholder="qty/item"
              />
              <button
                onClick={handleAdd}
                disabled={saving || !addMaterialId || !addQty}
                className="text-xs px-3 py-1.5 bg-brand-800 text-white rounded-md hover:bg-brand-900 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {saving ? "..." : "+ Add"}
              </button>
            </div>
          )}
        </>
      )}
    </div>
  );
}

// ── Main VariantManager ───────────────────────────────────

export function VariantManager({ productId, variants }: { productId: number; variants: ProductVariant[] }) {
  const router = useRouter();
  const [showAdd, setShowAdd] = useState(false);
  const [editId, setEditId] = useState<number | null>(null);
  const [deleteId, setDeleteId] = useState<number | null>(null);
  const [deleting, setDeleting] = useState(false);
  const [materialsId, setMaterialsId] = useState<number | null>(null);

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
        <h3 className="font-semibold">Tarberakat-ner</h3>
        <button
          type="button"
          onClick={() => { setShowAdd(true); setEditId(null); setMaterialsId(null); }}
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
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Chafss</th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Guyyn</th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Gin</th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Mnatsord</th>
              <th className="px-6 py-3 w-32"></th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-200">
            {variants.length === 0 && (
              <tr><td colSpan={5} className="px-6 py-8 text-center text-gray-500 text-sm">Tarberakat-ner chkan</td></tr>
            )}
            {variants.map((v) => (
              <React.Fragment key={v.id}>
                <tr className={materialsId === v.id ? "bg-brand-50/40" : ""}>
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
                            <button onClick={() => setDeleteId(null)} className="text-xs text-gray-500 hover:text-gray-700">
                              Cancel
                            </button>
                          </span>
                        ) : (
                          <span className="flex items-center gap-2 justify-end">
                            <button
                              onClick={() => setMaterialsId(materialsId === v.id ? null : v.id)}
                              className={materialsId === v.id ? "text-brand-700" : "text-gray-400 hover:text-brand-600"}
                              title="Material Requirements"
                            >
                              <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                                <path strokeLinecap="round" strokeLinejoin="round" d="M20.25 7.5l-.625 10.632a2.25 2.25 0 01-2.247 2.118H6.622a2.25 2.25 0 01-2.247-2.118L3.75 7.5M10 11.25h4M3.375 7.5h17.25c.621 0 1.125-.504 1.125-1.125v-1.5c0-.621-.504-1.125-1.125-1.125H3.375c-.621 0-1.125.504-1.125 1.125v1.5c0 .621.504 1.125 1.125 1.125z" />
                              </svg>
                            </button>
                            <button
                              onClick={() => { setEditId(v.id); setShowAdd(false); setMaterialsId(null); }}
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
                {materialsId === v.id && (
                  <tr>
                    <td colSpan={5} className="p-0">
                      <VariantMaterialPanel variantId={v.id} />
                    </td>
                  </tr>
                )}
              </React.Fragment>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}
