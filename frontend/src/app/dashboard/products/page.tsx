import { requireAuth } from "@/lib/auth";
import { serverGet } from "@/lib/api.server";
import { PaginatedResponse, Product, ProductCategory } from "@/types";
import { Card, CardContent } from "@/components/ui/Card";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { formatDate } from "@/lib/utils";
import Link from "next/link";
import { CreateProductButton } from "./ProductActions";
import { ForceDeleteProductButton } from "./ForceDeleteProductButton";

export default async function ProductsPage({
  searchParams,
}: {
  searchParams: Promise<{ page?: string }>;
}) {
  const session = await requireAuth();
  const isAdmin = session.role === "admin";
  const params = await searchParams;
  const page = parseInt(params.page || "1");

  const [data, categories] = await Promise.all([
    serverGet<PaginatedResponse<Product>>(`/products?page=${page}&limit=20`),
    isAdmin ? serverGet<ProductCategory[]>("/categories") : Promise.resolve([]),
  ]);

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-gray-900">Ապրանքներ</h1>
        {isAdmin && <CreateProductButton categories={categories || []} />}
      </div>

      <Card>
        <CardContent className="p-0">
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-gray-200">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Անվանում</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Արտիկուլ</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Կատեգորիա</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Տարբերակներ</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Կարգավիճակ</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Ստեղծվել է</th>
                  <th className="px-6 py-3"></th>
                </tr>
              </thead>
              <tbody className="bg-white divide-y divide-gray-200">
                {data?.items.length === 0 && (
                  <tr><td colSpan={7} className="px-6 py-12 text-center text-gray-500">Ապրանքներ չեն գտնվել</td></tr>
                )}
                {data?.items.map((product) => (
                  <tr key={product.id} className="hover:bg-gray-50">
                    <td className="px-6 py-4 text-sm font-medium text-gray-900">{product.name}</td>
                    <td className="px-6 py-4 text-sm text-gray-600 font-mono">{product.sku}</td>
                    <td className="px-6 py-4 text-sm text-gray-600">{product.category?.name || "—"}</td>
                    <td className="px-6 py-4 text-sm text-gray-600">{product.variants.length}</td>
                    <td className="px-6 py-4">
                      <StatusBadge status={product.is_active ? "completed" : "cancelled"} />
                    </td>
                    <td className="px-6 py-4 text-sm text-gray-600">{formatDate(product.created_at)}</td>
                    <td className="px-6 py-4 text-right whitespace-nowrap">
                      <div className="flex flex-col items-end gap-1 whitespace-nowrap">
                        <div className="flex items-center justify-end gap-3">
                          <Link href={`/dashboard/products/${product.id}`} className="text-brand-700 hover:underline text-sm">
                            Տեսնել
                          </Link>
                          {/* Force-delete: admin + archived + zero variants. */}
                          {isAdmin && !product.is_active && product.variants.length === 0 && (
                            <ForceDeleteProductButton
                              productId={product.id}
                              productName={product.name}
                            />
                          )}
                        </div>
                        {/* Archived-with-variants cleanup hint. */}
                        {!product.is_active && product.variants.length > 0 && (
                          <div className="text-xs text-gray-500 max-w-xs text-right">
                            <span className="block">
                              Ապրանքը արխիվացված է, բայց չի կարող ընդմիշտ ջնջվել մինչև մնում են տարբերակներ:
                            </span>
                            <Link
                              href={`/dashboard/products/${product.id}`}
                              className="text-brand-700 hover:underline"
                            >
                              Դիտել տարբերակները՝ մաքրելու համար →
                            </Link>
                          </div>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
