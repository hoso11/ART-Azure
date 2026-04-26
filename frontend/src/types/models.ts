export interface User {
  id: number;
  email: string;
  role: "admin" | "simple_user";
  is_active: boolean;
  customer_id: number | null;
  created_at: string;
}

export interface Customer {
  id: number;
  name: string;
  company_name: string | null;
  email: string | null;
  phone: string | null;
  address: string | null;
  notes: string | null;
  is_active: boolean;
  created_at: string;
}

export interface ProductCategory {
  id: number;
  name: string;
  description: string | null;
}

export interface ProductVariant {
  id: number;
  product_id: number;
  size: string;
  color: string;
  price: number;
  stock_quantity: number;
}

export interface ProductImage {
  id: number;
  product_id: number;
  storage_key: string;
  is_primary: boolean;
  created_at: string;
  url?: string;
}

export interface Product {
  id: number;
  name: string;
  sku: string;
  category_id: number | null;
  category: ProductCategory | null;
  description: string | null;
  technical_notes: string | null;
  is_active: boolean;
  created_at: string;
  variants: ProductVariant[];
  images: ProductImage[];
}

export interface OrderItem {
  id: number;
  order_id: number;
  product_variant_id: number;
  quantity: number;
  unit_price: number;
  notes: string | null;
}

export interface OrderCustomer {
  id: number;
  name: string;
  company_name: string | null;
  email: string | null;
  phone: string | null;
}

export interface Order {
  id: number;
  customer_id: number;
  created_by: number;
  status: string;
  priority: string;
  deadline: string | null;
  notes: string | null;
  created_at: string;
  updated_at: string;
  items: OrderItem[];
  customer: OrderCustomer | null;
}

export interface Material {
  id: number;
  name: string;
  sku: string;
  unit: string;
  low_stock_threshold: number;
  description: string | null;
  inventory: {
    id: number;
    material_id: number;
    quantity_on_hand: number;
    last_updated: string;
  } | null;
}

export interface ProductionStage {
  id: number;
  order_id: number;
  stage_name: string;
  status: string;
  assigned_to: number | null;
  started_at: string | null;
  completed_at: string | null;
  notes: string | null;
  logs: ProductionLog[];
}

export interface ProductionLog {
  id: number;
  production_stage_id: number;
  changed_by: number;
  previous_status: string;
  new_status: string;
  note: string | null;
  created_at: string;
}

export interface StockMovement {
  id: number;
  material_id: number;
  order_id: number | null;
  quantity_change: number;
  reason: string;
  created_by: number;
  created_at: string;
}

export interface ProductSizeMaterialRequirement {
  id: number;
  product_id: number;
  material_id: number;
  size: string;
  quantity_per_item: number;
  material: {
    id: number;
    name: string;
    unit: string;
  } | null;
}
