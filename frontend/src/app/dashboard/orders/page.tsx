import { requireAuth } from "@/lib/auth";
import { serverGet } from "@/lib/api";
import { PaginatedResponse, Order } from "@/types";
import { Card, CardContent, CardHeader } from "@/components/ui/Card";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { formatDate, formatCurrency } from "@/lib/utils";
import Link from "next/link";
import { OrderRowActions } from "./OrderRowActions";

const FILTER_LABELS: Record<string, string> = {
  active: "Ակտիվ պատվերներ",
  delayed: "Ուշացած պատվերներ",
};

export default async function OrdersPage({
  searchParams,
}: {
  searchParams: Promise<{ page?: string; search?: string; status?: string; filter?: string }>;
}) {
  const session = await requireAuth();
  const params = await searchParams;
  const page = parseInt(params.page || "1");
  const status = params.status || "";
  const filter = params.filter && FILTER_LABELS[params.filter] ? params.filter : "";

  let queryStr = `/orders?page=${page}&limit=20`;
  if (status) queryStr += `&status=${status}`;
  if (filter) queryStr += `&filter=${filter}`;

  const data = await serverGet<PaginatedResponse<Order>>(queryStr);

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-gray-900">
          {session.role === "admin" ? "Պատվերներ" : "Իմ պատվերներ"}
        </h1>
        <Link
          href="/dashboard/orders/new"
          className="px-4 py-2 bg-brand-800 text-white text-sm font-medium rounded-lg hover:bg-brand-900"
        >
          Նոր պատվեր
        </Link>
      </div>

      {filter && (
        <div className="mb-4 flex items-center gap-3 px-4 py-2 bg-brand-50 border border-brand-200 rounded-lg text-sm">
          <span className="text-gray-700">
            Ցուցադրված է՝ <strong className="text-brand-800">{FILTER_LABELS[filter]}</strong>
          </span>
          <Link href="/dashboard/orders" className="text-brand-700 hover:underline ml-auto">
            Մաքրել զտիչը
          </Link>
        </div>
      )}

      <Card>
        <CardContent className="p-0">
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-gray-200">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Համար</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Կարգավիճակ</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Առաջնահերթություն</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Հաճախորդ</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Ապրանքներ</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Վերջնաժամկետ</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Ստեղծվել է</th>
                  <th className="px-6 py-3"></th>
                </tr>
              </thead>
              <tbody className="bg-white divide-y divide-gray-200">
                {data?.items.length === 0 && (
                  <tr>
                    <td colSpan={8} className="px-6 py-12 text-center text-gray-500">
                      Արդյունքներ չեն գտնվել
                    </td>
                  </tr>
                )}
                {data?.items.map((order) => {
                  const total = order.items.reduce((s, i) => s + i.quantity * i.unit_price, 0);
                  return (
                    <tr key={order.id} className="hover:bg-gray-50">
                      <td className="px-6 py-4 text-sm font-medium text-gray-900">#{order.id}</td>
                      <td className="px-6 py-4"><StatusBadge status={order.status} /></td>
                      <td className="px-6 py-4"><StatusBadge status={order.priority} /></td>
                      <td className="px-6 py-4 text-sm text-gray-600 max-w-[180px] truncate">
                        {order.customer ? (
                          <Link href={`/dashboard/customers/${order.customer.id}`} className="text-brand-700 hover:underline">
                            {order.customer.name}
                          </Link>
                        ) : (
                          <span className="text-gray-400">—</span>
                        )}
                      </td>
                      <td className="px-6 py-4 text-sm text-gray-600">
                        {order.items.length} ապրանքներ &middot; {formatCurrency(total)}
                      </td>
                      <td className="px-6 py-4 text-sm text-gray-600">
                        {order.deadline ? formatDate(order.deadline) : "—"}
                      </td>
                      <td className="px-6 py-4 text-sm text-gray-600">{formatDate(order.created_at)}</td>
                      <td className="px-6 py-4 text-right">
                        {session.role === "admin" ? (
                          <OrderRowActions orderId={order.id} currentStatus={order.status} />
                        ) : (
                          <Link href={`/dashboard/orders/${order.id}`} className="text-brand-700 hover:underline text-sm">
                            Դիտել
                          </Link>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </CardContent>
      </Card>

      {data && data.total > 20 && (
        <div className="flex justify-center gap-2 mt-4">
          {page > 1 && (
            <Link href={`/dashboard/orders?page=${page - 1}${filter ? `&filter=${filter}` : ""}`} className="px-3 py-1 text-sm border rounded-lg hover:bg-gray-50">
              Previous
            </Link>
          )}
          <span className="px-3 py-1 text-sm text-gray-600">Էջ {page}</span>
          {page * 20 < data.total && (
            <Link href={`/dashboard/orders?page=${page + 1}${filter ? `&filter=${filter}` : ""}`} className="px-3 py-1 text-sm border rounded-lg hover:bg-gray-50">
              Next
            </Link>
          )}
        </div>
      )}
    </div>
  );
}
