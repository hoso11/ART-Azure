import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import { AuthResponse } from "@/types";
import type { UserRole } from "@/types/models";
import { canAccessModule, type Module } from "@/lib/permissions";

const INTERNAL_API_URL = process.env.INTERNAL_API_URL || "http://backend:8000";

export async function getSession(): Promise<AuthResponse | null> {
  const cookieStore = await cookies();
  const accessToken = cookieStore.get("access_token")?.value;

  if (!accessToken) return null;

  try {
    const response = await fetch(`${INTERNAL_API_URL}/api/v1/auth/me`, {
      headers: { Cookie: `access_token=${accessToken}` },
      cache: "no-store",
    });

    if (!response.ok) return null;
    return response.json();
  } catch {
    return null;
  }
}

export async function requireAuth(): Promise<AuthResponse> {
  const session = await getSession();
  if (!session) {
    redirect("/login");
  }
  return session;
}

export async function requireAdmin(): Promise<AuthResponse> {
  const session = await requireAuth();
  if (session.role !== "admin") {
    redirect("/dashboard");
  }
  return session;
}

// New: whitelist by role. Use for pages that admin / director / managers
// share. Falls through to /dashboard if the actor lacks any allowed role.
export async function requireRoles(...allowed: UserRole[]): Promise<AuthResponse> {
  const session = await requireAuth();
  if (!allowed.includes(session.role)) {
    redirect("/dashboard");
  }
  return session;
}

// New: gate a page on the per-module access table (mirrors backend matrix).
export async function requireModule(module: Module): Promise<AuthResponse> {
  const session = await requireAuth();
  if (!canAccessModule(session.role, module)) {
    redirect("/dashboard");
  }
  return session;
}
