"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { Card, CardContent, CardHeader } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { FormField, Input, Select, Textarea } from "@/components/ui/FormField";
import { Product, Customer } from "@/types";
import { formatCurrency } from "@/lib/utils";

export default function NewOrderPage() {
  const router = useRouter();
  const [customers, setCustomers] = useState<Customer[]>([]);
  const [products, setProducts] = useState<Product[]>([]);
  const [customerId, setCustomerId] = useState("");
  const [priority, setPriority] = useState("normal");
  const [deadline, setDeadline] = useState("");
  const [notes, setNotes] = useState("");
  const [items, setItems] = useState<{ variant_id: string; quantity: string; price: string }[]>([
    { variant_id: "", quantity: "1", price: "0" },
  ]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [noCustomerLinked, setNoCustomerLinked] = useState(false);

  useEffect(() => {
    // Try admin endpoint first; on 403 fall back to /customers/me for simple users
    fetch("/api/v1/customers?limit=100", { credentials: "include" })
      .then((r) => {
        if (r.status === 403) {
          // Simple user — fetch only their linked customer
          return fetch("/api/v1/customers/me", { credentials: "include" }).then((r2) => {
            if (r2.status === 404) {
              setNoCustomerLinked(true);
              return { items: [] };
            }
            if (!r2.ok) return { items: [] };
            return r2.json().then((customer) => ({ items: [customer] }));
          });
        }
        return r.json();
      })
      .then((d) => {
        const list = d.items || [];
        setCustomers(list);
        if (list.length === 1) {
          setCustomerId(String(list[0].id));
        }
      })
      .catch(() => {});

    fetch("/api/v1/products?limit=100", { credentials: "include" })
      .then((r) => r.json())
      .then((d) => setProducts(d.items || []))
      .catch(() => {});
  }, []);

  const allVariants = products.flatMap((p) =>
    p.variants.map((v) => ({
      id: v.id,
      label: `${p.name} — ${v.size} / ${v.color} (${formatCurrency(v.price)})`,
      price: v.price,
    }))
  );

  const addItem = () => setItems([...items, { variant_id: "", quantity: "1", price: "0" }]);
  const removeItem = (i: number) => setItems(items.filter((_, idx) => idx !== i));

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);

    try {
      const res = await fetch("/api/v1/orders", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({
          customer_id: parseInt(customerId),
          priority,
          deadline: deadline || null,
          notes: notes || null,
          items: items
            .filter((i) => i.variant_id)
            .map((i) => ({
              product_variant_id: parseInt(i.variant_id),
              quantity: parseInt(i.quantity),
              unit_price: parseFloat(i.price),
            })),
        }),
      });

      if (!res.ok) {
        const data = await res.json();
        setError(data.detail || "Failed to create order");
        return;
      }

      const order = await res.json();
      router.push(`/dashboard/orders/${order.id}`);
    } catch {
      setError("Connection error");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="max-w-3xl">
      <h1 className="text-2xl font-bold text-gray-900 mb-6">Նոր պատվեր</h1>

      <form onSubmit={handleSubmit}>
        {error && (
          <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700">
            {error}
          </div>
        )}

        <Card className="mb-6">
          <CardHeader><h3 className="font-semibold">Պատվերի մանրամասներ</h3></CardHeader>
          <CardContent>
            <FormField label="Հաճախորդ" required>
              {noCustomerLinked ? (
                <p className="text-sm text-amber-700 bg-amber-50 border border-amber-200 rounded-lg p-3">
                  Your account is not linked to a customer profile. Please contact your administrator.
                </p>
              ) : (
                <Select value={customerId} onChange={(e) => setCustomerId(e.target.value)} required>
                  <option value="">Ընտրել...</option>
                  {customers.map((c) => (
                    <option key={c.id} value={c.id}>
                      {c.name} {c.company_name ? `(${c.company_name})` : ""}
                    </option>
                  ))}
                </Select>
              )}
            </FormField>

            <div className="grid grid-cols-2 gap-4">
              <FormField label="Առաջնահերթություն">
                <Select value={priority} onChange={(e) => setPriority(e.target.value)}>
                  <option value="low">Ցածր</option>
                  <option value="normal">Սովորական</option>
                  <option value="high">Բարձր</option>
                  <option value="urgent">Շտապ</option>
                </Select>
              </FormField>

              <FormField label="Վերջնաժամկետ">
                <Input type="date" value={deadline} onChange={(e) => setDeadline(e.target.value)} />
              </FormField>
            </div>

            <FormField label="Նշումներ">
              <Textarea value={notes} onChange={(e) => setNotes(e.target.value)} placeholder="Պատվերի նշումներ..." />
            </FormField>
          </CardContent>
        </Card>

        <Card className="mb-6">
          <CardHeader>
            <div className="flex items-center justify-between">
              <h3 className="font-semibold">Պատվերի ապրանքներ</h3>
              <Button type="button" variant="secondary" size="sm" onClick={addItem}>
                Ավելացնել
              </Button>
            </div>
          </CardHeader>
          <CardContent>
            {items.map((item, i) => (
              <div key={i} className="flex gap-3 mb-3 items-end">
                <div className="flex-1">
                  <Select
                    value={item.variant_id}
                    onChange={(e) => {
                      const updated = [...items];
                      updated[i].variant_id = e.target.value;
                      const variant = allVariants.find((v) => v.id === parseInt(e.target.value));
                      if (variant) updated[i].price = variant.price.toString();
                      setItems(updated);
                    }}
                  >
                    <option value="">Ընտրել տարբերակ...</option>
                    {allVariants.map((v) => (
                      <option key={v.id} value={v.id}>{v.label}</option>
                    ))}
                  </Select>
                </div>
                <div className="w-24">
                  <Input
                    type="number"
                    min="1"
                    value={item.quantity}
                    onChange={(e) => {
                      const updated = [...items];
                      updated[i].quantity = e.target.value;
                      setItems(updated);
                    }}
                    placeholder="Qty"
                  />
                </div>
                <div className="w-28">
                  <Input
                    type="number"
                    step="0.01"
                    value={item.price}
                    onChange={(e) => {
                      const updated = [...items];
                      updated[i].price = e.target.value;
                      setItems(updated);
                    }}
                    placeholder="Price"
                  />
                </div>
                {items.length > 1 && (
                  <button
                    type="button"
                    onClick={() => removeItem(i)}
                    className="text-red-500 hover:text-red-700 pb-2"
                  >
                    Remove
                  </button>
                )}
              </div>
            ))}
          </CardContent>
        </Card>

        <div className="flex gap-3">
          <Button type="submit" loading={loading}>Ստեղծել պատվեր</Button>
          <Button type="button" variant="secondary" onClick={() => router.back()}>Չեղարկել</Button>
        </div>
      </form>
    </div>
  );
}
