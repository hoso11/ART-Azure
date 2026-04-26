"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Material } from "@/types";
import { Button } from "@/components/ui/Button";
import { FormField, Input, Textarea } from "@/components/ui/FormField";

export function EditMaterialForm({ material }: { material: Material }) {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [name, setName] = useState(material.name);
  const [sku, setSku] = useState(material.sku);
  const [unit, setUnit] = useState(material.unit);
  const [threshold, setThreshold] = useState(String(material.low_stock_threshold));
  const [description, setDescription] = useState(material.description || "");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

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
          low_stock_threshold: parseFloat(threshold),
          description: description || null,
        }),
      });
      if (!res.ok) {
        const data = await res.json();
        setError(data.detail || "Failed to update");
        return;
      }
      setOpen(false);
      router.refresh();
    } catch {
      setError("Connection error");
    } finally {
      setLoading(false);
    }
  };

  if (!open) {
    return (
      <Button size="sm" variant="secondary" onClick={() => setOpen(true)}>
        Edit
      </Button>
    );
  }

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
      <div className="bg-white rounded-lg shadow-lg p-6 w-full max-w-md">
        <h3 className="text-lg font-semibold mb-4">Խմբագրել նյութը</h3>
        {error && <p className="text-sm text-red-600 mb-3">{error}</p>}
        <form onSubmit={handleSubmit}>
          <FormField label="Անվանում" required>
            <Input value={name} onChange={(e) => setName(e.target.value)} required />
          </FormField>
          <FormField label="Արտիկուլ" required>
            <Input value={sku} onChange={(e) => setSku(e.target.value)} required />
          </FormField>
          <FormField label="Չափման" required>
            <Input value={unit} onChange={(e) => setUnit(e.target.value)} required />
          </FormField>
          <FormField label="Ցածր մնացորդի սահման">
            <Input type="number" step="0.001" min="0" value={threshold} onChange={(e) => setThreshold(e.target.value)} />
          </FormField>
          <FormField label="Նկարագրություն">
            <Textarea value={description} onChange={(e) => setDescription(e.target.value)} />
          </FormField>
          <div className="flex gap-2 mt-4">
            <Button type="submit" loading={loading}>Պահպանել</Button>
            <Button type="button" variant="secondary" onClick={() => setOpen(false)}>Չեղարկել</Button>
          </div>
        </form>
      </div>
    </div>
  );
}

export function DeleteMaterialButton({ materialId, materialName }: { materialId: number; materialName: string }) {
  const router = useRouter();
  const [confirming, setConfirming] = useState(false);
  const [loading, setLoading] = useState(false);

  const handleDelete = async () => {
    setLoading(true);
    try {
      const res = await fetch(`/api/v1/inventory/materials/${materialId}`, {
        method: "DELETE",
        credentials: "include",
      });
      if (res.ok || res.status === 204) {
        router.push("/dashboard/inventory");
        router.refresh();
      }
    } catch {
      // ignore
    } finally {
      setLoading(false);
    }
  };

  if (!confirming) {
    return (
      <Button size="sm" variant="secondary" onClick={() => setConfirming(true)}>
        Delete
      </Button>
    );
  }

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
      <div className="bg-white rounded-lg shadow-lg p-6 w-full max-w-sm">
        <h3 className="text-lg font-semibold mb-2">Ջնջել նյութը</h3>
        <p className="text-sm text-gray-600 mb-4">
          Are you sure you want to delete <strong>{materialName}</strong>? This cannot be undone.
        </p>
        <div className="flex gap-2">
          <Button onClick={handleDelete} loading={loading} className="bg-red-600 hover:bg-red-700">
            Delete
          </Button>
          <Button variant="secondary" onClick={() => setConfirming(false)}>Չեղարկել</Button>
        </div>
      </div>
    </div>
  );
}

export function AddStockMovement({ materialId }: { materialId: number }) {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [change, setChange] = useState("");
  const [reason, setReason] = useState("adjustment");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError("");
    try {
      const res = await fetch("/api/v1/inventory/movements", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({
          material_id: materialId,
          quantity_change: parseFloat(change),
          reason,
        }),
      });
      if (!res.ok) {
        const data = await res.json();
        setError(data.detail || "Failed to add movement");
        return;
      }
      setChange("");
      setReason("adjustment");
      setOpen(false);
      router.refresh();
    } catch {
      setError("Connection error");
    } finally {
      setLoading(false);
    }
  };

  if (!open) {
    return (
      <button
        type="button"
        onClick={() => setOpen(true)}
        className="text-xs font-medium text-brand-700 hover:text-brand-900"
      >
        + Add Movement
      </button>
    );
  }

  return (
    <form onSubmit={handleSubmit} className="bg-gray-50 border rounded-lg p-4 mb-4">
      <h4 className="text-sm font-semibold mb-3">Ավելացնել շարժ</h4>
      {error && <p className="text-xs text-red-600 mb-2">{error}</p>}
      <div className="grid grid-cols-2 gap-3">
        <FormField label="Փոփոխություն (+ մուտք, − ելք) − out)">
          <Input type="number" step="0.001" value={change} onChange={(e) => setChange(e.target.value)} required placeholder="e.g. 50 or -10" />
        </FormField>
        <FormField label="Պատճառ">
          <Input value={reason} onChange={(e) => setReason(e.target.value)} required />
        </FormField>
      </div>
      <div className="flex gap-2 mt-3">
        <Button type="submit" size="sm" loading={loading}>Ավելացնել</Button>
        <Button type="button" size="sm" variant="secondary" onClick={() => setOpen(false)}>Չեղարկել</Button>
      </div>
    </form>
  );
}
