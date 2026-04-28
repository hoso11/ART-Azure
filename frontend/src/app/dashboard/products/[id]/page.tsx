import { requireAuth } from "@/lib/auth";
import { serverGet } from "@/lib/api.server";
import { Product, ProductCategory } from "@/types";
import { Card, CardContent, CardHeader } from "@/components/ui/Card";
import { formatCurrency } from "@/lib/utils";
import Link from "next/link";
import { EditProductForm } from "../EditProductForm";
import { DeleteProductButton } from "../ProductActions";
import { ProductImageUpload } from "../ProductImageUpload";
import { VariantManager } from "../VariantActions";
import { ProductImageGallery } from "@/components/products/ProductImageGallery";

export default async function ProductDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const session = await requireAuth();
  const isAdmin = session.role === "admin";
  const { id } = await params;

  const [product, categories] = await Promise.all([
    serverGet<Product>(`/products/${id}`),
    isAdmin ? serverGet<ProductCategory[]>("/categories") : Promise.resolve([]),
  ]);

  if (!product) {
    return <div className="text-center py-12"><h1 className="text-xl font-semibold">Product not found</h1></div>;
  }

  return (
    <div>
      <Link href="/dashboard/products" className="text-sm text-brand-700 hover:underline">&larr; Վերադառնալ ապրանքներին</Link>

      <div className="flex items-center justify-between mt-1 mb-6">
        <h1 className="text-2xl font-bold text-gray-900">{product.name}</h1>
        {isAdmin && (
          <div className="flex gap-2">
            <EditProductForm product={product} categories={categories || []} />
            <DeleteProductButton productId={product.id} productName={product.name} />
          </div>
        )}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2 space-y-6">
          <Card>
            {isAdmin ? (
              <CardContent className="p-0">
                <div className="px-6 py-4">
                  <VariantManager productId={product.id} variants={product.variants} />
                </div>
              </CardContent>
            ) : (
              <>
                <CardHeader><h3 className="font-semibold">Տարբերակներ</h3></CardHeader>
                <CardContent className="p-0">
                  <table className="min-w-full divide-y divide-gray-200">
                    <thead className="bg-gray-50">
                      <tr>
                        <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Չափս</th>
                        <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Գույն</th>
                        <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Գին</th>
                        <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Մնացորդ</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-200">
                      {product.variants.length === 0 && (
                        <tr><td colSpan={4} className="px-6 py-8 text-center text-gray-500 text-sm">Տարբերակներ չկան</td></tr>
                      )}
                      {product.variants.map((v) => (
                        <tr key={v.id}>
                          <td className="px-6 py-4 text-sm">{v.size}</td>
                          <td className="px-6 py-4 text-sm">{v.color}</td>
                          <td className="px-6 py-4 text-sm">{formatCurrency(v.price)}</td>
                          <td className="px-6 py-4 text-sm">{v.stock_quantity}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </CardContent>
              </>
            )}
          </Card>

          {/* Images section */}
          <Card>
            <CardHeader><h3 className="font-semibold">Նկարներ</h3></CardHeader>
            <CardContent>
              {isAdmin ? (
                <ProductImageUpload
                  productId={product.id}
                  images={product.images}
                />
              ) : (
                <ProductImageGallery
                  images={product.images || []}
                  productName={product.name}
                  mainHeightClass="h-64"
                />
              )}
            </CardContent>
          </Card>
        </div>

        <Card>
          <CardHeader><h3 className="font-semibold">Մանրամասներ</h3></CardHeader>
          <CardContent>
            <dl className="space-y-3">
              <div><dt className="text-xs text-gray-500">Արտիկուլ</dt><dd className="text-sm font-mono">{product.sku}</dd></div>
              <div><dt className="text-xs text-gray-500">Կատեգորիա</dt><dd className="text-sm">{product.category?.name || "—"}</dd></div>
              <div><dt className="text-xs text-gray-500">Նկարագրություն</dt><dd className="text-sm">{product.description || "—"}</dd></div>
              <div><dt className="text-xs text-gray-500">Տեխնիկական նշումներ</dt><dd className="text-sm">{product.technical_notes || "—"}</dd></div>
              <div><dt className="text-xs text-gray-500">Կարգավիճակ</dt><dd className="text-sm">{product.is_active ? "Ակտիվ" : "Անակտիվ"}</dd></div>
            </dl>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
