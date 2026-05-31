import { requireAuth } from "@/lib/auth";
import { serverGet } from "@/lib/api.server";
import { Order, ProductionStage, PaginatedResponse } from "@/types";
import { Card, CardContent, CardHeader } from "@/components/ui/Card";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { formatDate, formatCurrency, formatNumber } from "@/lib/utils";
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

  // Per-item stock availability — used to render the availability columns and
  // to gate the `Ավարտված` (completed) button. Backend remains the source of
  // truth; this is purely a UX hint.
  const showAvailability = order.status === "confirmed" || order.status === "completed";
  const itemAvailability = order.items.map((i) => {
    const stock = i.product_variant?.stock_quantity ?? 0;
    const missing = Math.max(0, i.quantity - stock);
    return { item_id: i.id, stock, missing, sufficient: missing === 0 };
  });
  const anyShortage = itemAvailability.some((a) => !a.sufficient);
  const blockCompleteReason = anyShortage
    ? "Անբավարար մնացորդ — ավարտել հնարավոր չէ"
    : undefined;

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
                    {showAvailability && (
                      <>
                        <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Մնացորդ</th>
                        <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Կարգավիճակ</th>
                      </>
                    )}
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Միավորի գին</th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Միջանկյալ գումար</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-200">
                  {order.items.map((item, idx) => {
                    const variant = item.product_variant;
                    // When the variant was admin force-deleted (migration 015),
                    // product_variant_id is NULL and the join returns null.
                    // Fall back to the snapshot columns so the order history
                    // stays readable, with a (ջնջված) marker.
                    const orphaned = !variant && item.product_variant_id == null;
                    const productName = orphaned
                      ? `${item.product_name_snapshot ?? "—"} (ջնջված)`
                      : variant?.product?.name ?? `Տարբերակ #${item.product_variant_id ?? "—"}`;
                    const avail = itemAvailability[idx];
                    return (
                    <tr key={item.id}>
                      <td className="px-6 py-4 text-sm">
                        <div className={`font-medium ${orphaned ? "text-gray-500 italic" : "text-gray-900"}`}>
                          {productName}
                        </div>
                        {variant && (
                          <div className="text-xs text-gray-500 mt-0.5">
                            Չափս: {variant.size} · Գույն: {variant.color}
                          </div>
                        )}
                        {orphaned && item.variant_name_snapshot && (
                          <div className="text-xs text-gray-400 mt-0.5">
                            {item.variant_name_snapshot}
                          </div>
                        )}
                      </td>
                      <td className="px-6 py-4 text-sm">{formatNumber(item.quantity)}</td>
                      {showAvailability && (
                        <>
                          <td className={`px-6 py-4 text-sm font-medium ${avail.sufficient ? "text-gray-900" : "text-red-700"}`}>
                            {formatNumber(avail.stock)}
                          </td>
                          <td className="px-6 py-4 text-sm">
                            {avail.sufficient ? (
                              <span className="text-xs font-semibold text-green-700">Բավարար</span>
                            ) : (
                              <span className="text-xs font-semibold text-red-700">
                                Բացակայում է {formatNumber(avail.missing)}
                              </span>
                            )}
                          </td>
                        </>
                      )}
                      <td className="px-6 py-4 text-sm">{formatCurrency(item.unit_price)}</td>
                      <td className="px-6 py-4 text-sm font-medium">{formatCurrency(item.quantity * item.unit_price)}</td>
                    </tr>
                    );
                  })}
                </tbody>
                <tfoot className="bg-gray-50">
                  <tr>
                    <td colSpan={showAvailability ? 5 : 3} className="px-6 py-3 text-right text-sm font-semibold">Ընդհանուր</td>
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
                        <span className="text-sm font-medium">
                          {{"cutting": "Կտրում", "sewing": "Մշակում", "quality_control": "Որակի վերահսկում", "packaging": "Փաթեթավորում", "ready_for_shipment": "Պատրաստ է առաքման"}[stage.stage_name] || stage.stage_name.replace(/_/g, " ")}
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
                      <OrderStatusChange
                        orderId={order.id}
                        currentStatus={order.status}
                        blockComplete={anyShortage && !order.stock_deducted}
                        blockCompleteReason={blockCompleteReason}
                      />
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
