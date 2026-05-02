import { requireAdmin } from "@/lib/auth";
import { serverGet } from "@/lib/api.server";
import { DashboardStats, OrderTrend, PaginatedResponse } from "@/types";
import { Customer, Material } from "@/types/models";
import { Card, CardContent, CardHeader } from "@/components/ui/Card";
import { DashboardCharts } from "../DashboardCharts";
import { ReportBuilder } from "./ReportBuilder";

export default async function ReportsPage() {
  await requireAdmin();

  const [stats, trends, customersData, materialsData] = await Promise.all([
    serverGet<DashboardStats>("/reports/dashboard"),
    serverGet<OrderTrend[]>("/reports/order-trends?days=90"),
    serverGet<PaginatedResponse<Customer>>("/customers?limit=100"),
    serverGet<PaginatedResponse<Material>>("/inventory/materials?limit=100"),
  ]);

  const customers = customersData?.items ?? [];
  const materials = materialsData?.items ?? [];

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-gray-900">Հաշվետվություններ</h1>
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

      <ReportBuilder customers={customers} materials={materials} />
    </div>
  );
}