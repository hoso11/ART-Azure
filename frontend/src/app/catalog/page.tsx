import { requireAuth } from "@/lib/auth";
import { serverGet } from "@/lib/api";
import { PaginatedResponse, Product } from "@/types";
import { formatCurrency } from "@/lib/utils";
import Link from "next/link";

function getProductPrimaryImage(product: Product): string | null {
  const primary = product.images?.find((img) => img.is_primary);
  if (primary?.url) return primary.url;
  const first = product.images?.[0];
  if (first?.url) return first.url;
  return null;
}

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
          const minPrice = product.variants.length
            ? Math.min(...product.variants.map((v) => v.price))
            : 0;
          const imageUrl = getProductPrimaryImage(product);
          return (
            <Link key={product.id} href={`/catalog/${product.id}`} className="block">
              <div className="bg-white border border-gray-200 rounded-lg overflow-hidden hover:shadow-md transition-shadow">
                <div className="h-48 bg-brand-50 flex items-center justify-center">
                  {imageUrl ? (
                    <img
                      src={imageUrl}
                      alt={product.name}
                      className="w-full h-full object-cover"
                    />
                  ) : (
                    <svg className="h-16 w-16 text-brand-200" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1} d="M20.25 7.5l-.625 10.632a2.25 2.25 0 01-2.247 2.118H6.622a2.25 2.25 0 01-2.247-2.118L3.75 7.5M10 11.25h4M3.375 7.5h17.25c.621 0 1.125-.504 1.125-1.125v-1.5c0-.621-.504-1.125-1.125-1.125H3.375c-.621 0-1.125.504-1.125 1.125v1.5c0 .621.504 1.125 1.125 1.125z" />
                    </svg>
                  )}
                </div>
                <div className="p-4">
                  <p className="text-xs text-brand-500 font-medium uppercase">{product.category?.name}</p>
                  <h3 className="font-semibold text-gray-900 mt-1">{product.name}</h3>
                  <p className="text-sm text-gray-500 mt-1 line-clamp-2">{product.description}</p>
                  <div className="mt-3">
                    <span className="text-brand-800 font-semibold">
                      {minPrice > 0 ? `Սկսած ${formatCurrency(minPrice)}` : "Կապվեք գնի համար"}
                    </span>
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
