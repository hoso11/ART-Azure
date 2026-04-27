import { requireAdmin } from "@/lib/auth";
import { serverGet } from "@/lib/api.server";
import { PaginatedResponse, Customer } from "@/types";
import { Card, CardContent } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { formatDate } from "@/lib/utils";
import Link from "next/link";
import { CreateCustomerButton } from "./CustomerActions";

export default async function CustomersPage({
  searchParams,
}: {
  searchParams: Promise<{ page?: string }>;
}) {
  await requireAdmin();
  const params = await searchParams;
  const page = parseInt(params.page || "1");

  const data = await serverGet<PaginatedResponse<Customer>>(`/customers?page=${page}&limit=20`);

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-gray-900">Հաճախորդներ</h1>
        <CreateCustomerButton />
      </div>

      <Card>
        <CardContent className="p-0">
          <table className="min-w-full divide-y divide-gray-200">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Անվանում</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Ընկերություն</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Email</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Հեռախոս</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Կարգավիճակ</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Սկսած</th>
                <th className="px-6 py-3"></th>
              </tr>
            </thead>
            <tbody className="bg-white divide-y divide-gray-200">
              {data?.items.length === 0 && (
                <tr><td colSpan={7} className="px-6 py-12 text-center text-gray-500">Հաճախորդներ չեն գտնվել</td></tr>
              )}
              {data?.items.map((customer) => (
                <tr key={customer.id} className="hover:bg-gray-50">
                  <td className="px-6 py-4 text-sm font-medium text-gray-900">{customer.name}</td>
                  <td className="px-6 py-4 text-sm text-gray-600">{customer.company_name || "—"}</td>
                  <td className="px-6 py-4 text-sm text-gray-600">{customer.email || "—"}</td>
                  <td className="px-6 py-4 text-sm text-gray-600">{customer.phone || "—"}</td>
                  <td className="px-6 py-4">
                    <Badge className={customer.is_active ? "bg-green-100 text-green-800" : "bg-gray-100 text-gray-800"}>
                      {customer.is_active ? "Ակտիվ" : "Անակտիվ"}
                    </Badge>
                  </td>
                  <td className="px-6 py-4 text-sm text-gray-600">{formatDate(customer.created_at)}</td>
                  <td className="px-6 py-4 text-right">
                    <Link href={`/dashboard/customers/${customer.id}`} className="text-brand-700 hover:underline text-sm">
                      View
                    </Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </CardContent>
      </Card>
    </div>
  );
}
