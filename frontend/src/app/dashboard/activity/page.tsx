import { requireAdmin } from "@/lib/auth";
import { serverGet } from "@/lib/api.server";
import { PaginatedResponse, ActivityLog } from "@/types";
import { Card, CardContent } from "@/components/ui/Card";
import { formatDateTime } from "@/lib/utils";
import Link from "next/link";

const ACTION_LABELS: Record<string, string> = {
  "auth.login_success": "Մուտք",
  "auth.login_failed": "Մուտքի սխալ",
  "auth.logout": "Ելք",
  "user.created": "Օգտատեր ստեղծվեց",
  "user.updated": "Օգտատեր փոփոխվեց",
  "user.deleted": "Օգտատեր ջնջվեց",
  "user.password_changed": "Գաղտնաբառը փոխվեց",
  "user.discount_changed": "Զեղչը փոխվեց",
  "customer.created": "Հաճախորդ ստեղծվեց",
  "customer.updated": "Հաճախորդ փոփոխվեց",
  "customer.deleted": "Հաճախորդ ջնջվեց",
  "category.created": "Կատեգորիա ստեղծվեց",
  "category.updated": "Կատեգորիա փոփոխվեց",
  "category.deleted": "Կատեգորիա ջնջվեց",
  "product.created": "Ապրանք ստեղծվեց",
  "product.updated": "Ապրանք փոփոխվեց",
  "product.deleted": "Ապրանք ջնջվեց",
  "variant.created": "Տարբերակ ստեղծվեց",
  "variant.updated": "Տարբերակ փոփոխվեց",
  "variant.deleted": "Տարբերակ ջնջվեց",
  "material.created": "Նյութ ստեղծվեց",
  "material.updated": "Նյութ փոփոխվեց",
  "material.deleted": "Նյութ ջնջվեց",
  "inventory.stock_movement": "Պահեստի շարժ",
  "order.created": "Պատվեր ստեղծվեց",
  "order.updated": "Պատվեր փոփոխվեց",
  "order.deleted": "Պատվեր ջնջվեց",
  "order.status_changed": "Պատվերի կարգավիճակը փոխվեց",
  "order.item_added": "Պատվերի տող ավելացվեց",
  "order.item_removed": "Պատվերի տող հեռացվեց",
  "production.batch_created": "Արտադրությունը ստեղծվեց",
  "production.batch_updated": "Արտադրությունը փոփոխվեց",
  "production.batch_completed": "Արտադրությունն ավարտվեց",
  "production.batch_progress": "Արտադրության մասնակի պահպանում",
  "production.stage_updated": "Փուլը փոփոխվեց",
  "production.stage_status_changed": "Փուլի կարգավիճակը փոխվեց",
  "production.order_current_changed": "Արտադրության փուլը փոխվեց",
  "report.generated": "Հաշվետվություն ստեղծվեց",
  "report.exported": "Հաշվետվություն արտահանվեց",
};

const MODULE_LABELS: Record<string, string> = {
  auth: "Մուտք",
  user: "Օգտատեր",
  customer: "Հաճախորդ",
  category: "Կատեգորիա",
  product: "Ապրանք",
  variant: "Տարբերակ",
  material: "Նյութ",
  stock_movement: "Պահեստ",
  order: "Պատվեր",
  order_item: "Պատվերի տող",
  production_batch: "Արտադրություն",
  production_stage: "Արտադրության փուլ",
  report: "Հաշվետվություն",
};

const MODULE_FILTER_OPTIONS = [
  "", "auth", "user", "customer", "product", "variant",
  "material", "stock_movement", "order", "production_batch",
  "production_stage", "report",
];

function summarize(log: ActivityLog): string {
  if (log.details) return log.details;
  if (log.old_values && log.new_values) {
    const changed: string[] = [];
    for (const k of Object.keys(log.new_values)) {
      const oldV = (log.old_values as Record<string, unknown>)[k];
      const newV = (log.new_values as Record<string, unknown>)[k];
      if (JSON.stringify(oldV) !== JSON.stringify(newV)) {
        changed.push(`${k}: ${JSON.stringify(oldV)} → ${JSON.stringify(newV)}`);
      }
    }
    if (changed.length) return changed.join(" · ");
  }
  if (log.new_values) {
    return Object.entries(log.new_values)
      .map(([k, v]) => `${k}: ${JSON.stringify(v)}`)
      .join(" · ");
  }
  return "—";
}

export default async function ActivityPage({
  searchParams,
}: {
  searchParams: Promise<{
    page?: string;
    entity_type?: string;
    action?: string;
    user_id?: string;
    from_date?: string;
    to_date?: string;
  }>;
}) {
  await requireAdmin();
  const params = await searchParams;
  const page = parseInt(params.page || "1");

  const qs = new URLSearchParams();
  qs.set("page", String(page));
  qs.set("limit", "30");
  if (params.entity_type) qs.set("entity_type", params.entity_type);
  if (params.action) qs.set("action", params.action);
  if (params.user_id) qs.set("user_id", params.user_id);
  if (params.from_date) qs.set("from_date", params.from_date);
  if (params.to_date) qs.set("to_date", params.to_date);

  const data = await serverGet<PaginatedResponse<ActivityLog>>(`/activity-logs?${qs.toString()}`);
  const items = data?.items ?? [];
  const total = data?.total ?? 0;
  const totalPages = Math.max(1, Math.ceil(total / 30));

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-gray-900">Գործողությունների պատմություն</h1>
        <span className="text-sm text-gray-500">Ընդամենը՝ {total}</span>
      </div>

      <Card className="mb-4">
        <CardContent className="py-4">
          <form method="get" className="grid grid-cols-1 md:grid-cols-5 gap-3">
            <div>
              <label className="block text-xs text-gray-600 mb-1">Մոդուլ</label>
              <select
                name="entity_type"
                defaultValue={params.entity_type || ""}
                className="w-full text-sm rounded border border-gray-300 px-2 py-1.5 bg-white"
              >
                {MODULE_FILTER_OPTIONS.map((m) => (
                  <option key={m || "_all"} value={m}>
                    {m ? (MODULE_LABELS[m] || m) : "Բոլորը"}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-xs text-gray-600 mb-1">Գործողություն</label>
              <input
                type="text"
                name="action"
                defaultValue={params.action || ""}
                placeholder="օր.՝ order.created"
                className="w-full text-sm rounded border border-gray-300 px-2 py-1.5 bg-white"
              />
            </div>
            <div>
              <label className="block text-xs text-gray-600 mb-1">Օգտատեր ID</label>
              <input
                type="number"
                name="user_id"
                defaultValue={params.user_id || ""}
                className="w-full text-sm rounded border border-gray-300 px-2 py-1.5 bg-white"
              />
            </div>
            <div>
              <label className="block text-xs text-gray-600 mb-1">Սկիզբ</label>
              <input
                type="date"
                name="from_date"
                defaultValue={params.from_date || ""}
                className="w-full text-sm rounded border border-gray-300 px-2 py-1.5 bg-white"
              />
            </div>
            <div>
              <label className="block text-xs text-gray-600 mb-1">Ավարտ</label>
              <input
                type="date"
                name="to_date"
                defaultValue={params.to_date || ""}
                className="w-full text-sm rounded border border-gray-300 px-2 py-1.5 bg-white"
              />
            </div>
            <div className="md:col-span-5 flex gap-2 justify-end pt-1">
              <Link
                href="/dashboard/activity"
                className="px-3 py-1.5 text-sm rounded-lg border text-gray-600 border-gray-300 hover:bg-gray-50"
              >
                Մաքրել
              </Link>
              <button
                type="submit"
                className="px-3 py-1.5 text-sm rounded-lg bg-brand-800 text-white border border-brand-800 hover:bg-brand-900"
              >
                Կիրառել
              </button>
            </div>
          </form>
        </CardContent>
      </Card>

      <Card>
        <CardContent className="p-0">
          <table className="min-w-full divide-y divide-gray-200">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Ամսաթիվ</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Օգտատեր</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Գործողություն</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Մոդուլ</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">ID</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Մանրամասներ</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">IP</th>
              </tr>
            </thead>
            <tbody className="bg-white divide-y divide-gray-200">
              {items.length === 0 && (
                <tr>
                  <td colSpan={7} className="px-4 py-12 text-center text-gray-500 text-sm">
                    Գրառումներ չեն գտնվել
                  </td>
                </tr>
              )}
              {items.map((log) => (
                <tr key={log.id} className="hover:bg-gray-50 align-top">
                  <td className="px-4 py-3 text-sm text-gray-700 whitespace-nowrap">
                    {formatDateTime(log.created_at)}
                  </td>
                  <td className="px-4 py-3 text-sm text-gray-700 whitespace-nowrap">
                    {log.user_email || "—"}
                  </td>
                  <td className="px-4 py-3 text-sm text-gray-900">
                    <div>{ACTION_LABELS[log.action] || log.action}</div>
                    <div className="text-xs text-gray-400">{log.action}</div>
                  </td>
                  <td className="px-4 py-3 text-sm text-gray-700">
                    {MODULE_LABELS[log.entity_type] || log.entity_type}
                  </td>
                  <td className="px-4 py-3 text-sm text-gray-600">{log.entity_id ?? "—"}</td>
                  <td className="px-4 py-3 text-sm text-gray-700 break-words max-w-xl">
                    {summarize(log)}
                  </td>
                  <td className="px-4 py-3 text-sm text-gray-500 whitespace-nowrap">
                    {log.ip_address || "—"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </CardContent>
      </Card>

      {totalPages > 1 && (
        <div className="flex items-center justify-between mt-4 text-sm text-gray-600">
          <span>Էջ {page} / {totalPages}</span>
          <div className="flex gap-2">
            {page > 1 && (
              <Link
                href={{ pathname: "/dashboard/activity", query: { ...params, page: page - 1 } }}
                className="px-3 py-1.5 rounded border border-gray-300 hover:bg-gray-50"
              >
                Նախորդ
              </Link>
            )}
            {page < totalPages && (
              <Link
                href={{ pathname: "/dashboard/activity", query: { ...params, page: page + 1 } }}
                className="px-3 py-1.5 rounded border border-gray-300 hover:bg-gray-50"
              >
                Հաջորդ
              </Link>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
