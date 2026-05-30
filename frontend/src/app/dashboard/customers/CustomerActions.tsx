"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/Button";
import { Modal } from "@/components/ui/Modal";
import { FormField, Input, Textarea } from "@/components/ui/FormField";
import { showToast } from "@/lib/toast";

export function CreateCustomerButton() {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const [name, setName] = useState("");
  const [companyName, setCompanyName] = useState("");
  const [email, setEmail] = useState("");
  const [phone, setPhone] = useState("");
  const [address, setAddress] = useState("");
  const [notes, setNotes] = useState("");

  const resetForm = () => {
    setName("");
    setCompanyName("");
    setEmail("");
    setPhone("");
    setAddress("");
    setNotes("");
    setError("");
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);

    try {
      const res = await fetch("/api/v1/customers", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({
          name,
          company_name: companyName || null,
          email: email || null,
          phone: phone || null,
          address: address || null,
          notes: notes || null,
        }),
      });

      if (!res.ok) {
        const data = await res.json();
        setError(data.detail || "Failed to create customer");
        return;
      }

      const customer = await res.json();
      setOpen(false);
      resetForm();
      router.push(`/dashboard/customers/${customer.id}`);
      router.refresh();
    } catch {
      setError("Connection error");
    } finally {
      setLoading(false);
    }
  };

  return (
    <>
      <Button onClick={() => setOpen(true)}>Ավելացնել հաճախորդ</Button>

      <Modal open={open} onClose={() => { setOpen(false); resetForm(); }} title="Ավելացնել հաճախորդ">
        <form onSubmit={handleSubmit}>
          {error && (
            <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700">
              {error}
            </div>
          )}

          <FormField label="Անվանում" required>
            <Input value={name} onChange={(e) => setName(e.target.value)} placeholder="Contact name" required />
          </FormField>

          <FormField label="Ընկերություն">
            <Input value={companyName} onChange={(e) => setCompanyName(e.target.value)} placeholder="Company name" />
          </FormField>

          <FormField label="Email">
            <Input type="email" value={email} onChange={(e) => setEmail(e.target.value)} placeholder="email@company.com" />
          </FormField>

          <FormField label="Հեռախոս">
            <Input value={phone} onChange={(e) => setPhone(e.target.value)} placeholder="+1 (555) 000-0000" />
          </FormField>

          <FormField label="Հասցե">
            <Input value={address} onChange={(e) => setAddress(e.target.value)} placeholder="Full address" />
          </FormField>

          <FormField label="Նշումներ">
            <Textarea value={notes} onChange={(e) => setNotes(e.target.value)} placeholder="Additional notes..." />
          </FormField>

          <div className="flex justify-end gap-3 mt-6">
            <Button type="button" variant="secondary" onClick={() => { setOpen(false); resetForm(); }}>
              Cancel
            </Button>
            <Button type="submit" loading={loading}>
              Create Customer
            </Button>
          </div>
        </form>
      </Modal>
    </>
  );
}

interface DeleteCustomerButtonProps {
  customerId: number;
  customerName: string;
}

export function DeleteCustomerButton({ customerId, customerName }: DeleteCustomerButtonProps) {
  const router = useRouter();
  const [loading, setLoading] = useState(false);
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [error, setError] = useState("");

  const handleDelete = async () => {
    setError("");
    setLoading(true);

    try {
      const res = await fetch(`/api/v1/customers/${customerId}`, {
        method: "DELETE",
        credentials: "include",
      });

      if (!res.ok && res.status !== 204) {
        const data = await res.json().catch(() => ({}));
        const msg = data?.detail || "Չհաջողվեց ջնջել հաճախորդը";
        setError(msg);
        showToast(msg, "error");
        return;
      }

      setConfirmOpen(false);
      showToast("Հաճախորդը արխիվացվեց", "success");
      router.push("/dashboard/customers");
      router.refresh();
    } catch {
      const msg = "Կապի սխալ. չհաջողվեց ջնջել հաճախորդը";
      setError(msg);
      showToast(msg, "error");
    } finally {
      setLoading(false);
    }
  };

  return (
    <>
      <Button variant="danger" onClick={() => setConfirmOpen(true)}>
        Delete
      </Button>

      <Modal open={confirmOpen} onClose={() => setConfirmOpen(false)} title="Ջնջել հաճախորդը">
        {error && (
          <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700">
            {error}
          </div>
        )}
        <p className="text-sm text-gray-600 mb-6">
          Are you sure you want to delete <strong>{customerName}</strong>? This will deactivate the customer record.
        </p>
        <div className="flex justify-end gap-3">
          <Button type="button" variant="secondary" onClick={() => setConfirmOpen(false)}>
            Cancel
          </Button>
          <Button variant="danger" onClick={handleDelete} loading={loading}>
            Delete Customer
          </Button>
        </div>
      </Modal>
    </>
  );
}
