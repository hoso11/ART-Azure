"use client";

import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { Modal } from "@/components/ui/Modal";
import { Button } from "@/components/ui/Button";
import { FormField, Input, Select } from "@/components/ui/FormField";
import { showToast } from "@/lib/toast";
import { clientFetch } from "@/lib/api.client";
import type { Product } from "@/types";

const STAGE_LABELS: Record<string, string> = {
  cutting: "Կտրում",
  processing: "Մշակում",
  quality_control: "Որակի վերահսկում",
  packaging: "Փաթեթավորում",
  warehousing: "Պահեստավորում",
  ready_for_shipment: "Պատրաստ է առաքման",
};

const STATUS_LABELS: Record<string, string> = {
  pending: "Սպասման մեջ",
  in_progress: "Ընթացքի մեջ",
  completed: "Ավարտված",
};

type Mode = "single" | "bulk";

const MAX_BULK_ITEMS = 50;

// Per-variant state in bulk mode. `qty` stays a string so the input can be
// briefly empty without coercing to 0; we Number() it at submit time.
type BulkRowState = { selected: boolean; qty: string };

export function CreateBatchModal({
  open,
  onClose,
}: {
  open: boolean;
  onClose: () => void;
}) {
  const router = useRouter();
  const [products, setProducts] = useState<Product[]>([]);
  const [productsLoading, setProductsLoading] = useState(false);
  const [productsError, setProductsError] = useState<string | null>(null);
  const [productsLoadId, setProductsLoadId] = useState(0);
  const [mode, setMode] = useState<Mode>("single");
  const [productId, setProductId] = useState<string>("");

  // Single mode
  const [variantId, setVariantId] = useState<string>("");
  const [quantity, setQuantity] = useState<string>("1");

  // Bulk mode
  const [bulkRows, setBulkRows] = useState<Record<number, BulkRowState>>({});
  const [commonQty, setCommonQty] = useState<string>("10");
  const [colorFilter, setColorFilter] = useState<string>("");

  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!open) return;
    let cancelled = false;

    async function loadProducts() {
      setProductsLoading(true);
      setProductsError(null);
      try {
        let res = await clientFetch("/products?limit=100");
        if (res.status === 401) {
          const refresh = await clientFetch("/auth/refresh", { method: "POST" });
          if (refresh.ok) {
            res = await clientFetch("/products?limit=100");
          }
        }
        if (cancelled) return;
        if (!res.ok) {
          if (res.status === 401) {
            setProductsError("Մուտքագրումն ավարտվել է — թարմացրեք էջը");
          } else {
            setProductsError(`Չհաջողվեց բեռնել ապրանքները (${res.status})`);
          }
          return;
        }
        const data = await res.json();
        const items: Product[] = Array.isArray(data?.items) ? data.items : [];
        if (!cancelled) setProducts(items);
      } catch {
        if (!cancelled) setProductsError("Կապի սխալ — փորձեք կրկին");
      } finally {
        if (!cancelled) setProductsLoading(false);
      }
    }

    loadProducts();
    return () => {
      cancelled = true;
    };
  }, [open, productsLoadId]);

  // Reset everything on close.
  useEffect(() => {
    if (!open) {
      setMode("single");
      setProductId("");
      setVariantId("");
      setQuantity("1");
      setBulkRows({});
      setCommonQty("10");
      setColorFilter("");
      setError(null);
    }
  }, [open]);

  const selectedProduct = products.find((p) => String(p.id) === productId);
  const variants = useMemo(
    () => selectedProduct?.variants ?? [],
    [selectedProduct],
  );

  // When the product changes (or mode flips to bulk), seed the bulk rows.
  useEffect(() => {
    if (!productId) {
      setBulkRows({});
      setColorFilter("");
      return;
    }
    setBulkRows((prev) => {
      const next: Record<number, BulkRowState> = {};
      for (const v of variants) {
        next[v.id] = prev[v.id] ?? { selected: false, qty: "10" };
      }
      return next;
    });
    setVariantId("");
  }, [productId, variants]);

  const colors = useMemo(
    () => Array.from(new Set(variants.map((v) => v.color))),
    [variants],
  );

  const selectedRows = useMemo(
    () => variants.filter((v) => bulkRows[v.id]?.selected),
    [variants, bulkRows],
  );
  const selectedCount = selectedRows.length;
  const totalQty = selectedRows.reduce(
    (sum, v) => sum + Math.max(0, Number(bulkRows[v.id]?.qty ?? 0) || 0),
    0,
  );

  const toggleRow = (variantIdNum: number) => {
    setBulkRows((prev) => ({
      ...prev,
      [variantIdNum]: {
        ...(prev[variantIdNum] ?? { qty: "10" }),
        selected: !(prev[variantIdNum]?.selected ?? false),
      },
    }));
  };

  const setRowQty = (variantIdNum: number, value: string) => {
    setBulkRows((prev) => ({
      ...prev,
      [variantIdNum]: {
        ...(prev[variantIdNum] ?? { selected: false }),
        qty: value,
      },
    }));
  };

  const applyCommonToSelected = () => {
    setBulkRows((prev) => {
      const next = { ...prev };
      for (const v of variants) {
        if (next[v.id]?.selected) {
          next[v.id] = { ...next[v.id], qty: commonQty };
        }
      }
      return next;
    });
  };

  const selectAllForColor = () => {
    if (!colorFilter) return;
    setBulkRows((prev) => {
      const next = { ...prev };
      for (const v of variants) {
        if (v.color === colorFilter) {
          next[v.id] = { ...(next[v.id] ?? { qty: commonQty }), selected: true };
        }
      }
      return next;
    });
  };

  const clearSelection = () => {
    setBulkRows((prev) => {
      const next: Record<number, BulkRowState> = {};
      for (const id of Object.keys(prev)) {
        next[Number(id)] = { ...prev[Number(id)], selected: false };
      }
      return next;
    });
  };

  const submitDisabled = (() => {
    if (busy) return true;
    if (!productId) return true;
    if (mode === "single") {
      const qty = Number(quantity);
      return !variantId || !qty || qty < 1;
    }
    if (selectedCount === 0) return true;
    if (selectedCount > MAX_BULK_ITEMS) return true;
    for (const v of selectedRows) {
      const qty = Number(bulkRows[v.id]?.qty ?? 0);
      if (!qty || qty < 1) return true;
    }
    return false;
  })();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    if (mode === "single") {
      const qty = Number(quantity);
      if (!productId || !variantId || !qty || qty < 1) {
        setError("Լրացրեք բոլոր դաշտերը");
        return;
      }
      setBusy(true);
      try {
        const res = await clientFetch("/production/batches", {
          method: "POST",
          body: JSON.stringify({
            product_id: Number(productId),
            variant_id: Number(variantId),
            quantity_to_produce: qty,
          }),
        });
        if (!res.ok) {
          const body = await res.json().catch(() => ({}));
          setError(body.detail || "Չհաջողվեց ստեղծել արտադրությունը");
          return;
        }
        showToast("Արտադրությունը ստեղծվեց", "success");
        onClose();
        router.refresh();
      } catch {
        setError("Կապի սխալ");
      } finally {
        setBusy(false);
      }
      return;
    }

    // Bulk mode
    if (selectedCount === 0) {
      setError("Ընտրեք առնվազն մեկ տարբերակ");
      return;
    }
    if (selectedCount > MAX_BULK_ITEMS) {
      setError(`Մեկ խմբով կարող է լինել առավելագույնը ${MAX_BULK_ITEMS} տարբերակ`);
      return;
    }
    const items = selectedRows.map((v) => ({
      variant_id: v.id,
      quantity_to_produce: Number(bulkRows[v.id]?.qty ?? 0),
    }));
    if (items.some((i) => !i.quantity_to_produce || i.quantity_to_produce < 1)) {
      setError("Բոլոր ընտրված տարբերակների քանակը պետք է լինի 1 կամ ավելի");
      return;
    }

    setBusy(true);
    try {
      const res = await clientFetch("/production/batches/bulk", {
        method: "POST",
        body: JSON.stringify({
          product_id: Number(productId),
          items,
        }),
      });
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        setError(body.detail || "Չհաջողվեց ստեղծել արտադրությունները");
        return;
      }
      showToast(`Ստեղծվեց ${items.length} արտադրություն`, "success");
      onClose();
      router.refresh();
    } catch {
      setError("Կապի սխալ");
    } finally {
      setBusy(false);
    }
  };

  return (
    <Modal open={open} onClose={onClose} title="Նոր արտադրություն">
      <form onSubmit={handleSubmit}>
        {error && (
          <div className="mb-4 px-3 py-2 bg-red-50 border border-red-200 rounded text-sm text-red-700 whitespace-pre-wrap">
            {error}
          </div>
        )}

        <div className="mb-4 inline-flex rounded-lg border border-gray-200 bg-gray-50 p-1 text-sm">
          <button
            type="button"
            className={`px-3 py-1 rounded-md ${
              mode === "single"
                ? "bg-white shadow-sm font-medium text-brand-700"
                : "text-gray-600 hover:text-gray-800"
            }`}
            onClick={() => setMode("single")}
            disabled={busy}
          >
            Մեկական
          </button>
          <button
            type="button"
            className={`px-3 py-1 rounded-md ${
              mode === "bulk"
                ? "bg-white shadow-sm font-medium text-brand-700"
                : "text-gray-600 hover:text-gray-800"
            }`}
            onClick={() => setMode("bulk")}
            disabled={busy}
          >
            Շարք
          </button>
        </div>

        <FormField label="Ապրանք" required>
          <Select
            value={productId}
            onChange={(e) => {
              setProductId(e.target.value);
              setVariantId("");
            }}
            required
            disabled={productsLoading || !!productsError}
          >
            <option value="">
              {productsLoading
                ? "Բեռնվում է…"
                : productsError
                  ? "Չհաջողվեց բեռնել"
                  : products.length === 0
                    ? "Ապրանքներ չեն գտնվել"
                    : "— Ընտրեք —"}
            </option>
            {products.map((p) => (
              <option key={p.id} value={String(p.id)}>
                {p.name} ({p.sku})
              </option>
            ))}
          </Select>
          {productsError && (
            <div className="mt-1 flex items-center gap-2 text-sm">
              <span className="text-red-600">{productsError}</span>
              <button
                type="button"
                className="text-brand-700 hover:underline"
                onClick={() => setProductsLoadId((n) => n + 1)}
              >
                Կրկին փորձել
              </button>
            </div>
          )}
        </FormField>

        {mode === "single" && (
          <>
            <FormField label="Տարբերակ / Չափս / Գույն" required>
              <Select
                value={variantId}
                onChange={(e) => setVariantId(e.target.value)}
                required
                disabled={!productId}
              >
                <option value="">— Ընտրեք —</option>
                {variants.map((v) => (
                  <option key={v.id} value={String(v.id)}>
                    {v.size} / {v.color}
                  </option>
                ))}
              </Select>
            </FormField>

            <FormField label="Քանակ" required>
              <Input
                type="number"
                min={1}
                value={quantity}
                onChange={(e) => setQuantity(e.target.value)}
                required
              />
            </FormField>

            <FormField label="Սկզբնական փուլ">
              <Input value={STAGE_LABELS.cutting} disabled readOnly />
            </FormField>

            <FormField label="Կարգավիճակ">
              <Input value={STATUS_LABELS.pending} disabled readOnly />
            </FormField>
          </>
        )}

        {mode === "bulk" && (
          <>
            {!productId && (
              <p className="mb-3 text-sm text-gray-500">
                Նախ ընտրեք ապրանք՝ տարբերակների ցուցակը տեսնելու համար։
              </p>
            )}

            {productId && variants.length === 0 && (
              <p className="mb-3 text-sm text-gray-500">
                Տվյալ ապրանքը չունի տարբերակներ։
              </p>
            )}

            {productId && variants.length > 0 && (
              <>
                <div className="mb-3 grid gap-2 sm:grid-cols-3">
                  <FormField label="Ընդհանուր քանակ">
                    <Input
                      type="number"
                      min={1}
                      value={commonQty}
                      onChange={(e) => setCommonQty(e.target.value)}
                    />
                  </FormField>
                  <div className="flex items-end">
                    <Button
                      type="button"
                      variant="secondary"
                      onClick={applyCommonToSelected}
                      disabled={selectedCount === 0}
                    >
                      Կիրառել ընտրվածներին
                    </Button>
                  </div>
                  <FormField label="Ընտրել ըստ գույնի">
                    <div className="flex gap-2">
                      <Select
                        value={colorFilter}
                        onChange={(e) => setColorFilter(e.target.value)}
                      >
                        <option value="">— Ընտրեք գույն —</option>
                        {colors.map((c) => (
                          <option key={c} value={c}>
                            {c}
                          </option>
                        ))}
                      </Select>
                      <Button
                        type="button"
                        variant="secondary"
                        onClick={selectAllForColor}
                        disabled={!colorFilter}
                      >
                        Ընտրել
                      </Button>
                    </div>
                  </FormField>
                </div>

                <div className="mb-2 flex items-center justify-between text-sm">
                  <span className="text-gray-600">
                    Ընտրված է՝ {selectedCount} տարբերակ · ընդհանուր քանակ՝ {totalQty}
                  </span>
                  <button
                    type="button"
                    className="text-brand-700 hover:underline"
                    onClick={clearSelection}
                    disabled={selectedCount === 0}
                  >
                    Չեղարկել ընտրությունը
                  </button>
                </div>

                <div className="mb-4 max-h-72 overflow-auto rounded-lg border border-gray-200">
                  <table className="min-w-full text-sm">
                    <thead className="bg-gray-50 text-xs uppercase text-gray-500">
                      <tr>
                        <th className="w-10 px-3 py-2 text-left"></th>
                        <th className="px-3 py-2 text-left">Չափս</th>
                        <th className="px-3 py-2 text-left">Գույն</th>
                        <th className="px-3 py-2 text-right">Մնացորդ</th>
                        <th className="w-32 px-3 py-2 text-left">Քանակ</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-200">
                      {variants.map((v) => {
                        const row = bulkRows[v.id] ?? { selected: false, qty: "10" };
                        return (
                          <tr key={v.id} className={row.selected ? "bg-brand-50/40" : ""}>
                            <td className="px-3 py-2 align-middle">
                              <input
                                type="checkbox"
                                checked={row.selected}
                                onChange={() => toggleRow(v.id)}
                                aria-label={`Ընտրել ${v.size} / ${v.color}`}
                              />
                            </td>
                            <td className="px-3 py-2 align-middle">{v.size}</td>
                            <td className="px-3 py-2 align-middle">{v.color}</td>
                            <td className="px-3 py-2 align-middle text-right text-gray-600">
                              {v.stock_quantity}
                            </td>
                            <td className="px-3 py-2 align-middle">
                              <Input
                                type="number"
                                min={1}
                                value={row.qty}
                                onChange={(e) => setRowQty(v.id, e.target.value)}
                                disabled={!row.selected}
                              />
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>

                {selectedCount > MAX_BULK_ITEMS && (
                  <div className="mb-2 text-sm text-red-600">
                    Մեկ խմբով կարող է լինել առավելագույնը {MAX_BULK_ITEMS} տարբերակ։
                  </div>
                )}
              </>
            )}
          </>
        )}

        <div className="flex justify-end gap-3 pt-2">
          <Button type="button" variant="secondary" onClick={onClose} disabled={busy}>
            Չեղարկել
          </Button>
          <Button type="submit" loading={busy} disabled={submitDisabled}>
            Ստեղծել
          </Button>
        </div>
      </form>
    </Modal>
  );
}
