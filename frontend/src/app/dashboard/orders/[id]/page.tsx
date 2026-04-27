import { requireAuth } from "@/lib/auth";
import { serverGet } from "@/lib/api.server";
import { Order, ProductionStage, PaginatedResponse } from "@/types";
import { Card, CardContent, CardHeader } from "@/components/ui/Card";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { formatDate, formatCurrency } from "@/lib/utils";
import Link from "next/link";
import { OrderStatusChange } from "../OrderStatusChange";

export default async function OrderDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const session = await requireAuth();
  const { id } = await params;
  const order = await serverGet<Order>(`/orders/${id}`);

  if (!order) {
    return (
      <div className="text-center py-12">
        <h1 className="text-xl font-semibold text-gray-900">Order not found</h1>
        <Link href="/dashboard/orders" className="text-brand-700 hover:underline mt-2 inline-block">
          Վերադառնալ պատվերներին
        </Link>
      </div>
    );
  }

  let stages: ProductionStage[] = [];
  if (session.role === "admin") {
    const stageData = await serverGet<PaginatedResponse<ProductionStage>>(
      `/production?order_id=${id}&limit=50`
    );
    stages = stageData?.items || [];
  }

  const total = order.items.reduce((s, i) => s + i.quantity * i.unit_price, 0);

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <div>
          <Link href="/dashboard/orders" className="text-sm text-brand-700 hover:underline">
            &larr; Վերադառնալ պատվերներին
          </Link>
          <h1 className="text-2xl font-bold text-gray-900 mt-1">Order #{order.id}</h1>
        </div>
        <div className="flex gap-2">
          <StatusBadge status={order.status} />
          <StatusBadge status={order.priority} />
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2 space-y-6">
          <Card>
            <CardHeader><h3 className="font-semibold">Պատվերի ապրանքներ</h3></CardHeader>
            <CardContent className="p-0">
              <table className="min-w-full divide-y divide-gray-200">
                <thead className="bg-gray-50">
                  <tr>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Տարբերակ</th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Պատվիրված</th>
                    {order.status !== "draft" && (
                      <>
                        <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Պահուստից</th>
                        <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Արտ․</th>
                      </>
                    )}
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Միավորի գին</th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Միջանկյալ գումար</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-200">
                  {order.items.map((item) => (
                    <tr key={item.id}>
                      <td className="px-6 py-4 text-sm">Տարբերակ #{item.product_variant_id}</td>
                      <td className="px-6 py-4 text-sm">{item.quantity}</td>
                      {order.status !== "draft" && (
                        <>
                          <td className="px-6 py-4 text-sm text-green-700 font-medium">{item.fulfilled_from_stock}</td>
                          <td className="px-6 py-4 text-sm text-orange-600 font-medium">{item.production_quantity}</td>
                        </>
                      )}
                      <td className="px-6 py-4 text-sm">{formatCurrency(item.unit_price)}</td>
                      <td className="px-6 py-4 text-sm font-medium">{formatCurrency(item.quantity * item.unit_price)}</td>
                    </tr>
                  ))}
                </tbody>
                <tfoot className="bg-gray-50">
                  <tr>
                    <td colSpan={order.status !== "draft" ? 5 : 3} className="px-6 py-3 text-right text-sm font-semibold">Ընդհանուր</td>
                    <td className="px-6 py-3 text-sm font-bold">{formatCurrency(total)}</td>
                  </tr>
                </tfoot>
              </table>
            </CardContent>
          </Card>

          {stages.length > 0 && (
            <Card>
              <CardHeader><h3 className="font-semibold">Արտադրությունի փուլեր</h3></CardHeader>
              <CardContent>
                <div className="space-y-3">
                  {stages.map((stage) => (
                    <div key={stage.id} className="flex items-center justify-between py-2 border-b border-gray-100 last:border-0">
                      <div>
                        <span className="text-sm font-medium capitalize">
                          {{"cutting": "Կտրում", "sewing": "Կարում", "quality_control": "Որակի վերահսկում", "packaging": "Փաթեթավորում", "ready_for_shipment": "Պատրաստ է առաքման"}[stage.stage_name] || stage.stage_name.replace(/_/g, " ")}
                        </span>
                        {stage.started_at && (
                          <span className="text-xs text-gray-500 ml-2">
                            Started: {formatDate(stage.started_at)}
                          </span>
                        )}
                      </div>
                      <StatusBadge status={stage.status} />
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          )}
        </div>

        <div className="space-y-6">
          <Card>
            <CardHeader><h3 className="font-semibold">Մանրամասներ</h3></CardHeader>
            <CardContent>
              <dl className="space-y-3">
                <div>
                  <dt className="text-xs text-gray-500">Կարգավիճակ</dt>
                  <dd>
                    <StatusBadge status={order.status} />
                    {session.role === "admin" && (
                      <OrderStatusChange orderId={order.id} currentStatus={order.status} />
                    )}
                  </dd>
                </div>
                <div>
                  <dt className="text-xs text-gray-500">Հաճախորդ</dt>
                  <dd className="text-sm font-medium">
                    {order.customer ? (
                      <Link href={`/dashboard/customers/${order.customer.id}`} className="text-brand-700 hover:underline">
                        {order.customer.name}
                        {order.customer.company_name && (
                          <span className="block text-xs text-gray-500 font-normal">{order.customer.company_name}</span>
                        )}
                      </Link>
                    ) : (
                      <span className="text-gray-400">Անհայտ</span>
                    )}
                  </dd>
                </div>
                <div>
                  <dt className="text-xs text-gray-500">Ստեղծվել է</dt>
                  <dd className="text-sm">{formatDate(order.created_at)}</dd>
                </div>
                <div>
                  <dt className="text-xs text-gray-500">Վերջնաժամկետ</dt>
                  <dd className="text-sm">{order.deadline ? formatDate(order.deadline) : "Նշված չէ"}</dd>
                </div>
                <div>
                  <dt className="text-xs text-gray-500">Նշումներ</dt>
                  <dd className="text-sm">{order.notes || "—"}</dd>
                </div>
              </dl>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
