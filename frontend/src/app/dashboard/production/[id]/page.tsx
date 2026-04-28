import { requireAdmin } from "@/lib/auth";
import { serverGet } from "@/lib/api.server";
import { ProductionStage } from "@/types";
import { Card, CardContent, CardHeader } from "@/components/ui/Card";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { formatDateTime } from "@/lib/utils";
import Link from "next/link";

const STAGE_LABELS: Record<string, string> = {
  cutting: "Կտրում",
  sewing: "Մշակում",
  quality_control: "Որակի վերահսկում",
  packaging: "Փաթեթավորում",
  ready_for_shipment: "Պատրաստ է առաքման",
};

export default async function ProductionDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  await requireAdmin();
  const { id } = await params;
  const stage = await serverGet<ProductionStage>(`/production/${id}`);

  if (!stage) {
    return <div className="text-center py-12"><h1 className="text-xl font-semibold">Stage not found</h1></div>;
  }

  return (
    <div>
      <Link href="/dashboard/production" className="text-sm text-brand-700 hover:underline">&larr; Վերադառնալ արտադրությանը</Link>
      <div className="flex items-center gap-3 mt-1 mb-6">
        <h1 className="text-2xl font-bold text-gray-900">
          {STAGE_LABELS[stage.stage_name] || stage.stage_name.replace(/_/g, " ")}
        </h1>
        <StatusBadge status={stage.status} />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Card>
          <CardHeader><h3 className="font-semibold">Մանրամասներ</h3></CardHeader>
          <CardContent>
            <dl className="space-y-3">
              <div><dt className="text-xs text-gray-500">Պատվեր</dt><dd className="text-sm"><Link href={`/dashboard/orders/${stage.order_id}`} className="text-brand-700 hover:underline">Order #{stage.order_id}</Link></dd></div>
              <div><dt className="text-xs text-gray-500">Սկսվել</dt><dd className="text-sm">{stage.started_at ? formatDateTime(stage.started_at) : "Չի սկսվել"}</dd></div>
              <div><dt className="text-xs text-gray-500">Ավարտվել</dt><dd className="text-sm">{stage.completed_at ? formatDateTime(stage.completed_at) : "Չի ավարտվել"}</dd></div>
              <div><dt className="text-xs text-gray-500">Նշումներ</dt><dd className="text-sm">{stage.notes || "—"}</dd></div>
            </dl>
          </CardContent>
        </Card>

        <Card>
          <CardHeader><h3 className="font-semibold">Փոփոխությունների պատմություն</h3></CardHeader>
          <CardContent>
            {stage.logs.length === 0 ? (
              <p className="text-sm text-gray-500">Փոփոխություններ չեն գրանցվել</p>
            ) : (
              <div className="space-y-3">
                {stage.logs.map((log) => (
                  <div key={log.id} className="flex items-start gap-3 text-sm border-b border-gray-100 pb-3 last:border-0">
                    <div className="flex-1">
                      <div className="flex items-center gap-2">
                        <StatusBadge status={log.previous_status} />
                        <span className="text-gray-400">&rarr;</span>
                        <StatusBadge status={log.new_status} />
                      </div>
                      {log.note && <p className="text-gray-600 mt-1">{log.note}</p>}
                    </div>
                    <span className="text-xs text-gray-400 whitespace-nowrap">{formatDateTime(log.created_at)}</span>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
