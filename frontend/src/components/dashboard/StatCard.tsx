"use client";

import { useRouter } from "next/navigation";
import { Card, CardContent } from "@/components/ui/Card";

interface StatCardProps {
  label: string;
  value: number;
  color: string;
  href?: string;
}

export function StatCard({ label, value, color, href }: StatCardProps) {
  const router = useRouter();

  const colors: Record<string, string> = {
    blue: "bg-blue-50 text-blue-700",
    red: "bg-red-50 text-red-700",
    orange: "bg-orange-50 text-orange-700",
    yellow: "bg-yellow-50 text-yellow-700",
    green: "bg-green-50 text-green-700",
  };

  const inner = (
    <Card>
      <CardContent>
        <p className="text-sm text-gray-600">{label}</p>
        <p className={`text-3xl font-bold mt-1 ${colors[color] || "text-gray-900"} bg-transparent`}>
          {value}
        </p>
      </CardContent>
    </Card>
  );

  if (!href) return inner;

  return (
    <div
      role="button"
      tabIndex={0}
      onClick={() => router.push(href)}
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          router.push(href);
        }
      }}
      className="cursor-pointer hover:shadow-md transition-shadow rounded-lg"
    >
      {inner}
    </div>
  );
}
