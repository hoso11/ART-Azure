"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/Button";
import { Modal } from "@/components/ui/Modal";
import { FormField, Input, Select } from "@/components/ui/FormField";
import { User, Customer } from "@/types";

interface EditUserFormProps {
  user: User;
  customers: Customer[];
}

export function EditUserForm({ user, customers }: EditUserFormProps) {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const [email, setEmail] = useState(user.email);
  const [password, setPassword] = useState("");
  const [role, setRole] = useState(user.role);
  const [customerId, setCustomerId] = useState(user.customer_id?.toString() || "");

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);

    try {
      const body: Record<string, unknown> = {
        email,
        role,
        customer_id: customerId ? parseInt(customerId) : null,
      };
      if (password) {
        body.password = password;
      }

      const res = await fetch(`/api/v1/users/${user.id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify(body),
      });

      if (!res.ok) {
        const data = await res.json();
        setError(data.detail || "Failed to update user");
        return;
      }

      setOpen(false);
      setPassword("");
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
        Edit User
      </Button>

      <Modal open={open} onClose={() => { setOpen(false); setPassword(""); }} title="Խմբագրել օգտատիրոջը">
        <form onSubmit={handleSubmit}>
          {error && (
            <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700">
              {error}
            </div>
          )}

          <FormField label="Email" required>
            <Input type="email" value={email} onChange={(e) => setEmail(e.target.value)} required />
          </FormField>

          <FormField label="Նոր գաղտնաբառ">
            <Input type="password" value={password} onChange={(e) => setPassword(e.target.value)} placeholder="Leave blank to keep current" minLength={8} />
          </FormField>

          <FormField label="Դեր" required>
            <Select value={role} onChange={(e) => setRole(e.target.value as User["role"])}>
              <option value="simple_user">Օգտատեր</option>
              <option value="admin">Ադմին</option>
            </Select>
          </FormField>

          <FormField label="Կապված հաճախորդ">
            <Select value={customerId} onChange={(e) => setCustomerId(e.target.value)}>
              <option value="">Կապված չէ</option>
              {customers.map((c) => (
                <option key={c.id} value={c.id}>{c.name}{c.company_name ? ` (${c.company_name})` : ""}</option>
              ))}
            </Select>
          </FormField>

          <div className="flex justify-end gap-3 mt-6">
            <Button type="button" variant="secondary" onClick={() => { setOpen(false); setPassword(""); }}>
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
