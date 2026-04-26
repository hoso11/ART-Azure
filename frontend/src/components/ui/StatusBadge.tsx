import { Badge } from "./Badge";
import { getStatusColor } from "@/lib/utils";

const LABELS: Record<string, string> = {
  "draft": "Սևագիր",
  "confirmed": "Հաստատված",
  "in_production": "Արտադրության մեջ",
  "completed": "Ավարտված",
  "cancelled": "Չեղարկված",
  "shipped": "Shipped",
  "pending": "Սպասման մեջ",
  "in_progress": "Ընթացքի մեջ",
  "normal": "Սովորական",
  "low": "Ցածր",
  "high": "Բարձր",
  "urgent": "Շտապ",
  "active": "Ակտիվ"
};

interface StatusBadgeProps {
  status: string;
}

export function StatusBadge({ status }: StatusBadgeProps) {
  const label = LABELS[status] || status.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
  return <Badge className={getStatusColor(status)}>{label}</Badge>;
}
