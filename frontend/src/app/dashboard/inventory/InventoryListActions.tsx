"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { Material } from "@/types";
import { Button } from "@/components/ui/Button";
import { FormField, Input, Textarea } from "@/components/ui/FormField";

export function AddMaterialButton() {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [name, setName] = useState("");
  const [sku, setSku] = useState("");
  const [unit, setUnit] = useState("");
  const [qty, setQty] = useState("0");
  const [threshold, setThreshold] = useState("0");
  const [description, setDescription] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const reset = () => {
    setName(""); setSku(""); setUnit(""); setQty("0"); setThreshold("0"); setDescription(""); setError("");
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError("");
    try {
      const res = await fetch("/api/v1/inventory/materials", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({
          name,
          sku,
          unit,
          quantity_on_hand: parseFloat(qty) || 0,
          low_stock_threshold: parseFloat(threshold) || 0,
          description: description || null,
        }),
      });
      if (!res.ok) {
        const data = await res.json();
        setError(data.detail || "Չհաջողվեց ստեղծել");
        return;
      }
      reset();
      setOpen(false);
      router.refresh();
    } catch {
      setError("Կապի սխալ");
    } finally {
      setLoading(false);
    }
  };

  return (
    <>
      <Button onClick={() => setOpen(true)}>+ Ավելացնել նյութ</Button>
      {open && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg shadow-lg p-6 w-full max-w-md">
            <h3 className="text-lg font-semibold mb-4">Ավելացնել նյութ</h3>
            {error && <p className="text-sm text-red-600 mb-3">{error}</p>}
            <form onSubmit={handleSubmit}>
              <FormField label="Նյութի անվանում" required>
                <Input value={name} onChange={(e) => setName(e.target.value)} required />
              </FormField>
              <FormField label="Արտիկուլ" required>
                <Input value={sku} onChange={(e) => setSku(e.target.value)} required />
              </FormField>
              <FormField label="Չափման միավոր" required>
                <Input value={unit} onChange={(e) => setUnit(e.target.value)} required />
              </FormField>
              <FormField label="Առկա քանակ">
                <Input type="number" step="0.001" min="0" value={qty} onChange={(e) => setQty(e.target.value)} />
              </FormField>
              <FormField label="Մինիմալ քանակ">
                <Input type="number" step="0.001" min="0" value={threshold} onChange={(e) => setThreshold(e.target.value)} />
              </FormField>
              <FormField label="Նկարագրություն">
                <Textarea value={description} onChange={(e) => setDescription(e.target.value)} rows={2} />
              </FormField>
              <div className="flex gap-2 mt-4">
                <Button type="submit" loading={loading}>Ավելացնել</Button>
                <Button type="button" variant="secondary" onClick={() => { setOpen(false); reset(); }}>Չեղարկել</Button>
              </div>
            </form>
          </div>
        </div>
      )}
    </>
  );
}

export function EditMaterialButton({ material }: { material: Material }) {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [name, setName] = useState(material.name);
  const [sku, setSku] = useState(material.sku);
  const [unit, setUnit] = useState(material.unit);
  const [qty, setQty] = useState(String(material.inventory?.quantity_on_hand ?? 0));
  const [threshold, setThreshold] = useState(String(material.low_stock_threshold));
  const [description, setDescription] = useState(material.description || "");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (open) {
      setName(material.name);
      setSku(material.sku);
      setUnit(material.unit);
      setQty(String(material.inventory?.quantity_on_hand ?? 0));
      setThreshold(String(material.low_stock_threshold));
      setDescription(material.description || "");
      setError("");
    }
  }, [open, material]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError("");
    try {
      const res = await fetch(`/api/v1/inventory/materials/${material.id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({
          name,
          sku,
          unit,
          quantity_on_hand: parseFloat(qty) || 0,
          low_stock_threshold: parseFloat(threshold) || 0,
          description: description || null,
        }),
      });
      if (!res.ok) {
        const data = await res.json();
        setError(data.detail || "Չհաջողվեց թարմացնել");
        return;
      }
      setOpen(false);
      router.refresh();
    } catch {
      setError("Կապի սխալ");
    } finally {
      setLoading(false);
    }
  };

  return (
    <>
      <button
        type="button"
        onClick={() => setOpen(true)}
        className="text-brand-700 hover:text-brand-900 text-sm font-medium"
      >
        Խմբ.
      </button>
      {open && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg shadow-lg p-6 w-full max-w-md">
            <h3 className="text-lg font-semibold mb-4">Խմբագրել նյութը</h3>
            {error && <p className="text-sm text-red-600 mb-3">{error}</p>}
            <form onSubmit={handleSubmit}>
              <FormField label="Նյութի անվանում" required>
                <Input value={name} onChange={(e) => setName(e.target.value)} required />
              </FormField>
              <FormField label="Արտիկուլ" required>
                <Input value={sku} onChange={(e) => setSku(e.target.value)} required />
              </FormField>
              <FormField label="Չափման միավոր" required>
                <Input value={unit} onChange={(e) => setUnit(e.target.value)} required />
              </FormField>
              <FormField label="Առկա քանակ">
                <Input type="number" step="0.001" min="0" value={qty} onChange={(e) => setQty(e.target.value)} />
              </FormField>
              <FormField label="Մինիմալ քանակ">
                <Input type="number" step="0.001" min="0" value={threshold} onChange={(e) => setThreshold(e.target.value)} />
              </FormField>
              <FormField label="Նկարագրություն">
                <Textarea value={description} onChange={(e) => setDescription(e.target.value)} rows={2} />
              </FormField>
              <div className="flex gap-2 mt-4">
                <Button type="submit" loading={loading}>Պահպանել</Button>
                <Button type="button" variant="secondary" onClick={() => setOpen(false)}>Չեղարկել</Button>
              </div>
            </form>
          </div>
        </div>
      )}
    </>
  );
}

export function DeleteMaterialButton({ materialId, materialName }: { materialId: number; materialName: string }) {
  const router = useRouter();
  const [confirming, setConfirming] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const handleDelete = async () => {
    setLoading(true);
    setError("");
    try {
      const res = await fetch(`/api/v1/inventory/materials/${materialId}`, {
        method: "DELETE",
        credentials: "include",
      });
      if (res.status === 204 || res.ok) {
        setConfirming(false);
        router.refresh();
      } else {
        const data = await res.json();
        setError(data.detail || "Չհաջողվեց ջնջել");
      }
    } catch {
      setError("Կապի սխալ");
    } finally {
      setLoading(false);
    }
  };

  return (
    <>
      <button
        type="button"
        onClick={() => setConfirming(true)}
        className="text-red-600 hover:text-red-800 text-sm font-medium"
      >
        Ջնջ.
      </button>
      {confirming && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg shadow-lg p-6 w-full max-w-sm">
            <h3 className="text-lg font-semibold mb-2">Ջնջե՞լ նյութը</h3>
            <p className="text-sm text-gray-600 mb-4">
              Ջնջե՞լ <strong>{materialName}</strong>: Հնարավոր չի վերականգնել:
            </p>
            {error && <p className="text-sm text-red-600 mb-3">{error}</p>}
            <div className="flex gap-2">
              <Button
                onClick={handleDelete}
                loading={loading}
                className="bg-red-600 hover:bg-red-700 text-white"
              >
                Ջնջել
              </Button>
              <Button
                variant="secondary"
                onClick={() => { setConfirming(false); setError(""); }}
              >
                Չեղարկել
              </Button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
