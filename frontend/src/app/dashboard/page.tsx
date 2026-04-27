import { requireAuth } from "@/lib/auth";
import { serverGet } from "@/lib/api.server";
import { Card, CardContent, CardHeader } from "@/components/ui/Card";
import { DashboardStats, OrderTrend } from "@/types";
import { DashboardCharts } from "./DashboardCharts";
import { StatCard } from "@/components/dashboard/StatCard";

const PRODUCTION_STATUS_LABELS: Record<string, string> = {
  pending: "Սպասման մեջ",
  in_progress: "Ընթացքի մեջ",
  completed: "Ավարտված",
};

export default async function DashboardPage() {
  const session = await requireAuth();

  if (session.role === "admin") {
    const [stats, trends] = await Promise.all([
      serverGet<DashboardStats>("/reports/dashboard"),
      serverGet<OrderTrend[]>("/reports/order-trends?days=30"),
    ]);

    return (
      <div>
        <h1 className="text-2xl font-bold text-gray-900 mb-6">Վահանակ</h1>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
          <StatCard
            label="Ակտիվ պատվերներ"
            value={stats?.active_orders ?? 0}
            color="blue"
            href="/dashboard/orders?filter=active"
          />
          <StatCard
            label="Ուշացած պատվերներ"
            value={stats?.delayed_orders ?? 0}
            color="red"
            href="/dashboard/orders?filter=delayed"
          />
          <StatCard
            label="Ցածր մնացորդ ունեցող ապրանքներ"
            value={stats?.low_stock_items ?? 0}
            color="orange"
            href="/dashboard/inventory?filter=low_stock"
          />
          <StatCard
            label="Արտադրության մեջ"
            value={stats?.production_summary?.["in_progress"] ?? 0}
            color="yellow"
            href="/dashboard/production?filter=in_progress"
          />
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <Card>
            <CardHeader>
              <h3 className="font-semibold text-gray-900">Պատվերների միտումներ (30 օր)</h3>
            </CardHeader>
            <CardContent>
              <DashboardCharts trends={trends || []} />
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <h3 className="font-semibold text-gray-900">Արտադրությունի ամփոփում</h3>
            </CardHeader>
            <CardContent>
              <div className="space-y-3">
                {stats?.production_summary && Object.entries(stats.production_summary).map(([status, count]) => (
                  <div key={status} className="flex items-center justify-between">
                    <span className="text-sm text-gray-600">{PRODUCTION_STATUS_LABELS[status] || status.replace(/_/g, " ")}</span>
                    <span className="text-sm font-semibold text-gray-900">{count}</span>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        </div>
      </div>
    );
  }

  // Simple user dashboard
  return (
    <div>
      <h1 className="text-2xl font-bold text-gray-900 mb-2">Բարի գալուստ</h1>
      <p className="text-gray-600 mb-8">
        Դիտեք մեր ապրանքները և պատվիրեք
      </p>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <QuickLink href="/catalog" title="Դիտել կատալոգ" description="Դիտեք մեր ապրանքներ" />
        <QuickLink href="/dashboard/orders" title="Իմ պատվերներ" description="Հետևեք ձեր պատվերներ" />
        <QuickLink href="/dashboard/account" title="Իմ հաշիվ" description="Տեսեք ձեր հաշիվի տվյալները" />
      </div>
    </div>
  );
}

function QuickLink({ href, title, description }: { href: string; title: string; description: string }) {
  return (
    <a href={href} className="block">
      <Card className="hover:shadow-md transition-shadow">
        <CardContent>
          <h3 className="font-semibold text-gray-900">{title}</h3>
          <p className="text-sm text-gray-500 mt-1">{description}</p>
        </CardContent>
      </Card>
    </a>
  );
}
