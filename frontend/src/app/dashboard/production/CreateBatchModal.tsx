"use client";

import { useEffect, useState } from "react";
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
  const [productId, setProductId] = useState<string>("");
  const [variantId, setVariantId] = useState<string>("");
  const [quantity, setQuantity] = useState<string>("1");
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
          // Access token may have expired since the page rendered. Try a
          // single silent refresh — the refresh_token cookie is scoped to
          // /api/v1/auth/refresh and is httpOnly, so the browser handles it.
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

  useEffect(() => {
    if (!open) {
      setProductId("");
      setVariantId("");
      setQuantity("1");
      setError(null);
    }
  }, [open]);

  const selectedProduct = products.find((p) => String(p.id) === productId);
  const variants = selectedProduct?.variants ?? [];

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

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
  };

  return (
    <Modal open={open} onClose={onClose} title="Նոր արտադրություն">
      <form onSubmit={handleSubmit}>
        {error && (
          <div className="mb-4 px-3 py-2 bg-red-50 border border-red-200 rounded text-sm text-red-700 whitespace-pre-wrap">
            {error}
          </div>
        )}

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

        <div className="flex justify-end gap-3 pt-2">
          <Button type="button" variant="secondary" onClick={onClose} disabled={busy}>
            Չեղարկել
          </Button>
          <Button type="submit" loading={busy}>
            Ստեղծել
          </Button>
        </div>
      </form>
    </Modal>
  );
}
