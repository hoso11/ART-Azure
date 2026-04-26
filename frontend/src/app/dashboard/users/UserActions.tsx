"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/Button";
import { Modal } from "@/components/ui/Modal";
import { FormField, Input, Select } from "@/components/ui/FormField";
import { Customer } from "@/types";

interface CreateUserButtonProps {
  customers: Customer[];
}

export function CreateUserButton({ customers }: CreateUserButtonProps) {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [role, setRole] = useState("simple_user");
  const [customerId, setCustomerId] = useState("");

  const resetForm = () => {
    setEmail("");
    setPassword("");
    setRole("simple_user");
    setCustomerId("");
    setError("");
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);

    try {
      const res = await fetch("/api/v1/users", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({
          email,
          password,
          role,
          is_active: true,
          customer_id: customerId ? parseInt(customerId) : null,
        }),
      });

      if (!res.ok) {
        const data = await res.json();
        setError(data.detail || "Failed to create user");
        return;
      }

      const user = await res.json();
      setOpen(false);
      resetForm();
      router.push(`/dashboard/users/${user.id}`);
      router.refresh();
    } catch {
      setError("Connection error");
    } finally {
      setLoading(false);
    }
  };

  return (
    <>
      <Button onClick={() => setOpen(true)}>Ավելացնել օգտատեր</Button>

      <Modal open={open} onClose={() => { setOpen(false); resetForm(); }} title="Ավելացնել օգտատեր">
        <form onSubmit={handleSubmit}>
          {error && (
            <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700">
              {error}
            </div>
          )}

          <FormField label="Email" required>
            <Input type="email" value={email} onChange={(e) => setEmail(e.target.value)} placeholder="user@example.com" required />
          </FormField>

          <FormField label="Գաղտնաբառ" required>
            <Input type="password" value={password} onChange={(e) => setPassword(e.target.value)} placeholder="Minimum 8 characters" required minLength={8} />
          </FormField>

          <FormField label="Դեր" required>
            <Select value={role} onChange={(e) => setRole(e.target.value)}>
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
            <Button type="button" variant="secondary" onClick={() => { setOpen(false); resetForm(); }}>
              Cancel
            </Button>
            <Button type="submit" loading={loading}>
              Create User
            </Button>
          </div>
        </form>
      </Modal>
    </>
  );
}

interface DeactivateUserButtonProps {
  userId: number;
  isActive: boolean;
}

export function DeactivateUserButton({ userId, isActive }: DeactivateUserButtonProps) {
  const router = useRouter();
  const [loading, setLoading] = useState(false);
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [error, setError] = useState("");

  const handleToggle = async () => {
    setError("");
    setLoading(true);

    try {
      const res = await fetch(`/api/v1/users/${userId}`, {
        method: isActive ? "DELETE" : "PATCH",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        ...(isActive ? {} : { body: JSON.stringify({ is_active: true }) }),
      });

      if (!res.ok && res.status !== 204) {
        const data = await res.json();
        setError(data.detail || "Operation failed");
        return;
      }

      setConfirmOpen(false);
      router.refresh();
    } catch {
      setError("Connection error");
    } finally {
      setLoading(false);
    }
  };

  return (
    <>
      <Button
        variant={isActive ? "danger" : "secondary"}
        onClick={() => setConfirmOpen(true)}
      >
        {isActive ? "Ապակտիվացնել" : "Վերակտիվացնել"}
      </Button>

      <Modal open={confirmOpen} onClose={() => setConfirmOpen(false)} title={isActive ? "Ապակտիվացնել օգտատեր" : "Վերակտիվացնել օգտատեր"}>
        {error && (
          <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700">
            {error}
          </div>
        )}
        <p className="text-sm text-gray-600 mb-6">
          {isActive
            ? "This will deactivate the user and prevent them from logging in. Are you sure?"
            : "This will reactivate the user and restore their access. Are you sure?"}
        </p>
        <div className="flex justify-end gap-3">
          <Button type="button" variant="secondary" onClick={() => setConfirmOpen(false)}>
            Cancel
          </Button>
          <Button
            variant={isActive ? "danger" : "primary"}
            onClick={handleToggle}
            loading={loading}
          >
            {isActive ? "Ապակտիվացնել" : "Վերակտիվացնել"}
          </Button>
        </div>
      </Modal>
    </>
  );
}
