import { requireAuth } from "@/lib/auth";
import { serverGet } from "@/lib/api.server";
import { Product } from "@/types";
import { formatCurrency } from "@/lib/utils";
import Link from "next/link";
import { ProductImageGallery } from "@/components/products/ProductImageGallery";

export default async function CatalogProductPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  await requireAuth();
  const { id } = await params;
  const product = await serverGet<Product>(`/products/${id}`);

  if (!product) {
    return <div className="text-center py-12"><h1 className="text-xl font-semibold">Product not found</h1></div>;
  }

  return (
    <div className="max-w-5xl mx-auto px-6 py-8">
      <Link href="/catalog" className="text-sm text-brand-700 hover:underline">&larr; Վերադառնալ կատալոգ</Link>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-8 mt-4">
        <ProductImageGallery
          images={product.images || []}
          productName={product.name}
        />

        <div>
          <p className="text-sm text-brand-500 font-medium uppercase">{product.category?.name}</p>
          <h1 className="text-3xl font-bold text-gray-900 mt-1">{product.name}</h1>
          <p className="text-sm text-gray-400 font-mono mt-1">{product.sku}</p>
          <p className="text-gray-600 mt-4">{product.description}</p>

          {product.variants.length > 0 && (
            <div className="mt-6">
              <h3 className="font-semibold text-gray-900 mb-3">Հասանելի տարբերակներ</h3>
              {product.variants.some((v) => v.discounted_price != null) && (
                <div className="mb-3 px-3 py-2 bg-green-50 border border-green-200 rounded-lg text-sm text-green-800">
                  Ձեր {Math.round(100 - (product.variants.find((v) => v.discounted_price != null)!.discounted_price! / product.variants.find((v) => v.discounted_price != null)!.price) * 100)}% զեղչը կիրառված է
                </div>
              )}
              <div className="space-y-2">
                {product.variants.map((v) => (
                  <div key={v.id} className="flex items-center justify-between py-2 px-3 bg-gray-50 rounded-lg">
                    <span className="text-sm">
                      {v.size} / {v.color}
                    </span>
                    <div className="text-right">
                      {v.discounted_price != null ? (
                        <>
                          <div className="text-sm font-semibold text-brand-800">{formatCurrency(v.discounted_price)}</div>
                          <div className="text-xs text-gray-400 line-through">{formatCurrency(v.price)}</div>
                        </>
                      ) : (
                        <span className="text-sm font-semibold text-brand-800">{formatCurrency(v.price)}</span>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          <div className="mt-6">
            <Link
              href="/dashboard/orders/new"
              className="inline-block px-6 py-3 bg-brand-800 text-white font-medium rounded-lg hover:bg-brand-900"
            >
              Place Order
            </Link>
          </div>
        </div>
      </div>
    </div>
  );
}
