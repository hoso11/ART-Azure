"use client";

import { useEffect, useMemo, useState } from "react";
import { ProductImage } from "@/types";

// Sort: primary first, then by id ascending. Stable across renders for the
// same images array (memoised on identity).
function sortPrimaryFirst(images: ProductImage[]): ProductImage[] {
  return [...images].sort((a, b) => {
    if (a.is_primary && !b.is_primary) return -1;
    if (!a.is_primary && b.is_primary) return 1;
    return a.id - b.id;
  });
}

export function ProductImageGallery({
  images,
  productName,
  mainHeightClass = "h-80",
}: {
  images: ProductImage[];
  productName: string;
  mainHeightClass?: string;
}) {
  const sorted = useMemo(() => sortPrimaryFirst(images), [images]);

  const [selectedIdx, setSelectedIdx] = useState(0);
  const [lightboxOpen, setLightboxOpen] = useState(false);

  // Reset selection if the underlying list changes (e.g. after upload).
  useEffect(() => {
    setSelectedIdx(0);
  }, [images]);

  // Surface missing URLs to the console — never silently hide images.
  useEffect(() => {
    sorted.forEach((img) => {
      if (!img.url) {
        // eslint-disable-next-line no-console
        console.warn(
          `[ProductImageGallery] image id=${img.id} has no URL ` +
            `(storage_key="${img.storage_key}", product_id=${img.product_id})`
        );
      }
    });
  }, [sorted]);

  // Keyboard navigation while the lightbox is open.
  useEffect(() => {
    if (!lightboxOpen || sorted.length === 0) return;
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape") setLightboxOpen(false);
      if (e.key === "ArrowLeft")
        setSelectedIdx((i) => (i - 1 + sorted.length) % sorted.length);
      if (e.key === "ArrowRight")
        setSelectedIdx((i) => (i + 1) % sorted.length);
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [lightboxOpen, sorted.length]);

  if (sorted.length === 0) {
    return (
      <div
        className={`bg-brand-50 rounded-lg flex items-center justify-center ${mainHeightClass}`}
      >
        <svg
          className="h-24 w-24 text-brand-200"
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={1}
            d="M20.25 7.5l-.625 10.632a2.25 2.25 0 01-2.247 2.118H6.622a2.25 2.25 0 01-2.247-2.118L3.75 7.5M10 11.25h4M3.375 7.5h17.25c.621 0 1.125-.504 1.125-1.125v-1.5c0-.621-.504-1.125-1.125-1.125H3.375c-.621 0-1.125.504-1.125 1.125v1.5c0 .621.504 1.125 1.125 1.125z"
          />
        </svg>
      </div>
    );
  }

  const selected = sorted[selectedIdx] ?? sorted[0];
  const canOpenLightbox = !!selected?.url;

  return (
    <>
      <div className="space-y-3">
        <div
          className={`bg-brand-50 rounded-lg flex items-center justify-center ${mainHeightClass} overflow-hidden relative ${
            canOpenLightbox ? "cursor-zoom-in group" : ""
          }`}
          onClick={() => {
            if (canOpenLightbox) setLightboxOpen(true);
          }}
          role={canOpenLightbox ? "button" : undefined}
          tabIndex={canOpenLightbox ? 0 : -1}
          onKeyDown={(e) => {
            if (canOpenLightbox && (e.key === "Enter" || e.key === " ")) {
              e.preventDefault();
              setLightboxOpen(true);
            }
          }}
          title={canOpenLightbox ? "Սեղմեք մեծացնելու համար" : undefined}
        >
          {selected?.url ? (
            <>
              <img
                src={selected.url}
                alt={productName}
                className="w-full h-full object-cover transition-transform group-hover:scale-105"
              />
              <div className="absolute inset-0 bg-black/0 group-hover:bg-black/10 transition" />
            </>
          ) : (
            <div className="flex flex-col items-center gap-2 text-gray-400 px-4 text-center">
              <svg
                className="h-16 w-16"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={1}
                  d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z"
                />
              </svg>
              <span className="text-xs">Նկարի հասցեն բացակայում է</span>
            </div>
          )}
        </div>

        {sorted.length > 1 && (
          <div className="flex gap-2 overflow-x-auto pb-1">
            {sorted.map((img, i) => (
              <button
                key={img.id}
                type="button"
                onClick={() => setSelectedIdx(i)}
                aria-label={
                  img.is_primary ? "Հիմնական նկար" : `Նկար ${i + 1}`
                }
                aria-current={i === selectedIdx ? "true" : undefined}
                className={`flex-shrink-0 w-16 h-16 rounded border overflow-hidden bg-gray-100 relative ${
                  i === selectedIdx
                    ? "ring-2 ring-brand-500 border-brand-500"
                    : "border-gray-200 hover:border-gray-400"
                }`}
                title={img.is_primary ? "Հիմնական" : `Նկար ${i + 1}`}
              >
                {img.url ? (
                  <img
                    src={img.url}
                    alt=""
                    className="w-full h-full object-cover"
                  />
                ) : (
                  <div className="w-full h-full flex items-center justify-center">
                    <svg
                      className="h-5 w-5 text-gray-300"
                      fill="none"
                      viewBox="0 0 24 24"
                      stroke="currentColor"
                    >
                      <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        strokeWidth={1.5}
                        d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z"
                      />
                    </svg>
                  </div>
                )}
                {img.is_primary && (
                  <span className="absolute top-0.5 left-0.5 text-[9px] bg-brand-800 text-white px-1 py-0.5 rounded leading-none">
                    ★
                  </span>
                )}
              </button>
            ))}
          </div>
        )}
      </div>

      {lightboxOpen && selected?.url && (
        <div
          className="fixed inset-0 z-50 bg-black/85 flex items-center justify-center p-4"
          onClick={() => setLightboxOpen(false)}
          role="dialog"
          aria-modal="true"
          aria-label={productName}
        >
          <button
            type="button"
            onClick={(e) => {
              e.stopPropagation();
              setLightboxOpen(false);
            }}
            className="absolute top-4 right-4 text-white/90 hover:text-white text-3xl leading-none w-10 h-10 flex items-center justify-center rounded-full hover:bg-white/10"
            aria-label="Փակել"
          >
            ×
          </button>

          {sorted.length > 1 && (
            <>
              <button
                type="button"
                onClick={(e) => {
                  e.stopPropagation();
                  setSelectedIdx(
                    (i) => (i - 1 + sorted.length) % sorted.length,
                  );
                }}
                className="absolute left-4 top-1/2 -translate-y-1/2 text-white/90 hover:text-white text-4xl w-12 h-12 flex items-center justify-center rounded-full hover:bg-white/10"
                aria-label="Նախորդ"
              >
                ‹
              </button>
              <button
                type="button"
                onClick={(e) => {
                  e.stopPropagation();
                  setSelectedIdx((i) => (i + 1) % sorted.length);
                }}
                className="absolute right-4 top-1/2 -translate-y-1/2 text-white/90 hover:text-white text-4xl w-12 h-12 flex items-center justify-center rounded-full hover:bg-white/10"
                aria-label="Հաջորդ"
              >
                ›
              </button>
            </>
          )}

          <img
            src={selected.url}
            alt={productName}
            onClick={(e) => e.stopPropagation()}
            className="max-w-full max-h-[90vh] object-contain"
          />

          {sorted.length > 1 && (
            <div className="absolute bottom-4 left-0 right-0 text-center text-white/80 text-sm">
              {selectedIdx + 1} / {sorted.length}
            </div>
          )}
        </div>
      )}
    </>
  );
}
