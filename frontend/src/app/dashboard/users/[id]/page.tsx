import { requireModule } from "@/lib/auth";
import { serverGet } from "@/lib/api.server";
import { PaginatedResponse, User, Customer } from "@/types";
import { Card, CardContent, CardHeader } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { formatDate } from "@/lib/utils";
import Link from "next/link";
import { EditUserForm } from "../EditUserForm";
import { DeactivateUserButton } from "../UserActions";
import { ROLE_LABELS } from "@/lib/permissions";

const ROLE_BADGE_CLASS: Record<string, string> = {
  admin: "bg-purple-100 text-purple-800",
  director: "bg-amber-100 text-amber-800",
  production_manager: "bg-emerald-100 text-emerald-800",
  warehouse_manager: "bg-cyan-100 text-cyan-800",
  simple_user: "bg-blue-100 text-blue-800",
};

export default async function UserDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const session = await requireModule("users");
  const { id } = await params;

  const [user, customersData] = await Promise.all([
    serverGet<User>(`/users/${id}`),
    serverGet<PaginatedResponse<Customer>>("/customers?limit=100"),
  ]);

  if (!user) {
    return <div className="text-center py-12"><h1 className="text-xl font-semibold">User not found</h1></div>;
  }

  const isSelf = user.id === session.user_id;

  return (
    <div>
      <Link href="/dashboard/users" className="text-sm text-brand-700 hover:underline">&larr; Վերադառնալ օգտատերեր</Link>

      <div className="flex items-center justify-between mt-1 mb-6">
        <h1 className="text-2xl font-bold text-gray-900">{user.email}</h1>
        <div className="flex gap-2">
          <EditUserForm
            user={user}
            customers={customersData?.items || []}
            actorRole={session.role}
            isSelf={isSelf}
          />
          {!isSelf && (
            <DeactivateUserButton userId={user.id} isActive={user.is_active} />
          )}
        </div>
      </div>

      <Card className="max-w-lg">
        <CardHeader><h3 className="font-semibold">Օգտատերի մանրամասներ</h3></CardHeader>
        <CardContent>
          <dl className="space-y-3">
            <div><dt className="text-xs text-gray-500">Email</dt><dd className="text-sm">{user.email}</dd></div>
            <div>
              <dt className="text-xs text-gray-500">Դեր</dt>
              <dd>
                <Badge className={ROLE_BADGE_CLASS[user.role] ?? "bg-gray-100 text-gray-800"}>
                  {ROLE_LABELS[user.role] ?? user.role}
                </Badge>
              </dd>
            </div>
            <div><dt className="text-xs text-gray-500">Հաճախորդի կապ</dt><dd className="text-sm">{user.customer_id ? <Link href={`/dashboard/customers/${user.customer_id}`} className="text-brand-700 hover:underline">Customer #{user.customer_id}</Link> : "Կապված չէ"}</dd></div>
            {user.role === "simple_user" && (
              <div>
                <dt className="text-xs text-gray-500">Զեղչի տոկոս</dt>
                <dd className="text-sm font-medium text-brand-800">{Number(user.discount_percent)}%</dd>
              </div>
            )}
            <div>
              <dt className="text-xs text-gray-500">Կարգավիճակ</dt>
              <dd>
                <Badge className={user.is_active ? "bg-green-100 text-green-800" : "bg-red-100 text-red-800"}>
                  {user.is_active ? "Ակտիվ" : "Անակտիվ"}
                </Badge>
              </dd>
            </div>
            <div><dt className="text-xs text-gray-500">Ստեղծվել է</dt><dd className="text-sm">{formatDate(user.created_at)}</dd></div>
          </dl>
        </CardContent>
      </Card>
    </div>
  );
}
