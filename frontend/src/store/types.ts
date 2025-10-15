// Enhanced Product types
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
  category: Category;
  get_absolute_url: string;
  get_display_price: number;
  get_discount_percentage: number;
  tags: string[];
  specifications: Record<string, string>;
  shipping_info: ShippingInfo;
  variants?: ProductVariant[];
}

export interface ProductVariant {
  id: number;
  name: string;
  price: number;
  stock: number;
  attributes: Record<string, string>; // { color: 'red', size: 'XL' }
  image_url?: string;
}

export interface ShippingInfo {
  free_shipping: boolean;
  estimated_days: number;
  weight: number;
  dimensions: {
    length: number;
    width: number;
    height: number;
  };
}

export interface Category {
  id: number;
  name: string;
  slug: string;
  description?: string;
  image?: string;
  product_count: number;
  get_absolute_url: string;
  parent?: number;
  children?: Category[];
  metadata?: Record<string, any>;
  // Add these for enhanced functionality
  products?: Product[];
  filters?: any;
}

export interface CartItem {
  id: number;
  product: Product;
  quantity: number;
  total_price: number;
  variant?: ProductVariant;
  selected_options?: Record<string, string>;
}

export interface Cart {
  items: CartItem[];
  total_items: number;
  total_price: number;
  discount_amount: number;
  shipping_cost: number;
  tax_amount: number;
  grand_total: number;
  coupon_code?: string;
}

// Enhanced Filter types
export interface FilterOptions {
  sort_by: string;
  max_price: number;
  min_rating: number;
  in_stock: boolean;
  category?: string;
  brand?: string;
  tags?: string[];
  attributes?: Record<string, string[]>;
}

export interface SortOption {
  key: string;
  name: string;
  field: string;
  direction: 'asc' | 'desc';
}

// Enhanced Search types
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

export interface SearchResults {
  products: Product[];
  total_count: number;
  facets: SearchFacets;
  related_searches: string[];
  spelling_suggestions: string[];
}

export interface SearchFacets {
  categories: FacetItem[];
  brands: FacetItem[];
  price_ranges: PriceRangeFacet[];
  ratings: FacetItem[];
}

export interface FacetItem {
  name: string;
  value: string;
  count: number;
  selected: boolean;
}

export interface PriceRangeFacet {
  min: number;
  max: number;
  count: number;
  label: string;
}

// Enhanced Event types
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


export interface FilterChangeEvent extends CustomEvent {
  detail: FilterOptions;
}

export interface WishlistEvent extends CustomEvent {
  detail: {
    product: Product;
    action: 'add' | 'remove';
  };
}


export interface ProductViewEvent extends CustomEvent {
  detail: {
    product: Product;
    source: 'list' | 'search' | 'category' | 'related';
  };
}

// Analytics types
export interface AnalyticsEvent {
  type: string;
  data: Record<string, any>;
  timestamp: number;
}

// User preference types
export interface UserPreferences {
  currency: string;
  theme: 'light' | 'dark' | 'auto';
  notifications: {
    email: boolean;
    push: boolean;
    sms: boolean;
  };
  recently_viewed: number[]; // product IDs
  wishlist: number[]; // product IDs
}

// API Response types
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



// Form types
export interface ReviewFormData {
  rating: number;
  title: string;
  comment: string;
  recommend: boolean;
  pros?: string;
  cons?: string;
}

export interface ContactFormData {
  name: string;
  email: string;
  subject: string;
  message: string;
  type: 'general' | 'support' | 'sales' | 'complaint';
}

// Payment types
export interface PaymentMethod {
  id: string;
  name: string;
  type: 'card' | 'mobile' | 'bank' | 'digital';
  icon: string;
  supported_currencies: string[];
}

export interface PaymentIntent {
  id: string;
  amount: number;
  currency: string;
  status: 'pending' | 'succeeded' | 'failed';
  payment_method: string;
}