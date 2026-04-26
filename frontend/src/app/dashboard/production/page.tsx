import { requireAdmin } from "@/lib/auth";
import { serverGet } from "@/lib/api";
import { PaginatedResponse, ProductionStage } from "@/types";
import { Card, CardContent } from "@/components/ui/Card";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { formatDate } from "@/lib/utils";
import Link from "next/link";
import { StageStatusChange } from "./StageStatusChange";

export default async function ProductionPage({
  searchParams,
}: {
  searchParams: Promise<{ page?: string; status?: string; filter?: string }>;
}) {
  await requireAdmin();
  const params = await searchParams;
  const page = parseInt(params.page || "1");
  const filter = params.filter === "in_progress" ? "in_progress" : "";
  const effectiveStatus = params.status || filter;
  // Default to active production records — stages whose order is currently in_production.
  // Completed/cancelled orders drop off this list (their stages stay in DB for history,
  // and a stage detail page is still reachable by id).
  let queryStr = `/production?page=${page}&limit=20&active=true`;
  if (effectiveStatus) queryStr += `&status=${effectiveStatus}`;

  const data = await serverGet<PaginatedResponse<ProductionStage>>(queryStr);

  return (
    <div>
      <h1 className="text-2xl font-bold text-gray-900 mb-6">Արտադրություն</h1>

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
                  <td className="px-6 py-4 text-sm capitalize">{{"cutting": "Կտրում", "sewing": "Կարում", "quality_control": "Որակի վերահսկում", "packaging": "Փաթեթավորում", "ready_for_shipment": "Պատրաստ է առաքման"}[stage.stage_name] || stage.stage_name.replace(/_/g, " ")}</td>
                  <td className="px-6 py-4"><StatusBadge status={stage.status} /></td>
                  <td className="px-6 py-4 text-sm text-gray-600">{stage.started_at ? formatDate(stage.started_at) : "—"}</td>
                  <td className="px-6 py-4 text-sm text-gray-600">{stage.completed_at ? formatDate(stage.completed_at) : "—"}</td>
                  <td className="px-6 py-4 text-right">
                    <div className="flex items-center justify-end gap-3 whitespace-nowrap">
                      <StageStatusChange stageId={stage.id} currentStatus={stage.status} />
                      <Link href={`/dashboard/production/${stage.id}`} className="text-brand-700 hover:underline text-sm">
                        View
                      </Link>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </CardContent>
      </Card>
    </div>
  );
}
