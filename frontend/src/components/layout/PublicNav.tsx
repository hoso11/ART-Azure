"use client";

import Link from "next/link";
import { useState } from "react";

export function PublicNav() {
  const [open, setOpen] = useState(false);

  const close = () => setOpen(false);

  return (
    <nav className="bg-white border-b border-gray-200 sticky top-0 z-40">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 py-4 flex items-center justify-between gap-4">
        <Link href="/" className="text-xl font-bold text-brand-900 tracking-tight" onClick={close}>
          ART Արտադրություն
        </Link>

        <div className="hidden md:flex items-center gap-6">
          <Link href="/#products" className="text-sm text-gray-600 hover:text-brand-800">
            Ապրանքներ
          </Link>
          <Link href="/#about" className="text-sm text-gray-600 hover:text-brand-800">
            Մեր մասին
          </Link>
          <Link href="/#contact" className="text-sm text-gray-600 hover:text-brand-800">
            Կապ
          </Link>
          <Link
            href="/login"
            className="px-4 py-2 text-sm font-medium bg-brand-800 text-white rounded-lg hover:bg-brand-900 transition-colors"
          >
            Մուտք հաճախորդների համար
          </Link>
        </div>

        <button
          type="button"
          aria-label={open ? "Close menu" : "Open menu"}
          aria-expanded={open}
          onClick={() => setOpen((v) => !v)}
          className="md:hidden inline-flex items-center justify-center h-10 w-10 -mr-2 rounded-md text-gray-700 hover:bg-gray-100 focus:outline-none focus:ring-2 focus:ring-brand-500"
        >
          <svg className="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            {open ? (
              <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
            ) : (
              <path strokeLinecap="round" strokeLinejoin="round" d="M4 6h16M4 12h16M4 18h16" />
            )}
          </svg>
        </button>
      </div>

      {open && (
        <div className="md:hidden border-t border-gray-200 bg-white">
          <div className="px-4 py-3 flex flex-col gap-1">
            <Link href="/#products" onClick={close} className="px-3 py-2 rounded-md text-sm text-gray-700 hover:bg-gray-50">
              Ապրանքներ
            </Link>
            <Link href="/#about" onClick={close} className="px-3 py-2 rounded-md text-sm text-gray-700 hover:bg-gray-50">
              Մեր մասին
            </Link>
            <Link href="/#contact" onClick={close} className="px-3 py-2 rounded-md text-sm text-gray-700 hover:bg-gray-50">
              Կապ
            </Link>
            <Link
              href="/login"
              onClick={close}
              className="mt-1 px-4 py-2 text-sm font-medium bg-brand-800 text-white rounded-lg hover:bg-brand-900 text-center"
            >
              Մուտք հաճախորդների համար
            </Link>
          </div>
        </div>
      )}
    </nav>
  );
}
