import { requireAdmin } from "@/lib/auth";
import { serverGet } from "@/lib/api.server";
import { PaginatedResponse, User, Customer } from "@/types";
import { Card, CardContent } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { formatDate } from "@/lib/utils";
import Link from "next/link";
import { CreateUserButton } from "./UserActions";

export default async function UsersPage({
  searchParams,
}: {
  searchParams: Promise<{ page?: string }>;
}) {
  await requireAdmin();
  const params = await searchParams;
  const page = parseInt(params.page || "1");

  const [data, customersData] = await Promise.all([
    serverGet<PaginatedResponse<User>>(`/users?page=${page}&limit=20`),
    serverGet<PaginatedResponse<Customer>>("/customers?limit=100"),
  ]);

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-gray-900">Օգտատերեր</h1>
        <CreateUserButton customers={customersData?.items || []} />
      </div>

      <Card>
        <CardContent className="p-0">
          <table className="min-w-full divide-y divide-gray-200">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Email</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Դեր</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Հաճախորդ</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Կարգավիճակ</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Ստեղծվել է</th>
                <th className="px-6 py-3"></th>
              </tr>
            </thead>
            <tbody className="bg-white divide-y divide-gray-200">
              {data?.items.length === 0 && (
                <tr><td colSpan={6} className="px-6 py-12 text-center text-gray-500">Օգտատերեր չեն գտնվել</td></tr>
              )}
              {data?.items.map((user) => (
                <tr key={user.id} className="hover:bg-gray-50">
                  <td className="px-6 py-4 text-sm font-medium text-gray-900">{user.email}</td>
                  <td className="px-6 py-4">
                    <Badge className={user.role === "admin" ? "bg-purple-100 text-purple-800" : "bg-blue-100 text-blue-800"}>
                      {user.role === "admin" ? "Ադմին" : "Օգտատեր"}
                    </Badge>
                  </td>
                  <td className="px-6 py-4 text-sm text-gray-600">{user.customer_id ? `#${user.customer_id}` : "—"}</td>
                  <td className="px-6 py-4">
                    <Badge className={user.is_active ? "bg-green-100 text-green-800" : "bg-gray-100 text-gray-800"}>
                      {user.is_active ? "Ակտիվ" : "Անակտիվ"}
                    </Badge>
                  </td>
                  <td className="px-6 py-4 text-sm text-gray-600">{formatDate(user.created_at)}</td>
                  <td className="px-6 py-4 text-right">
                    <Link href={`/dashboard/users/${user.id}`} className="text-brand-700 hover:underline text-sm">
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
