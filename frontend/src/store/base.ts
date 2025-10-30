// src/store/base.ts - FIXED VERSION
// Enhanced Store Utilities with more functionality

// Declare the global showNotification function from base.js
declare function showNotification(
  message: string,
  type?: 'info' | 'success' | 'warning' | 'error',
  duration?: number
): void;

// Import types
interface ApiResponse<T> {
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

interface CartUpdateEvent extends CustomEvent {
  detail: {
    cart_total_items: number;
    cart_total_price: number;
    message: string;
    success: boolean;
    item?: any;
    action: 'add' | 'remove' | 'update' | 'clear';
  };
}

interface WishlistEvent extends CustomEvent {
  detail: {
    product: any;
    action: 'add' | 'remove';
  };
}

export class StoreUtils {
  // URL manipulation
  public static updateQueryStringParameter(url: string, key: string, value: string): string {
    const urlObj = new URL(url, window.location.origin);
    urlObj.searchParams.set(key, value);
    return urlObj.toString();
  }

  public static removeQueryStringParameter(url: string, key: string): string {
    const urlObj = new URL(url, window.location.origin);
    urlObj.searchParams.delete(key);
    return urlObj.toString();
  }

  public static getQueryStringParameter(url: string, key: string): string | null {
    const urlObj = new URL(url, window.location.origin);
    return urlObj.searchParams.get(key);
  }

  public static buildQueryString(params: Record<string, any>): string {
    const searchParams = new URLSearchParams();
    Object.entries(params).forEach(([key, value]) => {
      if (value !== null && value !== undefined && value !== '') {
        searchParams.append(key, String(value));
      }
    });
    return searchParams.toString();
  }

  // Enhanced debounce with immediate execution option
  public static debounce<T extends (...args: any[]) => void>(
    func: T,
    wait: number,
    immediate: boolean = false
  ): (...args: Parameters<T>) => void {
    let timeout: number | undefined;

    return (...args: Parameters<T>) => {
      const later = () => {
        timeout = undefined;
        if (!immediate) func.apply(this, args);
      };

      const callNow = immediate && !timeout;
      clearTimeout(timeout);
      timeout = window.setTimeout(later, wait);

      if (callNow) func.apply(this, args);
    };
  }

  // Throttle function
  public static throttle<T extends (...args: any[]) => void>(
    func: T,
    limit: number
  ): (...args: Parameters<T>) => void {
    let inThrottle: boolean;

    return (...args: Parameters<T>) => {
      if (!inThrottle) {
        func.apply(this, args);
        inThrottle = true;
        setTimeout(() => inThrottle = false, limit);
      }
    };
  }

  // Formatting utilities
  public static formatPrice(price: number, currency: string = 'KES'): string {
    return new Intl.NumberFormat('en-KE', {
      style: 'currency',
      currency: currency,
      minimumFractionDigits: 0,
      maximumFractionDigits: 0,
    }).format(price);
  }

  public static formatNumber(number: number): string {
    return new Intl.NumberFormat('en-KE').format(number);
  }

  public static formatDate(date: Date | string, options: Intl.DateTimeFormatOptions = {}): string {
    const defaultOptions: Intl.DateTimeFormatOptions = {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      ...options
    };
    return new Intl.DateTimeFormat('en-KE', defaultOptions).format(new Date(date));
  }

  // Storage utilities with expiration
  public static setStorage(key: string, value: any, expirationMinutes?: number): void {
    try {
      const item = {
        value,
        timestamp: expirationMinutes ? Date.now() + (expirationMinutes * 60 * 1000) : null
      };
      localStorage.setItem(key, JSON.stringify(item));
    } catch (e) {
      console.warn('Local storage not available:', e);
    }
  }

  public static getStorage<T>(key: string): T | null {
    try {
      const item = localStorage.getItem(key);
      if (!item) return null;

      const parsed = JSON.parse(item);
      if (parsed.timestamp && Date.now() > parsed.timestamp) {
        localStorage.removeItem(key);
        return null;
      }

      return parsed.value;
    } catch (e) {
      console.warn('Error reading from storage:', e);
      return null;
    }
  }

  public static removeStorage(key: string): void {
    try {
      localStorage.removeItem(key);
    } catch (e) {
      console.warn('Error removing from storage:', e);
    }
  }

  // CSRF token management
  public static getCSRFToken(): string {
    const csrfToken = document.querySelector('[name=csrfmiddlewaretoken]') as HTMLInputElement;
    return csrfToken ? csrfToken.value : '';
  }

  // API request utility
  public static async apiRequest<T>(
    url: string,
    options: RequestInit = {}
  ): Promise<ApiResponse<T>> {
    const defaultOptions: RequestInit = {
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': this.getCSRFToken(),
        ...options.headers,
      },
    };

    try {
      const response = await fetch(url, { ...defaultOptions, ...options });
      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.error || 'Request failed');
      }

      return data;
    } catch (error) {
      console.error('API request failed:', error);
      return {
        success: false,
        error: error instanceof Error ? error.message : 'Unknown error occurred'
      };
    }
  }

  // DOM utilities
  public static createElement<T extends HTMLElement>(
    tag: string,
    attributes: Record<string, string> = {},
    children: (HTMLElement | string)[] = []
  ): T {
    const element = document.createElement(tag) as T;

    Object.entries(attributes).forEach(([key, value]) => {
      if (key === 'className') {
        element.className = value;
      } else {
        element.setAttribute(key, value);
      }
    });

    children.forEach(child => {
      if (typeof child === 'string') {
        element.appendChild(document.createTextNode(child));
      } else {
        element.appendChild(child);
      }
    });

    return element;
  }

  // Animation utilities
  public static animateElement(
    element: HTMLElement,
    animation: string,
    duration: number = 300
  ): Promise<void> {
    return new Promise((resolve) => {
      element.style.animation = `${animation} ${duration}ms`;
      setTimeout(() => {
        element.style.animation = '';
        resolve();
      }, duration);
    });
  }

  // Validation utilities
  public static validateEmail(email: string): boolean {
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    return emailRegex.test(email);
  }

  public static validatePhone(phone: string): boolean {
    const phoneRegex = /^\+?[\d\s-()]{10,}$/;
    return phoneRegex.test(phone);
  }

  // Performance monitoring
  public static measurePerformance<T>(fn: () => T, name: string): T {
    const start = performance.now();
    const result = fn();
    const end = performance.now();
    console.log(`${name} took ${end - start}ms`);
    return result;
  }
}

// ✅ FIXED: Enhanced Cart Manager with GLOBAL duplicate notification prevention
export class CartManager {
  private static instance: CartManager;
  private cartCountElements: NodeListOf<HTMLElement>;
  private cartLink: HTMLElement | null;
  private wishlist: Set<number> = new Set();
  private static lastNotificationTime: number = 0; // ✅ Made static (global)
  private static notificationDebounceMs: number = 300; // ✅ Increased to 300ms
  private static isNotifying: boolean = false; // ✅ New: Prevent concurrent notifications

  private constructor() {
    this.cartCountElements = document.querySelectorAll('.cart-count, #cart-count, #mobile-cart-count');
    this.cartLink = document.getElementById('cart-link');
    this.loadWishlist();
    this.bindEvents();
    console.log('🛒 CartManager initialized');
  }

  public static getInstance(): CartManager {
    if (!CartManager.instance) {
      CartManager.instance = new CartManager();
    }
    return CartManager.instance;
  }

  private bindEvents(): void {
    // ✅ NUCLEAR OPTION: Remove any existing cart update listeners first
    // This prevents duplicate listeners if getInstance() is called multiple times
    const existingListener = (this as any)._cartUpdateListener;
    if (existingListener) {
      document.body.removeEventListener('htmx:afterRequest', existingListener);
      console.log('🧹 Removed existing HTMX listener');
    }

    // Create and store the bound listener
    const boundListener = this.handleCartUpdate.bind(this) as EventListener;
    (this as any)._cartUpdateListener = boundListener;

    // HTMX cart updates (only one listener now)
    document.body.addEventListener('htmx:afterRequest', boundListener);
    console.log('✅ Cart HTMX listener registered');

    // Wishlist events
    document.addEventListener('wishlist:toggle', ((event: WishlistEvent) => {
      this.toggleWishlist(event.detail.product);
    }) as EventListener);
  }

  private handleCartUpdate(event: Event): void {
    const customEvent = event as CustomEvent;
    const target = customEvent.target as HTMLElement;
    const form = target.closest('.add-to-cart-form');

    if (form && customEvent.detail && customEvent.detail.xhr.status === 200) {
      console.log('🔔 Cart update detected');
      try {
        const response = JSON.parse(customEvent.detail.xhr.responseText);

        if (response.success) {
            this.updateCartCount(response.cart_total_items);
            this.showDebouncedNotification(response.message, 'success');

            // Dispatch custom event for analytics
            this.dispatchCartEvent('add', response.cart_item);
        } else {
            // Check for "already in cart" message to show a warning instead of an error
            if (response.message === 'Product is already in your cart') {
              this.showDebouncedNotification(response.message, 'warning');
            } else {
              this.showDebouncedNotification(response.message, 'error');
            }
        }

      } catch (e) {
        console.error('Error parsing cart response:', e, customEvent.detail.xhr.responseText);
        this.showDebouncedNotification('An error occurred while updating cart.', 'error');
      }
    }
  }

  // ✅ ENHANCED: Global debounced notification with locking mechanism
  private showDebouncedNotification(message: string, type: 'success' | 'error' | 'warning' | 'info'): void {
    const now = Date.now();

    console.log('📬 Notification requested:', {
      message,
      type,
      timeSinceLastNotification: now - CartManager.lastNotificationTime,
      isCurrentlyNotifying: CartManager.isNotifying,
      willShow: !CartManager.isNotifying && (now - CartManager.lastNotificationTime >= CartManager.notificationDebounceMs)
    });

    // ✅ Check if we're already showing a notification
    if (CartManager.isNotifying) {
      console.log('⏭️  Notification skipped: Already showing a notification');
      return;
    }

    // ✅ Check if enough time has passed since last notification
    if (now - CartManager.lastNotificationTime < CartManager.notificationDebounceMs) {
      console.log('⏭️  Notification debounced:', message);
      return;
    }

    // ✅ Lock the notification system
    CartManager.isNotifying = true;
    CartManager.lastNotificationTime = now;

    // Show the notification
    showNotification(message, type);
    console.log('✅ Notification shown:', message);

    // ✅ Unlock after a brief delay
    setTimeout(() => {
      CartManager.isNotifying = false;
      console.log('🔓 Notification system unlocked');
    }, 100);
  }

  public updateCartCount(count: number): void {
    this.cartCountElements.forEach(el => {
      el.textContent = count.toString();
      el.classList.add('pulse');
      setTimeout(() => el.classList.remove('pulse'), 300);
    });

    // Animate cart icon
    if (this.cartLink) {
      this.cartLink.style.transform = 'scale(1.2)';
      setTimeout(() => {
        if (this.cartLink) {
          this.cartLink.style.transform = 'scale(1)';
        }
      }, 300);
    }
  }

  // Wishlist functionality
  public toggleWishlist(product: any): void {
    if (this.wishlist.has(product.id)) {
      this.wishlist.delete(product.id);
      this.showDebouncedNotification('Removed from wishlist', 'info');
    } else {
      this.wishlist.add(product.id);
      this.showDebouncedNotification('Added to wishlist', 'success');
    }

    this.saveWishlist();
    this.updateWishlistUI();

    // Dispatch wishlist event
    document.dispatchEvent(new CustomEvent('wishlist:updated', {
      detail: {
        product,
        action: this.wishlist.has(product.id) ? 'add' : 'remove'
      }
    }));
  }

  public isInWishlist(productId: number): boolean {
    return this.wishlist.has(productId);
  }

  private loadWishlist(): void {
    const saved = StoreUtils.getStorage<number[]>('wishlist');
    if (saved) {
      this.wishlist = new Set(saved);
    }
  }

  private saveWishlist(): void {
    StoreUtils.setStorage('wishlist', Array.from(this.wishlist));
  }

  private updateWishlistUI(): void {
    document.querySelectorAll('.wishlist-btn').forEach(btn => {
      const productId = parseInt(btn.getAttribute('data-product-id') || '0');
      if (this.wishlist.has(productId)) {
        btn.classList.add('active');
        btn.innerHTML = '<i class="fas fa-heart"></i>';
      } else {
        btn.classList.remove('active');
        btn.innerHTML = '<i class="far fa-heart"></i>';
      }
    });
  }

  // Analytics events
  private dispatchCartEvent(action: string, item?: any): void {
    const event = new CustomEvent('analytics:cart', {
      detail: {
        type: 'cart_interaction',
        data: { action, item, timestamp: Date.now() }
      }
    });
    document.dispatchEvent(event);
  }

  // Quick add to cart
  public quickAdd(productId: number, quantity: number = 1): void {
    const formData = new FormData();
    formData.append('product_id', productId.toString());
    formData.append('quantity', quantity.toString());
    formData.append('csrfmiddlewaretoken', StoreUtils.getCSRFToken());

    fetch('/cart/add/', {
      method: 'POST',
      body: formData,
      headers: {
        'X-Requested-With': 'XMLHttpRequest'
      }
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            this.updateCartCount(data.cart_total_items);
            this.showDebouncedNotification(data.message, 'success');
        } else {
            this.showDebouncedNotification(data.message, 'error');
        }
    })
    .catch(error => {
        console.error('Quick add failed:', error);
        this.showDebouncedNotification('Failed to add item to cart', 'error');
    });
  }
}

// Initialize cart manager (singleton - only runs once)
export const cartManager = CartManager.getInstance();

// ✅ Log to confirm single initialization
console.log('✅ base.ts loaded - CartManager singleton created');

// Export as default for module compatibility
export default {
  CartManager,
  cartManager,
  StoreUtils
};