import { requireAdmin } from "@/lib/auth";
import { serverGet } from "@/lib/api";
import { Customer } from "@/types";
import { Card, CardContent, CardHeader } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { formatDate } from "@/lib/utils";
import Link from "next/link";
import { EditCustomerForm } from "../EditCustomerForm";
import { DeleteCustomerButton } from "../CustomerActions";

export default async function CustomerDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  await requireAdmin();
  const { id } = await params;
  const customer = await serverGet<Customer>(`/customers/${id}`);

  if (!customer) {
    return <div className="text-center py-12"><h1 className="text-xl font-semibold">Customer not found</h1></div>;
  }

  return (
    <div>
      <Link href="/dashboard/customers" className="text-sm text-brand-700 hover:underline">&larr; Վերադառնալ հաճախորդներ</Link>

      <div className="flex items-center justify-between mt-1 mb-6">
        <h1 className="text-2xl font-bold text-gray-900">{customer.name}</h1>
        <div className="flex gap-2">
          <EditCustomerForm customer={customer} />
          <DeleteCustomerButton customerId={customer.id} customerName={customer.name} />
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Card>
          <CardHeader><h3 className="font-semibold">Կապի տեղեկություն</h3></CardHeader>
          <CardContent>
            <dl className="space-y-3">
              <div><dt className="text-xs text-gray-500">Ընկերություն</dt><dd className="text-sm">{customer.company_name || "—"}</dd></div>
              <div><dt className="text-xs text-gray-500">Email</dt><dd className="text-sm">{customer.email || "—"}</dd></div>
              <div><dt className="text-xs text-gray-500">Հեռախոս</dt><dd className="text-sm">{customer.phone || "—"}</dd></div>
              <div><dt className="text-xs text-gray-500">Հասցե</dt><dd className="text-sm">{customer.address || "—"}</dd></div>
              <div>
                <dt className="text-xs text-gray-500">Կարգավիճակ</dt>
                <dd>
                  <Badge className={customer.is_active ? "bg-green-100 text-green-800" : "bg-gray-100 text-gray-800"}>
                    {customer.is_active ? "Ակտիվ" : "Անակտիվ"}
                  </Badge>
                </dd>
              </div>
              <div><dt className="text-xs text-gray-500">Սկսած</dt><dd className="text-sm">{formatDate(customer.created_at)}</dd></div>
            </dl>
          </CardContent>
        </Card>

        <Card>
          <CardHeader><h3 className="font-semibold">Նշումներ</h3></CardHeader>
          <CardContent>
            <p className="text-sm text-gray-700">{customer.notes || "Նշումներ չկան"}</p>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
