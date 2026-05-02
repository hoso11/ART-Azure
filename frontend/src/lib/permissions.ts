// Single source of truth for frontend role/module visibility.
//
// **Backend is authoritative** — every API endpoint enforces authorization
// independently via FastAPI `require_roles(...)` (see
// `backend/app/dependencies.py`). This file is purely for hiding UI elements
// the user cannot use anyway, so they don't see broken pages or forbidden
// menu items.
//
// If you change anything here, change the matching backend constant in
// `backend/app/dependencies.py` (and the test matrix) at the same time.

import type { UserRole } from "@/types/models";

export type Module =
  | "dashboard"
  | "orders"
  | "production"
  | "products"
  | "inventory"
  | "customers"
  | "users"
  | "reports"
  | "activity"
  | "catalog"
  | "account";

// Mirror of backend matrix. "view" = can open the page; mutations are still
// enforced server-side per endpoint.
const MODULE_ACCESS: Record<Module, ReadonlySet<UserRole>> = {
  dashboard: new Set<UserRole>(["admin", "director", "production_manager", "warehouse_manager", "simple_user"]),
  orders: new Set<UserRole>(["admin", "director", "production_manager", "simple_user"]),
  production: new Set<UserRole>(["admin", "director", "production_manager"]),
  products: new Set<UserRole>(["admin", "director", "production_manager", "simple_user"]),
  inventory: new Set<UserRole>(["admin", "director", "warehouse_manager", "production_manager"]),
  customers: new Set<UserRole>(["admin", "director"]),
  users: new Set<UserRole>(["admin", "director"]),
  reports: new Set<UserRole>(["admin", "director", "production_manager"]),
  activity: new Set<UserRole>(["admin", "director"]),
  catalog: new Set<UserRole>(["simple_user"]),
  account: new Set<UserRole>(["simple_user"]),
};

export function canAccessModule(role: UserRole, module: Module): boolean {
  return MODULE_ACCESS[module].has(role);
}

// Whether `actor` may assign `target` as a role on a (new or existing) user.
// Mirrors `backend/app/users/service.py::can_assign_role`.
export function canAssignRole(actor: UserRole, target: UserRole): boolean {
  if (actor === "admin") return true;
  if (actor === "director") return target === "simple_user";
  return false;
}

// Roles `actor` is allowed to pick when creating or editing a user. Used to
// build the role <Select> options in the user forms.
export function allowedRolesFor(actor: UserRole): UserRole[] {
  if (actor === "admin") {
    return ["admin", "director", "production_manager", "warehouse_manager", "simple_user"];
  }
  if (actor === "director") {
    return ["simple_user"];
  }
  return [];
}

// Armenian display labels for roles.
export const ROLE_LABELS: Record<UserRole, string> = {
  admin: "Ադմին",
  director: "Տնօրեն",
  production_manager: "Արտադրության ղեկավար",
  warehouse_manager: "Պահեստապետ",
  simple_user: "Օգտատեր",
};
