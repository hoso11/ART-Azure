import { requireAuth } from "@/lib/auth";
import { serverGet } from "@/lib/api.server";
import { PaginatedResponse, Product } from "@/types";
import { formatCurrency } from "@/lib/utils";
import Link from "next/link";
import { ProductCardImage } from "@/components/products/ProductCardImage";

export default async function CatalogPage({
  searchParams,
}: {
  searchParams: Promise<{ page?: string; category_id?: string }>;
}) {
  await requireAuth();
  const params = await searchParams;
  const page = parseInt(params.page || "1");
  let queryStr = `/products?page=${page}&limit=12`;
  if (params.category_id) queryStr += `&category_id=${params.category_id}`;

  const data = await serverGet<PaginatedResponse<Product>>(queryStr);

  return (
    <div className="max-w-7xl mx-auto px-6 py-8">
      <h1 className="text-2xl font-bold text-gray-900 mb-6">Ապրանքների կատալոգ</h1>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6">
        {data?.items.length === 0 && (
          <div className="col-span-full text-center py-12 text-gray-500">
            No products available
          </div>
        )}
        {data?.items.map((product) => {
          const hasDiscount = product.variants.some((v) => v.discounted_price != null);
          const minOriginal = product.variants.length
            ? Math.min(...product.variants.map((v) => v.price))
            : 0;
          const minDiscounted = hasDiscount
            ? Math.min(...product.variants.filter((v) => v.discounted_price != null).map((v) => v.discounted_price!))
            : null;
          const discountPct = hasDiscount && minOriginal > 0 && minDiscounted != null
            ? Math.round(100 - (minDiscounted / minOriginal) * 100)
            : 0;
          return (
            <Link key={product.id} href={`/catalog/${product.id}`} className="block">
              <div className="bg-white border border-gray-200 rounded-lg overflow-hidden hover:shadow-md transition-shadow">
                <ProductCardImage
                  images={product.images || []}
                  productName={product.name}
                />
                <div className="p-4">
                  <p className="text-xs text-brand-500 font-medium uppercase">{product.category?.name}</p>
                  <h3 className="font-semibold text-gray-900 mt-1">{product.name}</h3>
                  <p className="text-sm text-gray-500 mt-1 line-clamp-2">{product.description}</p>
                  <div className="mt-3">
                    {minOriginal > 0 ? (
                      hasDiscount && minDiscounted != null ? (
                        <div>
                          <div className="flex items-center gap-2">
                            <span className="text-brand-800 font-semibold">{`Սկսած ${formatCurrency(minDiscounted)}`}</span>
                            <span className="text-xs bg-green-100 text-green-800 px-1.5 py-0.5 rounded font-medium">-{discountPct}%</span>
                          </div>
                          <span className="text-xs text-gray-400 line-through">{formatCurrency(minOriginal)}</span>
                        </div>
                      ) : (
                        <span className="text-brand-800 font-semibold">{`Սկսած ${formatCurrency(minOriginal)}`}</span>
                      )
                    ) : (
                      <span className="text-brand-800 font-semibold">Կապվեք գնի համար</span>
                    )}
                  </div>
                  <p className="text-xs text-gray-400 mt-1">{product.variants.length} տարբերակներ հասանելի</p>
                </div>
              </div>
            </Link>
          );
        })}
      </div>
    </div>
  );
}
