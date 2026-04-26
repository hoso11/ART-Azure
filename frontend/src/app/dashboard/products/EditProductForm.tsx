"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/Button";
import { Modal } from "@/components/ui/Modal";
import { FormField, Input, Select, Textarea } from "@/components/ui/FormField";
import { Product, ProductCategory } from "@/types";

interface EditProductFormProps {
  product: Product;
  categories: ProductCategory[];
}

export function EditProductForm({ product, categories }: EditProductFormProps) {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const [name, setName] = useState(product.name);
  const [sku, setSku] = useState(product.sku);
  const [categoryId, setCategoryId] = useState(
    product.category_id?.toString() || ""
  );
  const [description, setDescription] = useState(product.description || "");
  const [technicalNotes, setTechnicalNotes] = useState(
    product.technical_notes || ""
  );
  const [isActive, setIsActive] = useState(product.is_active);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);

    try {
      const res = await fetch(`/api/v1/products/${product.id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({
          name,
          sku,
          category_id: categoryId ? parseInt(categoryId) : null,
          description: description || null,
          technical_notes: technicalNotes || null,
          is_active: isActive,
        }),
      });

      if (!res.ok) {
        const data = await res.json();
        setError(data.detail || "Failed to update product");
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

  return (
    <>
      <Button variant="secondary" onClick={() => setOpen(true)}>
        Edit Product
      </Button>

      <Modal
        open={open}
        onClose={() => setOpen(false)}
        title="Խմբագրել ապրանքը"
      >
        <form onSubmit={handleSubmit}>
          {error && (
            <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700">
              {error}
            </div>
          )}

          <FormField label="Անվանում" required>
            <Input
              value={name}
              onChange={(e) => setName(e.target.value)}
              required
            />
          </FormField>

          <FormField label="Արտիկուլ" required>
            <Input
              value={sku}
              onChange={(e) => setSku(e.target.value)}
              required
            />
          </FormField>

          <FormField label="Կատեգորիա">
            <Select
              value={categoryId}
              onChange={(e) => setCategoryId(e.target.value)}
            >
              <option value="">Առանց կատեգորիա</option>
              {categories.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name}
                </option>
              ))}
            </Select>
          </FormField>

          <FormField label="Նկարագրություն">
            <Textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
            />
          </FormField>

          <FormField label="Տեխնիկական նշումներ">
            <Textarea
              value={technicalNotes}
              onChange={(e) => setTechnicalNotes(e.target.value)}
            />
          </FormField>

          <FormField label="Կարգավիճակ">
            <Select
              value={isActive ? "active" : "inactive"}
              onChange={(e) => setIsActive(e.target.value === "active")}
            >
              <option value="active">Ակտիվ</option>
              <option value="inactive">Անակտիվ</option>
            </Select>
          </FormField>

          <div className="flex justify-end gap-3 mt-6">
            <Button
              type="button"
              variant="secondary"
              onClick={() => setOpen(false)}
            >
              Cancel
            </Button>
            <Button type="submit" loading={loading}>
              Save Changes
            </Button>
          </div>
        </form>
      </Modal>
    </>
  );
}
