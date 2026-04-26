"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/Button";
import { Modal } from "@/components/ui/Modal";
import { FormField, Input, Select, Textarea } from "@/components/ui/FormField";
import { ProductCategory } from "@/types";

interface CreateProductModalProps {
  categories: ProductCategory[];
}

interface DeleteProductButtonProps {
  productId: number;
  productName: string;
}

export function DeleteProductButton({ productId, productName }: DeleteProductButtonProps) {
  const router = useRouter();
  const [loading, setLoading] = useState(false);
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [error, setError] = useState("");

  const handleDelete = async () => {
    setError("");
    setLoading(true);

    try {
      const res = await fetch(`/api/v1/products/${productId}`, {
        method: "DELETE",
        credentials: "include",
      });

      if (!res.ok && res.status !== 204) {
        const data = await res.json();
        setError(data.detail || "Failed to delete product");
        return;
      }

      setConfirmOpen(false);
      router.push("/dashboard/products");
      router.refresh();
    } catch {
      setError("Connection error");
    } finally {
      setLoading(false);
    }
  };

  return (
    <>
      <Button variant="danger" onClick={() => setConfirmOpen(true)}>
        Delete
      </Button>

      <Modal open={confirmOpen} onClose={() => setConfirmOpen(false)} title="Ջնջել ապրանքը">
        {error && (
          <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700">
            {error}
          </div>
        )}
        <p className="text-sm text-gray-600 mb-6">
          Are you sure you want to delete <strong>{productName}</strong>? This action cannot be undone.
        </p>
        <div className="flex justify-end gap-3">
          <Button type="button" variant="secondary" onClick={() => setConfirmOpen(false)}>
            Cancel
          </Button>
          <Button variant="danger" onClick={handleDelete} loading={loading}>
            Delete Product
          </Button>
        </div>
      </Modal>
    </>
  );
}

export function CreateProductButton({ categories }: CreateProductModalProps) {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const [name, setName] = useState("");
  const [sku, setSku] = useState("");
  const [categoryId, setCategoryId] = useState("");
  const [description, setDescription] = useState("");
  const [technicalNotes, setTechnicalNotes] = useState("");

  const resetForm = () => {
    setName("");
    setSku("");
    setCategoryId("");
    setDescription("");
    setTechnicalNotes("");
    setError("");
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);

    try {
      const res = await fetch("/api/v1/products", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({
          name,
          sku,
          category_id: categoryId ? parseInt(categoryId) : null,
          description: description || null,
          technical_notes: technicalNotes || null,
          variants: [],
        }),
      });

      if (!res.ok) {
        const data = await res.json();
        setError(data.detail || "Failed to create product");
        return;
      }

      const product = await res.json();
      setOpen(false);
      resetForm();
      router.push(`/dashboard/products/${product.id}`);
      router.refresh();
    } catch {
      setError("Connection error");
    } finally {
      setLoading(false);
    }
  };

  return (
    <>
      <Button onClick={() => setOpen(true)}>Ավելացնել ապրանք</Button>

      <Modal open={open} onClose={() => { setOpen(false); resetForm(); }} title="Ավելացնել ապրանք">
        <form onSubmit={handleSubmit}>
          {error && (
            <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700">
              {error}
            </div>
          )}

          <FormField label="Անվանում" required>
            <Input value={name} onChange={(e) => setName(e.target.value)} placeholder="e.g. Classic Oxford Shirt" required />
          </FormField>

          <FormField label="Արտիկուլ" required>
            <Input value={sku} onChange={(e) => setSku(e.target.value)} placeholder="e.g. PRD-OXF-001" required />
          </FormField>

          <FormField label="Կատեգորիա">
            <Select value={categoryId} onChange={(e) => setCategoryId(e.target.value)}>
              <option value="">Առանց կատեգորիա</option>
              {categories.map((c) => (
                <option key={c.id} value={c.id}>{c.name}</option>
              ))}
            </Select>
          </FormField>

          <FormField label="Նկարագրություն">
            <Textarea value={description} onChange={(e) => setDescription(e.target.value)} placeholder="Product description..." />
          </FormField>

          <FormField label="Տեխնիկական նշումներ">
            <Textarea value={technicalNotes} onChange={(e) => setTechnicalNotes(e.target.value)} placeholder="Manufacturing specs, fabric details..." />
          </FormField>

          <div className="flex justify-end gap-3 mt-6">
            <Button type="button" variant="secondary" onClick={() => { setOpen(false); resetForm(); }}>
              Cancel
            </Button>
            <Button type="submit" loading={loading}>
              Create Product
            </Button>
          </div>
        </form>
      </Modal>
    </>
  );
}
