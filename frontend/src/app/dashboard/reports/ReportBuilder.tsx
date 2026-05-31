"use client";

import { useState } from "react";
import { Customer, Material } from "@/types";
import { formatDate, formatCurrency, formatNumber, getStatusColor } from "@/lib/utils";
import { Card, CardContent, CardHeader } from "@/components/ui/Card";

// ── Types ────────────────────────────────────────────────

type ReportType =
  | "orders"
  | "sales"
  | "inventory"
  | "material-consumption"
  | "production"
  | "low-stock"
  | "customer-discounts"
  | "damaged-stock";

type DatePreset = "today" | "7d" | "30d" | "90d" | "custom";

interface Col {
  key: string;
  label: string;
  format?: "currency" | "date" | "badge" | "bool" | "number";
}

// ── Constants ────────────────────────────────────────────

const REPORT_TYPES: { value: ReportType; label: string }[] = [
  { value: "orders", label: "Պատվերների հաշվետվություն" },
  { value: "sales", label: "Վաճառքների հաշվետվություն" },
  { value: "inventory", label: "Պահեստի հաշվետվություն" },
  { value: "material-consumption", label: "Նյութերի օգտագործման հաշվետվություն" },
  { value: "production", label: "Արտադրության հաշվետվություն" },
  { value: "low-stock", label: "Ցածր մնացորդով նյութեր" },
  { value: "customer-discounts", label: "Հաճախորդների զեղչերի հաշվետվություն" },
  { value: "damaged-stock", label: "Խոտանի հաշվետվություն" },
];

const DATE_PRESETS: { value: DatePreset; label: string }[] = [
  { value: "today", label: "Այսօր" },
  { value: "7d", label: "7 օր" },
  { value: "30d", label: "30 օր" },
  { value: "90d", label: "90 օր" },
  { value: "custom", label: "Այլն" },
];

const DATE_FILTER_REPORTS = new Set<ReportType>(["orders", "sales", "material-consumption", "production"]);
// Reports where the customer dropdown is meaningful. Orders has had it from
// the start; sales gained it for the per-customer revenue export.
const CUSTOMER_FILTER_REPORTS = new Set<ReportType>(["orders", "sales"]);

// Three active statuses only. Reports filter by these — historical orders
// stuck at deprecated statuses are still readable, but not exposed as filter
// options. See migration 011.
const ORDER_STATUSES = ["draft", "confirmed", "completed"];
const PRODUCTION_STAGES = ["cutting", "sewing", "quality_control", "packaging", "ready_for_shipment"];

const COLUMNS: Record<ReportType, Col[]> = {
  orders: [
    { key: "id", label: "ID" },
    { key: "customer_name", label: "Հաճախորդ" },
    { key: "status", label: "Կարգավիճակ", format: "badge" },
    { key: "priority", label: "Կարևորություն", format: "badge" },
    { key: "total_price", label: "Ընդհանուր գումար", format: "currency" },
    { key: "created_at", label: "Ստեղծվել է", format: "date" },
    { key: "deadline", label: "Վերջնաժամկետ", format: "date" },
  ],
  sales: [],
  inventory: [
    { key: "name", label: "Նյութ" },
    { key: "sku", label: "Արտիկուլ" },
    { key: "unit", label: "Չափման միավոր" },
    { key: "quantity_on_hand", label: "Առկա քանակ", format: "number" },
    { key: "low_stock_threshold", label: "Նվազագույն", format: "number" },
    { key: "is_low_stock", label: "Ցածր մնացորդ", format: "bool" },
  ],
  "material-consumption": [
    { key: "material_name", label: "Նյութ" },
    { key: "quantity_change", label: "Քանակի փոփոխություն", format: "number" },
    { key: "unit", label: "Չափման միավոր" },
    { key: "order_id", label: "Պատվեր" },
    { key: "reason", label: "Պատճառ", format: "badge" },
    { key: "created_at", label: "Ամսաթիվ", format: "date" },
    { key: "created_by_email", label: "Ադմին" },
  ],
  production: [
    { key: "order_id", label: "Պատվերի համար" },
    { key: "stage_name", label: "Փուլ", format: "badge" },
    { key: "status", label: "Կարգավիճակ", format: "badge" },
    { key: "started_at", label: "Սկսվել է", format: "date" },
    { key: "completed_at", label: "Ավարտվել է", format: "date" },
  ],
  "low-stock": [
    { key: "name", label: "Նյութ" },
    { key: "sku", label: "Արտիկուլ" },
    { key: "unit", label: "Չափման միավոր" },
    { key: "quantity_on_hand", label: "Առկա քանակ", format: "number" },
    { key: "low_stock_threshold", label: "Նվազագույն", format: "number" },
    { key: "missing", label: "Բացակայող", format: "number" },
  ],
  "customer-discounts": [
    { key: "email", label: "Email" },
    { key: "customer_name", label: "Հաճախորդ" },
    { key: "discount_percent", label: "Զեղչի տոկոս", format: "number" },
    { key: "total_orders", label: "Պատվերներ", format: "number" },
    { key: "total_revenue", label: "Եկամուտ", format: "currency" },
  ],
  "damaged-stock": [
    { key: "product_name", label: "Ապրանք" },
    { key: "sku", label: "SKU" },
    { key: "size", label: "Չափս" },
    { key: "color", label: "Գույն" },
    { key: "damaged_stock_quantity", label: "Խոտանի քանակ", format: "number" },
  ],
};

// ── Helpers ──────────────────────────────────────────────

function getEffectiveDates(
  preset: DatePreset,
  customStart: string,
  customEnd: string
): { start: string; end: string } {
  const today = new Date();
  const fmt = (d: Date) => d.toISOString().split("T")[0];
  if (preset === "today") return { start: fmt(today), end: fmt(today) };
  if (preset === "7d") {
    const d = new Date(today);
    d.setDate(today.getDate() - 7);
    return { start: fmt(d), end: fmt(today) };
  }
  if (preset === "30d") {
    const d = new Date(today);
    d.setDate(today.getDate() - 30);
    return { start: fmt(d), end: fmt(today) };
  }
  if (preset === "90d") {
    const d = new Date(today);
    d.setDate(today.getDate() - 90);
    return { start: fmt(d), end: fmt(today) };
  }
  return { start: customStart, end: customEnd };
}

function renderCell(value: unknown, col: Col): React.ReactNode {
  if (value === null || value === undefined || value === "")
    return <span className="text-gray-400">—</span>;

  if (col.format === "currency") return formatCurrency(Number(value));
  if (col.format === "date") return formatDate(String(value));
  if (col.format === "number") return formatNumber(value as number | string);
  if (col.format === "bool") {
    return value ? (
      <span className="text-xs font-semibold text-red-600">Ցածր</span>
    ) : (
      <span className="text-xs font-semibold text-green-600">OK</span>
    );
  }
  if (col.format === "badge") {
    return (
      <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${getStatusColor(String(value))}`}>
        {String(value).replace(/_/g, " ")}
      </span>
    );
  }
  return String(value);
}

// ── Sub-components ────────────────────────────────────────

function EmptyState() {
  return (
    <div className="text-center py-12 text-gray-500 text-sm">
      Տվյալներ չկան</div>
  );
}

interface SalesOrderItem {
  order_id: number;
  order_date: string;
  product_name: string;
  sku: string;
  size: string;
  color: string;
  quantity: number;
  unit_price: number;
  total_price: number;
}

interface SalesData {
  summary: {
    total_orders: number;
    confirmed_orders: number;
    completed_orders: number;
    total_revenue: number;
  };
  by_day: { date: string; count: number; revenue: number }[];
  by_customer: { customer_name: string; company_name: string | null; orders: number; revenue: number }[];
  selected_customer?: { id: number; name: string; company_name: string | null } | null;
  selected_order?: { id: number; order_date: string; status: string } | null;
  order_items?: SalesOrderItem[];
}

function SalesPreview({ data }: { data: SalesData }) {
  const { summary, by_day, by_customer, selected_customer, selected_order, order_items } = data;
  return (
    <div className="space-y-6">
      {selected_customer && (
        <div className="bg-brand-50 border border-brand-200 rounded-lg px-4 py-3">
          <p className="text-xs text-gray-600">Ընտրված հաճախորդ</p>
          <p className="text-sm font-semibold text-brand-900 mt-0.5">
            {selected_customer.name}
            {selected_customer.company_name && (
              <span className="text-gray-600 font-normal">
                {" · "}{selected_customer.company_name}
              </span>
            )}
          </p>
          {selected_order && (
            <p className="text-xs text-brand-800 mt-1">
              Ընտրված պատվեր: <span className="font-semibold">#{selected_order.id}</span>
              <span className="text-gray-600 font-normal">
                {" · "}{selected_order.order_date}
                {" · "}{selected_order.status}
              </span>
            </p>
          )}
        </div>
      )}

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {[
          { label: "Բոլոր պատվերներ", value: summary.total_orders, color: "text-blue-700" },
          { label: "Հաստատված", value: summary.confirmed_orders, color: "text-green-700" },
          { label: "Ավարտված", value: summary.completed_orders, color: "text-purple-700" },
          { label: "Ընդհանուր եկամուտ", value: formatCurrency(summary.total_revenue), color: "text-brand-800" },
        ].map((item) => (
          <div key={item.label} className="bg-gray-50 rounded-lg p-4">
            <p className="text-xs text-gray-500">{item.label}</p>
            <p className={`text-xl font-bold mt-1 ${item.color}`}>{item.value}</p>
          </div>
        ))}
      </div>

      {by_day.length > 0 && (
        <div>
          <h4 className="text-sm font-semibold text-gray-700 mb-2">Օրական եկամուտ</h4>
          <div className="overflow-x-auto">
            <table className="min-w-full text-sm">
              <thead>
                <tr className="border-b border-gray-200">
                  <th className="text-left py-2 pr-4 text-gray-500 font-medium">Ամսաթիվ</th>
                  <th className="text-left py-2 pr-4 text-gray-500 font-medium">Պատվերներ</th>
                  <th className="text-left py-2 text-gray-500 font-medium">Եկամուտ</th>
                </tr>
              </thead>
              <tbody>
                {by_day.map((row) => (
                  <tr key={row.date} className="border-b border-gray-100 hover:bg-gray-50">
                    <td className="py-2 pr-4">{row.date}</td>
                    <td className="py-2 pr-4">{row.count}</td>
                    <td className="py-2">{formatCurrency(row.revenue)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {by_customer.length > 0 && (
        <div>
          <h4 className="text-sm font-semibold text-gray-700 mb-2">Եկամուտ ըստ հաճախորդի</h4>
          <div className="overflow-x-auto">
            <table className="min-w-full text-sm">
              <thead>
                <tr className="border-b border-gray-200">
                  <th className="text-left py-2 pr-4 text-gray-500 font-medium">Հաճախորդ</th>
                  <th className="text-left py-2 pr-4 text-gray-500 font-medium">Ընկերություն</th>
                  <th className="text-left py-2 pr-4 text-gray-500 font-medium">Պատվերներ</th>
                  <th className="text-left py-2 text-gray-500 font-medium">Եկամուտ</th>
                </tr>
              </thead>
              <tbody>
                {by_customer.map((row, i) => (
                  <tr key={i} className="border-b border-gray-100 hover:bg-gray-50">
                    <td className="py-2 pr-4 font-medium">{row.customer_name}</td>
                    <td className="py-2 pr-4 text-gray-500">{row.company_name || "—"}</td>
                    <td className="py-2 pr-4">{row.orders}</td>
                    <td className="py-2">{formatCurrency(row.revenue)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {order_items && order_items.length > 0 && (
        <div>
          <h4 className="text-sm font-semibold text-gray-700 mb-2">Պատվերի ապրանքներ</h4>
          <div className="overflow-x-auto">
            <table className="min-w-full text-sm">
              <thead>
                <tr className="border-b border-gray-200">
                  <th className="text-left py-2 pr-4 text-gray-500 font-medium">Պատվեր #</th>
                  <th className="text-left py-2 pr-4 text-gray-500 font-medium">Ամսաթիվ</th>
                  <th className="text-left py-2 pr-4 text-gray-500 font-medium">Ապրանք</th>
                  <th className="text-left py-2 pr-4 text-gray-500 font-medium">Արտիկուլ</th>
                  <th className="text-left py-2 pr-4 text-gray-500 font-medium">Չափս</th>
                  <th className="text-left py-2 pr-4 text-gray-500 font-medium">Գույն</th>
                  <th className="text-left py-2 pr-4 text-gray-500 font-medium">Քանակ</th>
                  <th className="text-left py-2 pr-4 text-gray-500 font-medium">Միավորի գին</th>
                  <th className="text-left py-2 text-gray-500 font-medium">Ընդհանուր</th>
                </tr>
              </thead>
              <tbody>
                {order_items.map((row, i) => (
                  <tr key={i} className="border-b border-gray-100 hover:bg-gray-50">
                    <td className="py-2 pr-4 font-medium">#{row.order_id}</td>
                    <td className="py-2 pr-4">{row.order_date}</td>
                    <td className="py-2 pr-4">{row.product_name || "—"}</td>
                    <td className="py-2 pr-4 font-mono text-xs text-gray-500">{row.sku || "—"}</td>
                    <td className="py-2 pr-4">{row.size}</td>
                    <td className="py-2 pr-4">{row.color}</td>
                    <td className="py-2 pr-4">{formatNumber(row.quantity)}</td>
                    <td className="py-2 pr-4">{formatCurrency(row.unit_price)}</td>
                    <td className="py-2 font-medium">{formatCurrency(row.total_price)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {by_day.length === 0 && by_customer.length === 0 && (!order_items || order_items.length === 0) && (
        <EmptyState />
      )}
    </div>
  );
}

interface DamagedStockData {
  summary: {
    total_damaged: number;
    products_affected: number;
    variants_affected: number;
  };
  items: {
    product_id: number;
    product_name: string;
    sku: string;
    variant_id: number;
    size: string;
    color: string;
    damaged_stock_quantity: number;
  }[];
}

function DamagedStockPreview({ data }: { data: DamagedStockData }) {
  const { summary, items } = data;
  return (
    <div className="space-y-6">
      <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
        <div className="bg-red-50 border border-red-100 rounded-lg p-4">
          <p className="text-xs text-gray-600">Ընդհանուր խոտան</p>
          <p className="text-xl font-bold mt-1 text-red-700">{summary.total_damaged}</p>
        </div>
        <div className="bg-gray-50 rounded-lg p-4">
          <p className="text-xs text-gray-500">Ապրանքների քանակ</p>
          <p className="text-xl font-bold mt-1 text-gray-800">{summary.products_affected}</p>
        </div>
        <div className="bg-gray-50 rounded-lg p-4">
          <p className="text-xs text-gray-500">Տարբերակների քանակ</p>
          <p className="text-xl font-bold mt-1 text-gray-800">{summary.variants_affected}</p>
        </div>
      </div>

      {items.length === 0 ? (
        <EmptyState />
      ) : (
        <div className="overflow-x-auto">
          <table className="min-w-full text-sm">
            <thead>
              <tr className="border-b border-gray-200">
                <th className="text-left py-2 pr-4 text-xs font-medium text-gray-500">Ապրանք</th>
                <th className="text-left py-2 pr-4 text-xs font-medium text-gray-500">SKU</th>
                <th className="text-left py-2 pr-4 text-xs font-medium text-gray-500">Չափս</th>
                <th className="text-left py-2 pr-4 text-xs font-medium text-gray-500">Գույն</th>
                <th className="text-left py-2 text-xs font-medium text-gray-500">Խոտանի քանակ</th>
              </tr>
            </thead>
            <tbody>
              {items.map((row) => (
                <tr key={row.variant_id} className="border-b border-gray-100 hover:bg-gray-50">
                  <td className="py-2 pr-4 font-medium">{row.product_name}</td>
                  <td className="py-2 pr-4 text-gray-500 font-mono text-xs">{row.sku}</td>
                  <td className="py-2 pr-4">{row.size}</td>
                  <td className="py-2 pr-4">{row.color}</td>
                  <td className="py-2 text-red-700 font-semibold">{formatNumber(row.damaged_stock_quantity)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

// ── Main component ────────────────────────────────────────

export function ReportBuilder({
  customers,
  materials,
}: {
  customers: Customer[];
  materials: Material[];
}) {
  const [reportType, setReportType] = useState<ReportType>("orders");
  const [datePreset, setDatePreset] = useState<DatePreset>("30d");
  const [customStart, setCustomStart] = useState("");
  const [customEnd, setCustomEnd] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [customerFilter, setCustomerFilter] = useState("");
  const [orderFilter, setOrderFilter] = useState("");
  const [customerOrders, setCustomerOrders] = useState<{ id: number; date: string }[]>([]);
  const [materialFilter, setMaterialFilter] = useState("");
  const [stageFilter, setStageFilter] = useState("");
  const [loading, setLoading] = useState(false);
  const [reportData, setReportData] = useState<unknown>(null);
  const [error, setError] = useState("");
  const [generated, setGenerated] = useState(false);

  const hasDateFilter = DATE_FILTER_REPORTS.has(reportType);

  function buildParams(format = "json"): URLSearchParams {
    const p = new URLSearchParams({ format });
    if (hasDateFilter) {
      const { start, end } = getEffectiveDates(datePreset, customStart, customEnd);
      if (start) p.set("start_date", start);
      if (end) p.set("end_date", end);
    }
    if (reportType === "orders") {
      if (statusFilter) p.set("status", statusFilter);
    }
    if (CUSTOMER_FILTER_REPORTS.has(reportType) && customerFilter) {
      p.set("customer_id", customerFilter);
      if (reportType === "sales" && orderFilter) {
        p.set("order_id", orderFilter);
      }
    }
    if (reportType === "material-consumption" && materialFilter) {
      p.set("material_id", materialFilter);
    }
    if (reportType === "production" && stageFilter) {
      p.set("stage", stageFilter);
    }
    return p;
  }

  async function handleGenerate() {
    setError("");
    setLoading(true);
    setGenerated(false);
    setReportData(null);
    try {
      const res = await fetch(`/api/v1/reports/${reportType}?${buildParams("json")}`, {
        credentials: "include",
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        setError(err.detail || "Չհաջողվեց ստեղծել հաշվետվությունը");
        return;
      }
      const json = await res.json();
      setReportData(json);
      setGenerated(true);

      // Snapshot the customer's full order list from a customer-only sales
      // generate (no order filter). Subsequent order-filtered generates keep
      // the previous snapshot so the dropdown stays populated.
      if (
        reportType === "sales" &&
        customerFilter &&
        !orderFilter &&
        json &&
        Array.isArray(json.order_items)
      ) {
        const seen = new Map<number, string>();
        for (const it of json.order_items as SalesOrderItem[]) {
          if (!seen.has(it.order_id)) seen.set(it.order_id, it.order_date);
        }
        const next = Array.from(seen.entries())
          .map(([id, date]) => ({ id, date }))
          .sort((a, b) => b.id - a.id);
        setCustomerOrders(next);
      }
    } catch {
      setError("Կապի սխալ");
    } finally {
      setLoading(false);
    }
  }

  function handleExport() {
    window.location.href = `/api/v1/reports/${reportType}?${buildParams("csv")}`;
  }

  // Reset filters when report type changes
  function handleTypeChange(type: ReportType) {
    setReportType(type);
    setStatusFilter("");
    setCustomerFilter("");
    setOrderFilter("");
    setCustomerOrders([]);
    setMaterialFilter("");
    setStageFilter("");
    setGenerated(false);
    setReportData(null);
    setError("");
  }

  function handleCustomerChange(value: string) {
    setCustomerFilter(value);
    // Switching customer invalidates the previous customer's order list.
    setOrderFilter("");
    setCustomerOrders([]);
  }

  const rows = Array.isArray(reportData) ? (reportData as Record<string, unknown>[]) : [];
  const cols = COLUMNS[reportType];

  return (
    <Card className="mt-8">
      <CardHeader>
        <h3 className="font-semibold text-gray-900">Ստեղծել Հաշվետվություն</h3>
      </CardHeader>
      <CardContent>
        {/* ── Controls ── */}
        <div className="space-y-4">
          {/* Report type */}
          <div>
            <label className="block text-xs font-medium text-gray-600 mb-1">
Հաշվետվություն տեսակ
            </label>
            <select
              value={reportType}
              onChange={(e) => handleTypeChange(e.target.value as ReportType)}
              className="w-full md:w-80 text-sm rounded-lg border border-gray-300 px-3 py-2 bg-white focus:border-brand-500 focus:ring-1 focus:ring-brand-500"
            >
              {REPORT_TYPES.map((rt) => (
                <option key={rt.value} value={rt.value}>{rt.label}</option>
              ))}
            </select>
          </div>

          {/* Date range */}
          {hasDateFilter && (
            <div>
              <label className="block text-xs font-medium text-gray-600 mb-1">
                Ժամանակահատված
              </label>
              <div className="flex flex-wrap gap-2 mb-2">
                {DATE_PRESETS.map((p) => (
                  <button
                    key={p.value}
                    onClick={() => setDatePreset(p.value)}
                    className={`px-3 py-1.5 text-xs font-medium rounded-lg border transition-colors ${
                      datePreset === p.value
                        ? "bg-brand-800 text-white border-brand-800"
                        : "bg-white text-gray-700 border-gray-300 hover:border-brand-400"
                    }`}
                  >
                    {p.label}
                  </button>
                ))}
              </div>
              {datePreset === "custom" && (
                <div className="flex gap-3 items-center">
                  <div>
                    <label className="block text-xs text-gray-500 mb-1">սկիզբ</label>
                    <input
                      type="date"
                      value={customStart}
                      onChange={(e) => setCustomStart(e.target.value)}
                      className="text-sm rounded-lg border border-gray-300 px-3 py-1.5 focus:border-brand-500 focus:ring-1 focus:ring-brand-500"
                    />
                  </div>
                  <div>
                    <label className="block text-xs text-gray-500 mb-1">ավարտ</label>
                    <input
                      type="date"
                      value={customEnd}
                      onChange={(e) => setCustomEnd(e.target.value)}
                      className="text-sm rounded-lg border border-gray-300 px-3 py-1.5 focus:border-brand-500 focus:ring-1 focus:ring-brand-500"
                    />
                  </div>
                </div>
              )}
            </div>
          )}

          {/* Optional filters */}
          {(CUSTOMER_FILTER_REPORTS.has(reportType) || reportType === "material-consumption" || reportType === "production") && (
            <div className="flex flex-wrap gap-4">
              {reportType === "orders" && (
                <div>
                  <label className="block text-xs font-medium text-gray-600 mb-1">Կարգավիճակ</label>
                  <select
                    value={statusFilter}
                    onChange={(e) => setStatusFilter(e.target.value)}
                    className="text-sm rounded-lg border border-gray-300 px-3 py-2 bg-white focus:border-brand-500 focus:ring-1 focus:ring-brand-500"
                  >
                    <option value="">Բոլոր</option>
                    {ORDER_STATUSES.map((s) => (
                      <option key={s} value={s}>{s.replace(/_/g, " ")}</option>
                    ))}
                  </select>
                </div>
              )}
              {CUSTOMER_FILTER_REPORTS.has(reportType) && (
                <div>
                  <label className="block text-xs font-medium text-gray-600 mb-1">Հաճախորդ</label>
                  <select
                    value={customerFilter}
                    onChange={(e) => handleCustomerChange(e.target.value)}
                    className="text-sm rounded-lg border border-gray-300 px-3 py-2 bg-white focus:border-brand-500 focus:ring-1 focus:ring-brand-500"
                  >
                    <option value="">Բոլոր</option>
                    {customers.map((c) => (
                      <option key={c.id} value={c.id}>
                        {c.name}{c.company_name ? ` (${c.company_name})` : ""}
                      </option>
                    ))}
                  </select>
                </div>
              )}
              {reportType === "sales" && customerFilter && customerOrders.length > 0 && (
                <div>
                  <label className="block text-xs font-medium text-gray-600 mb-1">Պատվեր</label>
                  <select
                    value={orderFilter}
                    onChange={(e) => setOrderFilter(e.target.value)}
                    className="text-sm rounded-lg border border-gray-300 px-3 py-2 bg-white focus:border-brand-500 focus:ring-1 focus:ring-brand-500"
                  >
                    <option value="">Բոլոր պատվերները</option>
                    {customerOrders.map((o) => (
                      <option key={o.id} value={o.id}>
                        #{o.id} ({o.date})
                      </option>
                    ))}
                  </select>
                </div>
              )}
              {reportType === "material-consumption" && (
                <div>
                  <label className="block text-xs font-medium text-gray-600 mb-1">Նյութեր</label>
                  <select
                    value={materialFilter}
                    onChange={(e) => setMaterialFilter(e.target.value)}
                    className="text-sm rounded-lg border border-gray-300 px-3 py-2 bg-white focus:border-brand-500 focus:ring-1 focus:ring-brand-500"
                  >
                    <option value="">Բոլոր</option>
                    {materials.map((m) => (
                      <option key={m.id} value={m.id}>{m.name}</option>
                    ))}
                  </select>
                </div>
              )}
              {reportType === "production" && (
                <div>
                  <label className="block text-xs font-medium text-gray-600 mb-1">Արտադրության փուլ</label>
                  <select
                    value={stageFilter}
                    onChange={(e) => setStageFilter(e.target.value)}
                    className="text-sm rounded-lg border border-gray-300 px-3 py-2 bg-white focus:border-brand-500 focus:ring-1 focus:ring-brand-500"
                  >
                    <option value="">Բոլոր</option>
                    {PRODUCTION_STAGES.map((s) => (
                      <option key={s} value={s}>{s.replace(/_/g, " ")}</option>
                    ))}
                  </select>
                </div>
              )}
            </div>
          )}

          {/* Action buttons */}
          <div className="flex gap-3 pt-1">
            <button
              onClick={handleGenerate}
              disabled={loading}
              className="px-4 py-2 bg-brand-800 text-white text-sm font-medium rounded-lg hover:bg-brand-900 disabled:opacity-60 disabled:cursor-not-allowed"
            >
              {loading ? "Ստեղծվում է..." : "Ստեղծել հաշվետվություն"}
            </button>
            {generated && (
              <button
                onClick={handleExport}
                className="px-4 py-2 bg-white text-brand-800 text-sm font-medium rounded-lg border border-brand-300 hover:bg-brand-50"
              >
                Արտահանել CSV
              </button>
            )}
          </div>
        </div>

        {/* ── Error ── */}
        {error && (
          <div className="mt-4 p-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700">
            {error}
          </div>
        )}

        {/* ── Preview ── */}
        {generated && (
          <div className="mt-6 border-t border-gray-100 pt-6">
            <div className="flex items-center justify-between mb-3">
              <h4 className="text-sm font-semibold text-gray-700">
                {REPORT_TYPES.find((r) => r.value === reportType)?.label}
              </h4>
              {Array.isArray(reportData) && (
                <span className="text-xs text-gray-400">{rows.length} տող</span>
              )}
            </div>

            {reportType === "sales" ? (
              reportData ? (
                <SalesPreview data={reportData as SalesData} />
              ) : (
                <EmptyState />
              )
            ) : reportType === "damaged-stock" ? (
              reportData ? (
                <DamagedStockPreview data={reportData as DamagedStockData} />
              ) : (
                <EmptyState />
              )
            ) : rows.length === 0 ? (
              <EmptyState />
            ) : (
              <div className="overflow-x-auto">
                <table className="min-w-full text-sm">
                  <thead>
                    <tr className="border-b border-gray-200">
                      {cols.map((col) => (
                        <th
                          key={col.key}
                          className="text-left py-2 pr-4 text-xs font-medium text-gray-500 whitespace-nowrap"
                        >
                          {col.label}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {rows.map((row, i) => (
                      <tr key={i} className="border-b border-gray-100 hover:bg-gray-50">
                        {cols.map((col) => (
                          <td key={col.key} className="py-2 pr-4 whitespace-nowrap">
                            {renderCell(row[col.key], col)}
                          </td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
