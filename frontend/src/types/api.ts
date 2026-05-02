export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  limit: number;
}

import type { UserRole } from "./models";

export interface AuthResponse {
  message: string;
  user_id: number;
  email: string;
  role: UserRole;
}

export interface ApiError {
  detail: string;
  code: string;
}

export interface DashboardStats {
  active_orders: number;
  delayed_orders: number;
  low_stock_items: number;
  production_summary: Record<string, number>;
  recent_activity: {
    id: number;
    action: string;
    entity_type: string;
    created_at: string;
  }[];
}

export interface OrderTrend {
  date: string;
  count: number;
}
