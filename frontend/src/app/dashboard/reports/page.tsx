import { requireAdmin } from "@/lib/auth";
import { serverGet } from "@/lib/api";
import { DashboardStats, OrderTrend } from "@/types";
import { Card, CardContent, CardHeader } from "@/components/ui/Card";
import { DashboardCharts } from "../DashboardCharts";
import Link from "next/link";

export default async function ReportsPage() {
  await requireAdmin();

  const [stats, trends] = await Promise.all([
    serverGet<DashboardStats>("/reports/dashboard"),
    serverGet<OrderTrend[]>("/reports/order-trends?days=90"),
  ]);

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-gray-900">Հաշվետվություններ</h1>
        <a
          href="/api/v1/reports/export/orders"
          className="px-4 py-2 bg-brand-800 text-white text-sm font-medium rounded-lg hover:bg-brand-900"
        >
          Export Orders CSV
        </a>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
        <Card>
          <CardContent>
            <p className="text-sm text-gray-600">Ակտիվ պատվերներ</p>
            <p className="text-3xl font-bold text-blue-700 mt-1">{stats?.active_orders ?? 0}</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent>
            <p className="text-sm text-gray-600">Ուշացած պատվերներ</p>
            <p className="text-3xl font-bold text-red-700 mt-1">{stats?.delayed_orders ?? 0}</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent>
            <p className="text-sm text-gray-600">Ցածր մնացորդ ունեցող ապրանքներ</p>
            <p className="text-3xl font-bold text-orange-700 mt-1">{stats?.low_stock_items ?? 0}</p>
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader><h3 className="font-semibold">Պատվերների միտումներ (90 օր)</h3></CardHeader>
        <CardContent>
          <DashboardCharts trends={trends || []} />
        </CardContent>
      </Card>
    </div>
  );
}
