import { requireAdmin } from "@/lib/auth";
import { serverGet } from "@/lib/api";
import { Order } from "@/types";
import Link from "next/link";
import { OrderEditForm } from "./OrderEditForm";

export default async function EditOrderPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  await requireAdmin();
  const { id } = await params;
  const order = await serverGet<Order>(`/orders/${id}`);

  if (!order) {
    return (
      <div className="text-center py-12">
        <h1 className="text-xl font-semibold text-gray-900">Order not found</h1>
        <Link href="/dashboard/orders" className="text-brand-700 hover:underline mt-2 inline-block">
          Վերադառնալ պատվերներին
        </Link>
      </div>
    );
  }

  return (
    <div className="max-w-3xl">
      <div className="mb-6">
        <Link href={`/dashboard/orders/${order.id}`} className="text-sm text-brand-700 hover:underline">
          &larr; Վերադառնալ պատվերին
        </Link>
        <h1 className="text-2xl font-bold text-gray-900 mt-1">Խմբագրել պատվեր #{order.id}</h1>
      </div>

      <OrderEditForm order={order} />
    </div>
  );
}
