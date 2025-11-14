// Cleaned Product types - Only used types retained

export interface Product {
  id: number;
  name: string;
  slug: string;
  price: number;
  discount_price?: number;
  stock: number;
  rating: number;
  review_count: number;
  image_url: string;
  on_sale: boolean;
  available: boolean;
  get_absolute_url: string;
  get_display_price: number;
  get_discount_percentage: number;
}

export interface ProductVariant {
  id: number;
  color: string | null;
  size: string | null;
  price: number;
  quantity: number;
}

export interface Category {
  id: number;
  name: string;
  slug: string;
  product_count: number;
  get_absolute_url: string;
}

export interface CartItem {
  id: number;
  product: Product;
  quantity: number;
  total_price: number;
  variant?: ProductVariant;
}

export interface Cart {
  items: CartItem[];
  total_items: number;
  total_price: number;
  grand_total: number;
}

export interface FilterOptions {
  sort_by: string;
  max_price: number;
  min_rating: number;
  in_stock: boolean;
  category?: string;
  brand?: string;
}

export interface SortOption {
  key: string;
  name: string;
  field: string;
  direction: 'asc' | 'desc';
}

export interface SearchSuggestion {
  type: 'product' | 'category' | 'trending' | 'search' | 'brand';
  name: string;
  url: string;
  image?: string;
  price?: string;
  rating?: number;
  category?: string;
  relevance: number;
}

export interface CartUpdateEvent extends CustomEvent {
  detail: {
    cart_total_items: number;
    cart_total_price: number;
    message: string;
    success: boolean;
    item?: CartItem;
    action: 'add' | 'remove' | 'update' | 'clear';
  };
}

export interface WishlistEvent extends CustomEvent {
  detail: {
    product: Product;
    action: 'add' | 'remove';
  };
}

export interface FilterChangeEvent extends CustomEvent {
  detail: FilterOptions;
}

export interface ApiResponse<T> {
  success: boolean;
  data?: T;
  error?: string;
  message?: string;
  pagination?: {
    page: number;
    page_size: number;
    total_pages: number;
    total_count: number;
  };
}