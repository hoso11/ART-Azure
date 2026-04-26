"use client";

import { useState, useRef } from "react";
import { useRouter } from "next/navigation";
import { ImageUpload } from "@/components/ui/ImageUpload";
import { Button } from "@/components/ui/Button";
import { Modal } from "@/components/ui/Modal";
import { ProductImage } from "@/types";

interface ProductImageUploadProps {
  productId: number;
  images: ProductImage[];
}

export function ProductImageUpload({
  productId,
  images,
}: ProductImageUploadProps) {
  const router = useRouter();
  const [error, setError] = useState("");
  const [deleting, setDeleting] = useState<number | null>(null);
  const [settingPrimary, setSettingPrimary] = useState<number | null>(null);
  const [deleteConfirm, setDeleteConfirm] = useState<ProductImage | null>(null);
  const [replacingId, setReplacingId] = useState<number | null>(null);
  const replaceInputRef = useRef<HTMLInputElement>(null);

  const handleUpload = async (file: File) => {
    setError("");
    const formData = new FormData();
    formData.append("file", file);

    try {
      const res = await fetch(
        `/api/v1/products/${productId}/images?is_primary=${images.length === 0}`,
        {
          method: "POST",
          credentials: "include",
          body: formData,
        }
      );

      if (!res.ok) {
        const data = await res.json();
        setError(data.detail || "Failed to upload image");
        return;
      }

      router.refresh();
    } catch {
      setError("Connection error");
    }
  };

  const handleDelete = async () => {
    if (!deleteConfirm) return;
    setError("");
    setDeleting(deleteConfirm.id);

    try {
      const res = await fetch(`/api/v1/products/images/${deleteConfirm.id}`, {
        method: "DELETE",
        credentials: "include",
      });

      if (!res.ok && res.status !== 204) {
        const data = await res.json();
        setError(data.detail || "Failed to delete image");
        return;
      }

      setDeleteConfirm(null);
      router.refresh();
    } catch {
      setError("Connection error");
    } finally {
      setDeleting(null);
    }
  };

  const handleReplace = async (file: File, imageId: number) => {
    setError("");
    setReplacingId(imageId);

    // Delete old image first
    try {
      const delRes = await fetch(`/api/v1/products/images/${imageId}`, {
        method: "DELETE",
        credentials: "include",
      });

      if (!delRes.ok && delRes.status !== 204) {
        const data = await delRes.json();
        setError(data.detail || "Failed to replace image");
        setReplacingId(null);
        return;
      }
    } catch {
      setError("Connection error");
      setReplacingId(null);
      return;
    }

    // Upload new image
    const formData = new FormData();
    formData.append("file", file);

    try {
      const res = await fetch(
        `/api/v1/products/${productId}/images?is_primary=true`,
        {
          method: "POST",
          credentials: "include",
          body: formData,
        }
      );

      if (!res.ok) {
        const data = await res.json();
        setError(data.detail || "Failed to upload replacement image");
        return;
      }

      router.refresh();
    } catch {
      setError("Connection error");
    } finally {
      setReplacingId(null);
    }
  };

  const handleSetPrimary = async (imageId: number) => {
    setError("");
    setSettingPrimary(imageId);

    try {
      const res = await fetch(`/api/v1/products/images/${imageId}/primary`, {
        method: "PATCH",
        credentials: "include",
      });

      if (!res.ok) {
        const data = await res.json();
        setError(data.detail || "Failed to set primary image");
        return;
      }

      router.refresh();
    } catch {
      setError("Connection error");
    } finally {
      setSettingPrimary(null);
    }
  };

  const getImageUrl = (image: ProductImage) => {
    return image.url || "";
  };

  return (
    <div>
      {error && (
        <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700">
          {error}
        </div>
      )}

      {images.length > 0 && (
        <div className="grid grid-cols-2 sm:grid-cols-3 gap-3 mb-4">
          {images.map((image) => (
            <div key={image.id} className="relative group border rounded-lg overflow-hidden">
              {getImageUrl(image) ? (
                <img
                  src={getImageUrl(image)}
                  alt="Product"
                  className="w-full h-32 object-cover"
                />
              ) : (
                <div className="w-full h-32 bg-gray-100 flex items-center justify-center">
                  <svg className="h-8 w-8 text-gray-300" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
                  </svg>
                </div>
              )}

              {image.is_primary && (
                <span className="absolute top-1 left-1 text-xs bg-brand-800 text-white px-2 py-0.5 rounded">
                  Primary
                </span>
              )}

              {/* Action overlay */}
              <div className="absolute inset-0 bg-black/0 group-hover:bg-black/40 transition-all flex items-center justify-center gap-1.5 opacity-0 group-hover:opacity-100">
                {/* Replace button */}
                <button
                  onClick={() => {
                    setReplacingId(image.id);
                    replaceInputRef.current?.click();
                  }}
                  disabled={replacingId === image.id}
                  className="bg-white text-gray-700 rounded-full w-8 h-8 flex items-center justify-center text-sm hover:bg-gray-100 disabled:opacity-50"
                  title="Խմբագրել նկարը"
                >
                  <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-8l-4-4m0 0L8 8m4-4v12" />
                  </svg>
                </button>

                {/* Delete button */}
                <button
                  onClick={() => setDeleteConfirm(image)}
                  disabled={deleting === image.id}
                  className="bg-red-600 text-white rounded-full w-8 h-8 flex items-center justify-center text-sm hover:bg-red-700 disabled:opacity-50"
                  title="Ջնջել նկարը"
                >
                  <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                  </svg>
                </button>

                {/* Set as primary button (only for non-primary images) */}
                {!image.is_primary && (
                  <button
                    onClick={() => handleSetPrimary(image.id)}
                    disabled={settingPrimary === image.id}
                    className="bg-brand-800 text-white rounded-full w-8 h-8 flex items-center justify-center text-sm hover:bg-brand-900 disabled:opacity-50"
                    title="Հիմնական"
                  >
                    <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11.049 2.927c.3-.921 1.603-.921 1.902 0l1.519 4.674a1 1 0 00.95.69h4.915c.969 0 1.371 1.24.588 1.81l-3.976 2.888a1 1 0 00-.363 1.118l1.518 4.674c.3.922-.755 1.688-1.538 1.118l-3.976-2.888a1 1 0 00-1.176 0l-3.976 2.888c-.783.57-1.838-.197-1.538-1.118l1.518-4.674a1 1 0 00-.363-1.118l-3.976-2.888c-.784-.57-.38-1.81.588-1.81h4.914a1 1 0 00.951-.69l1.519-4.674z" />
                    </svg>
                  </button>
                )}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Hidden input for replace action */}
      <input
        ref={replaceInputRef}
        type="file"
        accept="image/jpeg,image/png,image/webp"
        className="hidden"
        onChange={(e) => {
          const file = e.target.files?.[0];
          if (file && replacingId) {
            handleReplace(file, replacingId);
          }
          e.target.value = "";
        }}
      />

      <ImageUpload
        onUpload={handleUpload}
        accept="image/jpeg,image/png,image/webp"
      />
      <p className="text-xs text-gray-400 mt-2">
        Max 5MB. Accepted: JPEG, PNG, WebP.
      </p>

      {/* Delete confirmation modal */}
      <Modal
        open={!!deleteConfirm}
        onClose={() => setDeleteConfirm(null)}
        title="Ջնջել նկարը"
      >
        <p className="text-sm text-gray-600 mb-6">
          Are you sure you want to remove this image? This cannot be undone.
        </p>
        <div className="flex justify-end gap-3">
          <Button
            type="button"
            variant="secondary"
            onClick={() => setDeleteConfirm(null)}
          >
            Cancel
          </Button>
          <Button
            variant="danger"
            onClick={handleDelete}
            loading={deleting === deleteConfirm?.id}
          >
            Delete Image
          </Button>
        </div>
      </Modal>
    </div>
  );
}
