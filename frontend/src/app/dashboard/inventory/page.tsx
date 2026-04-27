import { requireAdmin } from "@/lib/auth";
import { serverGet } from "@/lib/api";
import { PaginatedResponse, Material } from "@/types";
import { Card, CardContent } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import Link from "next/link";
import { AddMaterialButton, EditMaterialButton, DeleteMaterialButton } from "./InventoryListActions";

export default async function InventoryPage({
  searchParams,
}: {
  searchParams: Promise<{ page?: string; filter?: string }>;
}) {
  await requireAdmin();
  const params = await searchParams;
  const page = parseInt(params.page || "1");
  const filter = params.filter === "low_stock" ? "low_stock" : "";

  let items: Material[] = [];
  let total = 0;

  if (filter === "low_stock") {
    const lowStock = await serverGet<Material[]>(`/inventory/materials/low-stock`);
    items = lowStock || [];
    total = items.length;
  } else {
    const data = await serverGet<PaginatedResponse<Material>>(`/inventory/materials?page=${page}&limit=20`);
    items = data?.items || [];
    total = data?.total || 0;
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-gray-900">Պահեստ</h1>
        <AddMaterialButton />
      </div>

      {filter === "low_stock" && (
        <div className="mb-4 flex items-center gap-3 px-4 py-2 bg-brand-50 border border-brand-200 rounded-lg text-sm">
          <span className="text-gray-700">
            Ցուցադրված է՝ <strong className="text-brand-800">Ցածր մնացորդ ունեցող ապրանքներ</strong>
          </span>
          <Link href="/dashboard/inventory" className="text-brand-700 hover:underline ml-auto">
            Մաքրել զտիչը
          </Link>
        </div>
      )}

      <Card>
        <CardContent className="p-0">
          <table className="min-w-full divide-y divide-gray-200">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Նյութ</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Արտիկուլ</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Չափման</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Առկա քանակ</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">սահման</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Կարգավիճակ</th>
                <th className="px-6 py-3"></th>
              </tr>
            </thead>
            <tbody className="bg-white divide-y divide-gray-200">
              {items.length === 0 && (
                <tr><td colSpan={7} className="px-6 py-12 text-center text-gray-500">Նյութեր չեն գտնվել</td></tr>
              )}
              {items.map((material) => {
                const qty = material.inventory?.quantity_on_hand ?? 0;
                const isLow = material.low_stock_threshold > 0 && qty <= material.low_stock_threshold;
                return (
                  <tr key={material.id} className="hover:bg-gray-50">
                    <td className="px-6 py-4 text-sm font-medium text-gray-900">{material.name}</td>
                    <td className="px-6 py-4 text-sm text-gray-600 font-mono">{material.sku}</td>
                    <td className="px-6 py-4 text-sm text-gray-600">{material.unit}</td>
                    <td className="px-6 py-4 text-sm font-medium">{qty}</td>
                    <td className="px-6 py-4 text-sm text-gray-600">{material.low_stock_threshold}</td>
                    <td className="px-6 py-4">
                      {isLow ? (
                        <Badge className="bg-red-100 text-red-800">Ցածր մնացորդ</Badge>
                      ) : (
                        <Badge className="bg-green-100 text-green-800">OK</Badge>
                      )}
                    </td>
                    <td className="px-6 py-4 text-right">
                      <div className="flex items-center justify-end gap-3">
                        <Link href={`/dashboard/inventory/${material.id}`} className="text-brand-700 hover:text-brand-900 text-sm font-medium">
                          Տես.
                        </Link>
                        <EditMaterialButton material={material} />
                        <DeleteMaterialButton materialId={material.id} materialName={material.name} />
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </CardContent>
      </Card>
    </div>
  );
}
