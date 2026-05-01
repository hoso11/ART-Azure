"use client";

import { useEffect, useMemo, useState } from "react";
import { ProductImage } from "@/types";

function sortPrimaryFirst(images: ProductImage[]): ProductImage[] {
  return [...images].sort((a, b) => {
    if (a.is_primary && !b.is_primary) return -1;
    if (!a.is_primary && b.is_primary) return 1;
    return a.id - b.id;
  });
}

function PlaceholderIcon() {
  return (
    <svg
      className="h-16 w-16 text-brand-200"
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
  );
}

/**
 * Card-sized clickable product image with a built-in fullscreen lightbox.
 * Clicking opens a modal that supports prev/next, thumbnails, and keyboard
 * (Esc / ← / →). When the card itself is wrapped in a <Link>, click events
 * are stopped so navigation doesn't fire.
 */
export function ProductCardImage({
  images,
  productName,
  containerClassName = "h-48 bg-brand-50 flex items-center justify-center",
}: {
  images: ProductImage[];
  productName: string;
  containerClassName?: string;
}) {
  const sorted = useMemo(() => sortPrimaryFirst(images), [images]);
  const primary = sorted[0];

  const [open, setOpen] = useState(false);
  const [idx, setIdx] = useState(0);

  useEffect(() => {
    if (!open || sorted.length === 0) return;
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape") setOpen(false);
      if (e.key === "ArrowLeft")
        setIdx((i) => (i - 1 + sorted.length) % sorted.length);
      if (e.key === "ArrowRight") setIdx((i) => (i + 1) % sorted.length);
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [open, sorted.length]);

  // No image at all → render the placeholder icon, NOT clickable.
  if (!primary?.url) {
    return (
      <div className={containerClassName}>
        <PlaceholderIcon />
      </div>
    );
  }

  const openLightbox = (e: React.MouseEvent | React.KeyboardEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIdx(0);
    setOpen(true);
  };

  const selected = sorted[idx] ?? sorted[0];

  return (
    <>
      <div
        className={`${containerClassName} cursor-zoom-in group overflow-hidden relative`}
        onClick={openLightbox}
        role="button"
        tabIndex={0}
        onKeyDown={(e) => {
          if (e.key === "Enter" || e.key === " ") openLightbox(e);
        }}
        title="Սեղմեք մեծացնելու համար"
        aria-label={`${productName} — բացել նկարը`}
      >
        <img
          src={primary.url}
          alt={productName}
          className="w-full h-full object-cover transition-transform group-hover:scale-105"
        />
        <div className="absolute inset-0 bg-black/0 group-hover:bg-black/10 transition" />
        {sorted.length > 1 && (
          <span className="absolute bottom-1 right-1 bg-black/60 text-white text-[10px] px-1.5 py-0.5 rounded leading-none">
            +{sorted.length - 1}
          </span>
        )}
      </div>

      {open && (
        <div
          className="fixed inset-0 z-50 bg-black/85 flex items-center justify-center p-4"
          onClick={(e) => {
            // Click on the dark backdrop closes; click on the card link
            // underneath must not fire either.
            e.preventDefault();
            e.stopPropagation();
            setOpen(false);
          }}
          role="dialog"
          aria-modal="true"
          aria-label={productName}
        >
          <button
            type="button"
            onClick={(e) => {
              e.preventDefault();
              e.stopPropagation();
              setOpen(false);
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
                  e.preventDefault();
                  e.stopPropagation();
                  setIdx((i) => (i - 1 + sorted.length) % sorted.length);
                }}
                className="absolute left-4 top-1/2 -translate-y-1/2 text-white/90 hover:text-white text-4xl w-12 h-12 flex items-center justify-center rounded-full hover:bg-white/10"
                aria-label="Նախորդ"
              >
                ‹
              </button>
              <button
                type="button"
                onClick={(e) => {
                  e.preventDefault();
                  e.stopPropagation();
                  setIdx((i) => (i + 1) % sorted.length);
                }}
                className="absolute right-4 top-1/2 -translate-y-1/2 text-white/90 hover:text-white text-4xl w-12 h-12 flex items-center justify-center rounded-full hover:bg-white/10"
                aria-label="Հաջորդ"
              >
                ›
              </button>
            </>
          )}

          {selected?.url && (
            <img
              src={selected.url}
              alt={productName}
              onClick={(e) => {
                e.preventDefault();
                e.stopPropagation();
              }}
              className="max-w-full max-h-[80vh] object-contain"
            />
          )}

          {sorted.length > 1 && (
            <>
              <div
                className="absolute bottom-16 left-0 right-0 flex justify-center gap-2 px-4 overflow-x-auto"
                onClick={(e) => e.stopPropagation()}
              >
                {sorted.map((img, i) => (
                  <button
                    key={img.id}
                    type="button"
                    onClick={(e) => {
                      e.preventDefault();
                      e.stopPropagation();
                      setIdx(i);
                    }}
                    aria-label={
                      img.is_primary ? "Հիմնական նկար" : `Նկար ${i + 1}`
                    }
                    aria-current={i === idx ? "true" : undefined}
                    className={`flex-shrink-0 w-14 h-14 rounded border overflow-hidden bg-gray-800 ${
                      i === idx
                        ? "ring-2 ring-white border-white"
                        : "border-white/30 hover:border-white/70"
                    }`}
                  >
                    {img.url && (
                      <img
                        src={img.url}
                        alt=""
                        className="w-full h-full object-cover"
                      />
                    )}
                  </button>
                ))}
              </div>
              <div className="absolute bottom-4 left-0 right-0 text-center text-white/80 text-sm">
                {idx + 1} / {sorted.length}
              </div>
            </>
          )}
        </div>
      )}
    </>
  );
}
