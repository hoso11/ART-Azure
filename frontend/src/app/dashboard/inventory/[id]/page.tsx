import { requireModule } from "@/lib/auth";
import { serverGet } from "@/lib/api.server";
import { Material, StockMovement, PaginatedResponse } from "@/types";
import { Card, CardContent, CardHeader } from "@/components/ui/Card";
import { formatDateTime, formatNumber } from "@/lib/utils";
import Link from "next/link";
import { EditMaterialForm, DeleteMaterialButton, AddStockMovement } from "../InventoryActions";
import { ForceDeleteMaterialButton } from "../ForceDeleteMaterialButton";

export default async function MaterialDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const session = await requireModule("inventory");
  const isAdmin = session.role === "admin";
  const { id } = await params;

  const [material, movements] = await Promise.all([
    serverGet<Material>(`/inventory/materials/${id}`),
    serverGet<PaginatedResponse<StockMovement>>(`/inventory/movements?material_id=${id}&limit=50`),
  ]);

  if (!material) {
    return <div className="text-center py-12"><h1 className="text-xl font-semibold">Material not found</h1></div>;
  }

  return (
    <div>
      <Link href="/dashboard/inventory" className="text-sm text-brand-700 hover:underline">&larr; Վերադառնալ պահեստ</Link>

      <div className="flex items-center justify-between mt-1 mb-6">
        <h1 className="text-2xl font-bold text-gray-900">{material.name}</h1>
        <div className="flex gap-2 items-center">
          <EditMaterialForm material={material} />
          <DeleteMaterialButton materialId={material.id} materialName={material.name} />
          {/* Pydantic serializes Decimal as string ("0.000"); coerce to
              Number so the strict-equality gate matches the displayed value. */}
          {isAdmin && Number(material.inventory?.quantity_on_hand ?? 0) === 0 && (
            <ForceDeleteMaterialButton
              materialId={material.id}
              materialName={material.name}
            />
          )}
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <Card>
          <CardHeader><h3 className="font-semibold">Մանրամասներ</h3></CardHeader>
          <CardContent>
            <dl className="space-y-3">
              <div><dt className="text-xs text-gray-500">Արտիկուլ</dt><dd className="text-sm font-mono">{material.sku}</dd></div>
              <div><dt className="text-xs text-gray-500">Չափման</dt><dd className="text-sm">{material.unit}</dd></div>
              <div><dt className="text-xs text-gray-500">Առկա քանակ</dt><dd className="text-sm font-bold">{formatNumber(material.inventory?.quantity_on_hand ?? 0)}</dd></div>
              <div><dt className="text-xs text-gray-500">Ցածր մնացորդի սահման</dt><dd className="text-sm">{formatNumber(material.low_stock_threshold)}</dd></div>
              <div><dt className="text-xs text-gray-500">Նկարագրություն</dt><dd className="text-sm">{material.description || "—"}</dd></div>
            </dl>
          </CardContent>
        </Card>

        <div className="lg:col-span-2">
          <Card>
            <CardHeader>
              <div className="flex items-center justify-between">
                <h3 className="font-semibold">Պահեստի շարժումներ</h3>
                <AddStockMovement materialId={material.id} />
              </div>
            </CardHeader>
            <CardContent className="p-0">
              <table className="min-w-full divide-y divide-gray-200">
                <thead className="bg-gray-50">
                  <tr>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Ստեղծվել</th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Փոփոխություն</th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Պատճառ</th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Պատվեր</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-200">
                  {movements?.items.length === 0 && (
                    <tr><td colSpan={4} className="px-6 py-8 text-center text-gray-500">Շարժումներ չեն գրանցվել</td></tr>
                  )}
                  {movements?.items.map((m) => (
                    <tr key={m.id}>
                      <td className="px-6 py-4 text-sm">{formatDateTime(m.created_at)}</td>
                      <td className={`px-6 py-4 text-sm font-medium ${m.quantity_change > 0 ? "text-green-700" : "text-red-700"}`}>
                        {m.quantity_change > 0 ? "+" : ""}{formatNumber(m.quantity_change)}
                      </td>
                      <td className="px-6 py-4 text-sm capitalize">{m.reason.replace(/_/g, " ")}</td>
                      <td className="px-6 py-4 text-sm">{m.order_id ? `#${m.order_id}` : "—"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
