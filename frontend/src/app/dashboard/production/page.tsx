import { requireModule } from "@/lib/auth";
import { serverGet } from "@/lib/api.server";
import { PaginatedResponse, ProductionStage, ProductionBatch } from "@/types";
import { Card, CardContent } from "@/components/ui/Card";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { formatDate, formatNumber } from "@/lib/utils";
import Link from "next/link";
import { OrderCurrentControl } from "./OrderCurrentControl";
import { CreateBatchButton } from "./CreateBatchButton";
import { BatchControl } from "./BatchControl";
import { DeleteBatchButton } from "./DeleteBatchButton";
import { ForceDeleteBatchButton } from "./ForceDeleteBatchButton";

const STAGE_LABELS: Record<string, string> = {
  cutting: "Կտրում",
  sewing: "Մշակում",
  processing: "Մշակում",
  quality_control: "Որակի վերահսկում",
  packaging: "Փաթեթավորում",
  warehousing: "Պահեստավորում",
  ready_for_shipment: "Պատրաստ է առաքման",
};

export default async function ProductionPage({
  searchParams,
}: {
  searchParams: Promise<{ page?: string; status?: string; filter?: string }>;
}) {
  const session = await requireModule("production");
  const isAdmin = session.role === "admin";
  const params = await searchParams;
  const page = parseInt(params.page || "1");
  const filter = params.filter === "in_progress" ? "in_progress" : "";
  const effectiveStatus = params.status || filter;
  let queryStr = `/production?page=${page}&limit=20&active=true&one_per_order=true`;
  if (effectiveStatus) queryStr += `&status=${effectiveStatus}`;

  const data = await serverGet<PaginatedResponse<ProductionStage>>(queryStr);

  let batchesQueryStr = `/production/batches?page=1&limit=20`;
  if (effectiveStatus) batchesQueryStr += `&stage_status=${effectiveStatus}`;
  const batches = await serverGet<PaginatedResponse<ProductionBatch>>(batchesQueryStr);

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-gray-900">Արտադրություն</h1>
        <CreateBatchButton />
      </div>

      {filter === "in_progress" && (
        <div className="mb-4 flex items-center gap-3 px-4 py-2 bg-brand-50 border border-brand-200 rounded-lg text-sm">
          <span className="text-gray-700">
            Ցուցադրված է՝ <strong className="text-brand-800">Ընթացքի մեջ</strong>
          </span>
          <Link href="/dashboard/production" className="text-brand-700 hover:underline ml-auto">
            Մաքրել զտիչը
          </Link>
        </div>
      )}

      <div className="flex gap-2 mb-4">
        {["", "pending", "in_progress", "completed"].map((s) => (
          <Link
            key={s}
            href={`/dashboard/production${s ? `?status=${s}` : ""}`}
            className={`px-3 py-1.5 text-sm rounded-lg border ${params.status === s || (!params.status && !s) ? "bg-brand-800 text-white border-brand-800" : "text-gray-600 border-gray-300 hover:bg-gray-50"}`}
          >
            {{"": "Բոլորը", "pending": "Սպասման մեջ", "in_progress": "Ընթացքի մեջ", "completed": "Ավարտված"}[s] || s}
          </Link>
        ))}
      </div>

      <Card>
        <CardContent className="p-0">
          <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-gray-200">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Պատվեր</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Փուլ</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Կարգավիճակ</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Սկսվել է</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Ավարտվել է</th>
                <th className="px-6 py-3"></th>
              </tr>
            </thead>
            <tbody className="bg-white divide-y divide-gray-200">
              {data?.items.length === 0 && (
                <tr><td colSpan={6} className="px-6 py-12 text-center text-gray-500">Արտադրությունի փուլեր չեն գտնվել</td></tr>
              )}
              {data?.items.map((stage) => (
                <tr key={stage.id} className="hover:bg-gray-50">
                  <td className="px-6 py-4 text-sm font-medium">
                    <Link href={`/dashboard/orders/${stage.order_id}`} className="text-brand-700 hover:underline">
                      Order #{stage.order_id}
                    </Link>
                  </td>
                  <td className="px-6 py-4 text-sm">{STAGE_LABELS[stage.stage_name] || stage.stage_name}</td>
                  <td className="px-6 py-4"><StatusBadge status={stage.status} /></td>
                  <td className="px-6 py-4 text-sm text-gray-600">{stage.started_at ? formatDate(stage.started_at) : "—"}</td>
                  <td className="px-6 py-4 text-sm text-gray-600">{stage.completed_at ? formatDate(stage.completed_at) : "—"}</td>
                  <td className="px-6 py-4 text-right whitespace-nowrap">
                    <div className="flex items-center justify-end gap-3 whitespace-nowrap">
                      <OrderCurrentControl
                        orderId={stage.order_id}
                        currentStage={stage.stage_name}
                        currentStatus={stage.status}
                      />
                      <Link href={`/dashboard/production/${stage.id}`} className="text-brand-700 hover:underline text-sm">
                        Տեսնել
                      </Link>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          </div>
        </CardContent>
      </Card>

      {/* Stock-based production batches (production-for-stock) */}
      <Card className="mt-6">
        <div className="px-6 py-3 border-b border-gray-100 flex items-center justify-between">
          <h2 className="text-sm font-semibold text-gray-700">Պահեստի համար</h2>
          <span className="text-xs text-gray-500">Տեսակ՝ Պահեստի համար</span>
        </div>
        <CardContent className="p-0">
          <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-gray-200">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Ապրանք</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Տարբերակ</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Քանակ</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Փուլ</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Կարգավիճակ</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Ստեղծվել է</th>
                <th className="px-6 py-3"></th>
              </tr>
            </thead>
            <tbody className="bg-white divide-y divide-gray-200">
              {batches?.items.length === 0 && (
                <tr>
                  <td colSpan={7} className="px-6 py-12 text-center text-gray-500 text-sm">
                    Պահեստի համար արտադրություն չկա
                  </td>
                </tr>
              )}
              {batches?.items.map((b) => (
                <tr key={b.id} className="hover:bg-gray-50">
                  <td className="px-6 py-4 text-sm font-medium text-gray-900">
                    {b.product?.name
                      || (b.product_name_snapshot ? `${b.product_name_snapshot} (ջնջված)` : `#${b.product_id}`)}
                  </td>
                  <td className="px-6 py-4 text-sm text-gray-700">
                    {b.variant
                      ? `${b.variant.size} / ${b.variant.color}`
                      : (b.variant_name_snapshot
                          ? `${b.variant_name_snapshot} (ջնջված)`
                          : (b.variant_id != null ? `#${b.variant_id}` : "—"))}
                  </td>
                  <td className="px-6 py-4 text-sm font-medium">
                    {formatNumber(b.quantity_to_produce)}
                    {/* Show running cumulative whenever any quantity has been processed,
                        not only after final completion. While in progress, also display
                        the remaining count so admins can plan the next partial save. */}
                    {(b.good_quantity > 0 || b.damaged_quantity > 0) && (
                      <div className="mt-1 text-xs flex items-center gap-2 flex-wrap">
                        <span className="text-green-700">Լավ՝ {formatNumber(b.good_quantity)}</span>
                        {b.damaged_quantity > 0 && (
                          <span
                            className="bg-red-100 text-red-800 px-1.5 py-0.5 rounded font-medium"
                            title={b.defect_reason || undefined}
                          >
                            Խոտան՝ {formatNumber(b.damaged_quantity)}
                          </span>
                        )}
                        {!b.stock_added && (
                          <span className="text-gray-500">
                            Մնացած՝ {formatNumber(b.quantity_to_produce - b.good_quantity - b.damaged_quantity)}
                          </span>
                        )}
                      </div>
                    )}
                  </td>
                  <td className="px-6 py-4 text-sm">
                    {STAGE_LABELS[b.current_stage] || b.current_stage}
                  </td>
                  <td className="px-6 py-4">
                    <StatusBadge status={b.stage_status} />
                  </td>
                  <td className="px-6 py-4 text-sm text-gray-600">{formatDate(b.created_at)}</td>
                  <td className="px-6 py-4 text-right whitespace-nowrap">
                    <div className="flex items-center justify-end gap-3 whitespace-nowrap">
                      <BatchControl
                        batchId={b.id}
                        currentStage={b.current_stage}
                        currentStatus={b.stage_status}
                        stockAdded={b.stock_added}
                        quantityToProduce={b.quantity_to_produce}
                        goodSoFar={b.good_quantity}
                        damagedSoFar={b.damaged_quantity}
                      />
                      {isAdmin && b.stage_status === "completed" && b.stock_added && (
                        <DeleteBatchButton
                          batchId={b.id}
                          good={b.good_quantity}
                          damaged={b.damaged_quantity}
                        />
                      )}
                      {/* Universal admin force-delete: works in any stage
                          (pending / in_progress / completed). Does NOT roll
                          back inventory — confirmed by typed FORCE DELETE
                          in the modal. */}
                      {isAdmin && (
                        <ForceDeleteBatchButton
                          batchId={b.id}
                          stageStatus={b.stage_status}
                          materialsDeducted={b.materials_deducted}
                          good={b.good_quantity}
                          damaged={b.damaged_quantity}
                        />
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
