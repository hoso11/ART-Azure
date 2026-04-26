"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/Button";
import { Modal } from "@/components/ui/Modal";
import { FormField, Input, Select, Textarea } from "@/components/ui/FormField";
import { Customer } from "@/types";

interface EditCustomerFormProps {
  customer: Customer;
}

export function EditCustomerForm({ customer }: EditCustomerFormProps) {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const [name, setName] = useState(customer.name);
  const [companyName, setCompanyName] = useState(customer.company_name || "");
  const [email, setEmail] = useState(customer.email || "");
  const [phone, setPhone] = useState(customer.phone || "");
  const [address, setAddress] = useState(customer.address || "");
  const [notes, setNotes] = useState(customer.notes || "");
  const [isActive, setIsActive] = useState(customer.is_active);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);

    try {
      const res = await fetch(`/api/v1/customers/${customer.id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({
          name,
          company_name: companyName || null,
          email: email || null,
          phone: phone || null,
          address: address || null,
          notes: notes || null,
          is_active: isActive,
        }),
      });

      if (!res.ok) {
        const data = await res.json();
        setError(data.detail || "Failed to update customer");
        return;
      }

      setOpen(false);
      router.refresh();
    } catch {
      setError("Connection error");
    } finally {
      setLoading(false);
    }
  };

  return (
    <>
      <Button variant="secondary" onClick={() => setOpen(true)}>
        Edit Customer
      </Button>

      <Modal open={open} onClose={() => setOpen(false)} title="Խմբագրել հաճախորդը">
        <form onSubmit={handleSubmit}>
          {error && (
            <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700">
              {error}
            </div>
          )}

          <FormField label="Անվանում" required>
            <Input value={name} onChange={(e) => setName(e.target.value)} required />
          </FormField>

          <FormField label="Ընկերություն">
            <Input value={companyName} onChange={(e) => setCompanyName(e.target.value)} />
          </FormField>

          <FormField label="Email">
            <Input type="email" value={email} onChange={(e) => setEmail(e.target.value)} />
          </FormField>

          <FormField label="Հեռախոս">
            <Input value={phone} onChange={(e) => setPhone(e.target.value)} />
          </FormField>

          <FormField label="Հասցե">
            <Input value={address} onChange={(e) => setAddress(e.target.value)} />
          </FormField>

          <FormField label="Նշումներ">
            <Textarea value={notes} onChange={(e) => setNotes(e.target.value)} />
          </FormField>

          <FormField label="Կարգավիճակ">
            <Select
              value={isActive ? "active" : "inactive"}
              onChange={(e) => setIsActive(e.target.value === "active")}
            >
              <option value="active">Ակտիվ</option>
              <option value="inactive">Անակտիվ</option>
            </Select>
          </FormField>

          <div className="flex justify-end gap-3 mt-6">
            <Button type="button" variant="secondary" onClick={() => setOpen(false)}>
              Cancel
            </Button>
            <Button type="submit" loading={loading}>
              Save Changes
            </Button>
          </div>
        </form>
      </Modal>
    </>
  );
}
