"use client";

import { OrderTrendsChart } from "@/components/charts/OrderTrendsChart";
import { OrderTrend } from "@/types";

export function DashboardCharts({ trends }: { trends: OrderTrend[] }) {
  if (trends.length === 0) {
    return <p className="text-sm text-gray-500 text-center py-8">Տվյալներ դեռ չկան</p>;
  }
  return <OrderTrendsChart data={trends} />;
}
