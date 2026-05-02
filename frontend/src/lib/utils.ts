export function formatDate(dateString: string): string {
  return new Date(dateString).toLocaleDateString("hy-AM", {
    year: "numeric",
    month: "short",
    day: "numeric",
  });
}

export function formatDateTime(dateString: string): string {
  return new Date(dateString).toLocaleString("hy-AM", {
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function formatCurrency(amount: number | string): string {
  const num = Number(amount) || 0;
  return `${new Intl.NumberFormat("hy-AM", { maximumFractionDigits: 0 }).format(Math.round(num))} ֏`;
}

export function formatNumber(value: number | string | null | undefined): string {
  if (value === null || value === undefined || value === "") return "";
  const str = String(value);
  if (!str.includes(".")) return str;
  const num = Number(value);
  if (!Number.isFinite(num)) return str;
  return num.toFixed(1);
}

export function cn(...classes: (string | boolean | undefined | null)[]): string {
  return classes.filter(Boolean).join(" ");
}

export function getStatusColor(status: string): string {
  const colors: Record<string, string> = {
    draft: "bg-gray-100 text-gray-800",
    confirmed: "bg-blue-100 text-blue-800",
    in_production: "bg-yellow-100 text-yellow-800",
    completed: "bg-green-100 text-green-800",
    shipped: "bg-purple-100 text-purple-800",
    cancelled: "bg-red-100 text-red-800",
    pending: "bg-gray-100 text-gray-800",
    in_progress: "bg-yellow-100 text-yellow-800",
    skipped: "bg-orange-100 text-orange-800",
    low: "bg-gray-100 text-gray-800",
    normal: "bg-blue-100 text-blue-800",
    high: "bg-orange-100 text-orange-800",
    urgent: "bg-red-100 text-red-800",
  };
  return colors[status] || "bg-gray-100 text-gray-800";
}

export function getPriorityColor(priority: string): string {
  return getStatusColor(priority);
}
