"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/Button";
import { Modal } from "@/components/ui/Modal";
import { FormField, Input, Select } from "@/components/ui/FormField";
import { User, Customer } from "@/types";
import type { UserRole } from "@/types/models";
import { allowedRolesFor, ROLE_LABELS } from "@/lib/permissions";

interface EditUserFormProps {
  user: User;
  customers: Customer[];
  actorRole: UserRole;
  // True when the actor is editing their own account. Disables the role
  // <Select> (backend would 403 self-role-change anyway) and surfaces a hint.
  isSelf?: boolean;
}

export function EditUserForm({ user, customers, actorRole, isSelf = false }: EditUserFormProps) {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  // Roles the actor can assign. Always include the user's *current* role so
  // editing other fields without changing the role works for users whose role
  // the actor cannot assign (e.g. director editing a simple_user is fine, but
  // can't set the role to anything else).
  const allowed = allowedRolesFor(actorRole);
  const roleOptions: UserRole[] = allowed.includes(user.role)
    ? allowed
    : [user.role, ...allowed];

  const [email, setEmail] = useState(user.email);
  const [password, setPassword] = useState("");
  const [role, setRole] = useState<UserRole>(user.role);
  const [customerId, setCustomerId] = useState(user.customer_id?.toString() || "");
  const [discountPercent, setDiscountPercent] = useState(String(user.discount_percent ?? 0));

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);

    try {
      const body: Record<string, unknown> = {
        email,
        role,
        customer_id: customerId ? parseInt(customerId) : null,
        discount_percent: parseFloat(discountPercent) || 0,
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
            <Select
              value={role}
              onChange={(e) => setRole(e.target.value as UserRole)}
              disabled={isSelf}
            >
              {roleOptions.map((r) => (
                <option key={r} value={r}>{ROLE_LABELS[r]}</option>
              ))}
            </Select>
            {isSelf && (
              <p className="mt-1 text-xs text-gray-500">
                Չեք կարող փոխել ձեր սեփական դերը
              </p>
            )}
          </FormField>

          <FormField label="Կապված հաճախորդ">
            <Select value={customerId} onChange={(e) => setCustomerId(e.target.value)}>
              <option value="">Կապված չէ</option>
              {customers.map((c) => (
                <option key={c.id} value={c.id}>{c.name}{c.company_name ? ` (${c.company_name})` : ""}</option>
              ))}
            </Select>
          </FormField>

          {role === "simple_user" && (
            <FormField label="Զեղչի տոկոս" required>
              <Input
                type="number"
                min="0"
                max="100"
                step="0.01"
                value={discountPercent}
                onChange={(e) => setDiscountPercent(e.target.value)}
                required
              />
            </FormField>
          )}

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
