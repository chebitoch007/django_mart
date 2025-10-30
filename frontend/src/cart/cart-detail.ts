// Enhanced Cart functionality with animations and microinteractions
import './cart-detail.css';

interface CartUpdateResponse {
    success: boolean;
    item_total: string; // numeric string (Money.amount)
    cart_total_price: string; // numeric string (Money.amount)
    cart_total_items: number;
    product_stock: number;
    item_quantity: number;
    message?: string;
}

interface CartItemElement extends HTMLElement {
    dataset: {
        productId: string;
        updateUrl: string;
        stock: string;
    };
}

// Toast notification interface
interface ToastOptions {
    message: string;
    type: 'success' | 'error' | 'warning';
    duration?: number;
}

class CartManager {
    private csrfToken: string;
    private activeRequests: Set<string> = new Set();
    private toastContainer: HTMLElement | null = null;
    private currencySymbol: string = 'KES '; // Default fallback, dynamically updated

    constructor() {
        console.log('🛒 CartManager initialized');
        this.csrfToken = this.getCSRFToken();
        this.detectCurrencySymbol();
        this.initToastContainer();
        this.initEventListeners();
        this.initStickyCheckoutBar();
    }

    // Detect currency prefix (e.g. "KES", "USD") from subtotal DOM element
    private detectCurrencySymbol(): void {
        const subtotal = document.getElementById('cart-subtotal')?.textContent || '';
        const match = subtotal.match(/[A-Z]{3}/);
        if (match) {
            this.currencySymbol = `${match[0]} `;
            console.log(`💱 Detected currency: ${this.currencySymbol}`);
        } else {
            console.warn('⚠️ No currency code detected, using default KES');
        }
    }

    private getCSRFToken(): string {
        const tokenElement = document.querySelector('[name=csrfmiddlewaretoken]') as HTMLInputElement;
        if (!tokenElement) {
            console.warn('⚠️ CSRF token not found');
            throw new Error('CSRF token not found');
        }
        return tokenElement.value;
    }

    private initToastContainer(): void {
        this.toastContainer = document.createElement('div');
        this.toastContainer.className = 'toast-container';
        this.toastContainer.setAttribute('aria-live', 'polite');
        this.toastContainer.setAttribute('aria-atomic', 'true');
        document.body.appendChild(this.toastContainer);
    }

    private initStickyCheckoutBar(): void {
        const cartTotal = document.getElementById('cart-total')?.textContent || `${this.currencySymbol}0`;
        const hasItems = document.querySelectorAll('.cart-card').length > 0;

        if (!hasItems) return;

        const stickyBar = document.createElement('div');
        stickyBar.className = 'sticky-checkout-bar';
        stickyBar.innerHTML = `
            <div class="sticky-checkout-content">
                <div class="sticky-total">
                    <span class="sticky-label">Total:</span>
                    <span class="sticky-amount" id="sticky-cart-total">${cartTotal}</span>
                </div>
                <button type="button" class="sticky-checkout-btn" onclick="document.querySelector('.checkout-btn')?.click()">
                    Checkout
                </button>
            </div>
        `;
        document.body.appendChild(stickyBar);
    }

    private initEventListeners(): void {
        console.log('🎯 Initializing event listeners');

        // Quantity buttons
        document.querySelectorAll('.quantity-btn').forEach(button => {
            button.addEventListener('click', (e) => this.handleQuantityButtonClick(e));
        });

        // Quantity input changes
        document.querySelectorAll('.quantity-input').forEach(input => {
            input.addEventListener('change', (e) => this.handleQuantityInputChange(e));
        });

        // Remove item forms
        document.querySelectorAll('.cart-remove-form').forEach(form => {
            form.addEventListener('submit', (e) => this.handleRemoveItem(e));
        });

        console.log('✅ Event listeners initialized');
    }

    // -------------------
    // Quantity + Updates
    // -------------------
    private handleQuantityButtonClick(event: Event): void {
        const button = event.currentTarget as HTMLButtonElement;
        const form = button.closest('.quantity-form') as HTMLDivElement | null;
        const input = form?.querySelector('.quantity-input') as HTMLInputElement | null;
        const row = button.closest('.cart-card') as HTMLElement | null;

        if (!input || !row) {
            console.warn('⚠️ Could not find input or row for quantity button');
            return;
        }

        let newQuantity = parseInt(input.value) || 1;

        if (button.classList.contains('increase')) {
            newQuantity++;
        } else if (button.classList.contains('decrease') && newQuantity > 1) {
            newQuantity--;
        }

        input.value = newQuantity.toString();

        // Get productId using getAttribute for reliability
        const productId = row.getAttribute('data-product-id');
        if (!productId) {
            console.error('❌ productId missing on cart row (data-product-id)');
            console.log('Row element:', row);
            return;
        }

        console.log(`📦 Updating product ${productId} to quantity ${newQuantity}`);

        this.updateCartItem(productId, newQuantity, input, row).catch(err => {
            console.error('❌ updateCartItem failed:', err);
        });
    }

    private handleQuantityInputChange(event: Event): void {
        const input = event.currentTarget as HTMLInputElement;
        const row = input.closest('.cart-card') as HTMLElement | null;

        if (!row) {
            console.warn('⚠️ Could not find row for quantity input');
            return;
        }

        let newQuantity = parseInt(input.value) || 1;

        // Validate quantity
        if (isNaN(newQuantity) || newQuantity < 1) {
            newQuantity = 1;
        }

        const maxStock = parseInt(input.max) || parseInt(row.getAttribute('data-stock') || '0');
        if (newQuantity > maxStock) {
            newQuantity = maxStock;
            this.showStockWarningDynamic(row, maxStock);
        } else {
            this.hideStockWarningDynamic(row);
        }

        input.value = newQuantity.toString();

        // Get productId using getAttribute for reliability
        const productId = row.getAttribute('data-product-id');
        if (!productId) {
            console.error('❌ productId missing on cart row (data-product-id)');
            return;
        }

        console.log(`📦 Updating product ${productId} to quantity ${newQuantity}`);

        this.updateCartItem(productId, newQuantity, input, row).catch(err => {
            console.error('❌ updateCartItem failed:', err);
            // revert to previous value if available
            input.value = input.getAttribute('data-original-value') || '1';
        });
    }

    // -------------------
    // Core cart update
    // -------------------
    private async updateCartItem(
        productId: string,
        quantity: number,
        input: HTMLInputElement,
        row: HTMLElement
    ): Promise<void> {
        // prevent multiple simultaneous updates for the same item
        if (this.activeRequests.has(productId)) {
            console.log(`⏳ Request already in progress for product ${productId}`);
            return;
        }

        this.activeRequests.add(productId);
        this.showLoadingOverlay(row);

        try {
            const updateUrl = row.getAttribute('data-update-url') || `/cart/update/${productId}/`;
            console.log(`🔄 Updating cart: URL=${updateUrl}, quantity=${quantity}`);

            const formData = new FormData();
            formData.append('quantity', quantity.toString());
            formData.append('csrfmiddlewaretoken', this.csrfToken);

            const response = await fetch(updateUrl, {
                method: 'POST',
                body: formData,
                headers: { 'X-Requested-With': 'XMLHttpRequest' }
            });

            if (!response.ok) {
                throw new Error(`HTTP ${response.status}`);
            }

            const data: CartUpdateResponse = await response.json();
            console.log('📥 Server response:', data);

            if (data.success) {
                await this.updateCartUI(data, productId, input);
                this.showToast({ message: 'Cart updated successfully', type: 'success' });
            } else if (data.message) {
                this.showToast({ message: data.message, type: 'error' });
            }
        } catch (err) {
            console.error('❌ updateCartItem failed:', err);
            this.showToast({ message: 'Error updating cart', type: 'error' });
            input.value = input.getAttribute('data-original-value') || '1';
        } finally {
            this.hideLoadingOverlay(row);
            this.activeRequests.delete(productId);
        }
    }

    // -------------------
    // UI + Animations
    // -------------------
    private async updateCartUI(data: CartUpdateResponse, productId: string, input: HTMLInputElement): Promise<void> {
        const totalElement = document.getElementById(`total-${productId}`);
        if (totalElement) {
            const oldValue = this.parsePrice(totalElement.textContent || '0');
            const newValue = parseFloat(data.item_total);
            await this.animateNumber(totalElement, oldValue, newValue, this.currencySymbol);
        }

        await this.updateCartTotals(data.cart_total_price);
        this.updateCartCount(data.cart_total_items);

        input.max = data.product_stock.toString();
        input.value = data.item_quantity.toString();
        input.setAttribute('data-original-value', data.item_quantity.toString());
    }

    private async updateCartTotals(cartTotalPrice: string): Promise<void> {
        const subtotalElement = document.getElementById('cart-subtotal');
        const totalCartElement = document.getElementById('cart-total');
        const stickyTotalElement = document.getElementById('sticky-cart-total');

        const newValue = parseFloat(cartTotalPrice);

        for (const el of [subtotalElement, totalCartElement, stickyTotalElement]) {
            if (el) {
                const oldValue = this.parsePrice(el.textContent || '0');
                await this.animateNumber(el, oldValue, newValue, this.currencySymbol);
            }
        }
    }

    private animateNumber(
        element: HTMLElement,
        start: number,
        end: number,
        prefix: string = '',
        suffix: string = ''
    ): Promise<void> {
        return new Promise((resolve) => {
            const duration = 300;
            const startTime = performance.now();
            const diff = end - start;

            const animate = (currentTime: number) => {
                const elapsed = currentTime - startTime;
                const progress = Math.min(elapsed / duration, 1);
                const easeProgress = 1 - Math.pow(1 - progress, 3);
                const current = start + diff * easeProgress;
                element.textContent = `${prefix}${this.formatNumber(Math.round(current))}${suffix}`;
                if (progress < 1) requestAnimationFrame(animate);
                else resolve();
            };

            requestAnimationFrame(animate);
        });
    }

    private parsePrice(text: string): number {
        return parseFloat(text.replace(/[^0-9.-]+/g, '')) || 0;
    }

    private formatNumber(num: number): string {
        return num.toLocaleString('en-US');
    }

    private updateCartCount(totalItems: number): void {
        const cartCountElement = document.querySelector('.cart-item-count');
        if (cartCountElement) {
            const itemText = totalItems === 1 ? 'item' : 'items';
            cartCountElement.textContent = `${totalItems} ${itemText}`;
        }
    }

    // -------------------
    // Removal + Toasters
    // -------------------
    private async handleRemoveItem(event: Event): Promise<void> {
        event.preventDefault();
        const form = event.currentTarget as HTMLFormElement;
        const row = form.closest('.cart-card') as HTMLElement;
        const productId = form.action.split('/').filter(Boolean).pop();

        if (!productId || !row) return;
        this.showLoadingOverlay(row);

        try {
            const response = await fetch(form.action, {
                method: 'POST',
                body: new FormData(form),
                headers: { 'X-Requested-With': 'XMLHttpRequest' }
            });
            const data = await response.json();

            if (data.success) {
                await this.removeCartItemRow(row, data);
                this.showToast({ message: 'Item removed from cart', type: 'success' });
            }
        } catch (error) {
            this.showToast({ message: 'Error removing item', type: 'error' });
        } finally {
            this.hideLoadingOverlay(row);
        }
    }

    private async removeCartItemRow(row: HTMLElement, data: any): Promise<void> {
        row.classList.add('removing');
        await new Promise(resolve => setTimeout(resolve, 400));
        row.remove();
        await this.updateCartTotals(data.cart_total_price);
        this.updateCartCount(data.cart_total_items);
        if (data.cart_total_items === 0) location.reload();
    }

    private showToast(options: ToastOptions): void {
        const { message, type, duration = 3000 } = options;
        if (!this.toastContainer) return;

        const toast = document.createElement('div');
        toast.className = `toast toast-${type}`;
        toast.setAttribute('role', type === 'error' ? 'alert' : 'status');
        toast.innerHTML = `
            <div class="toast-icon">${this.getToastIcon(type)}</div>
            <div class="toast-message">${message}</div>
        `;

        this.toastContainer.appendChild(toast);
        setTimeout(() => toast.classList.add('show'), 10);
        setTimeout(() => {
            toast.classList.remove('show');
            toast.classList.add('hide');
            setTimeout(() => toast.remove(), 300);
        }, duration);
    }

    private getToastIcon(type: string): string {
        const icons = {
            success: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M20 6L9 17l-5-5"/></svg>`,
            error: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <circle cx="12" cy="12" r="10"/><path d="M15 9l-6 6M9 9l6 6"/></svg>`,
            warning: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/>
                <path d="M12 9v4M12 17h.01"/></svg>`
        };
        return icons[type as keyof typeof icons] || icons.success;
    }

    // -------------------
    // Helpers (overlays, warnings)
    // -------------------
    private showLoadingOverlay(row: HTMLElement): void {
        if (row.querySelector('.loading-overlay')) return;
        const overlay = document.createElement('div');
        overlay.className = 'loading-overlay';
        overlay.innerHTML = `<div class="loading-spinner"><div class="spinner"></div></div>`;
        row.appendChild(overlay);
    }

    private hideLoadingOverlay(row: HTMLElement): void {
        const overlay = row.querySelector('.loading-overlay');
        if (overlay) overlay.remove();
    }

    private showStockWarningDynamic(row: HTMLElement, maxStock: number): void {
        const quantityControl = row.querySelector('.quantity-control');
        if (!quantityControl) return;
        if (quantityControl.querySelector('.stock-warning-dynamic')) return;
        const warning = document.createElement('div');
        warning.className = 'stock-warning-dynamic';
        warning.innerHTML = `
            <svg viewBox="0 0 24 24" fill="none" style="width:14px;height:14px;">
                <path d="M12 9v4M12 17h.01" stroke="currentColor" stroke-width="1.2"/></svg>
            Only ${maxStock} available
        `;
        quantityControl.appendChild(warning);
    }

    private hideStockWarningDynamic(row: HTMLElement): void {
        const warning = row.querySelector('.stock-warning-dynamic');
        if (warning) warning.remove();
    }
}

document.addEventListener('DOMContentLoaded', () => {
    try {
        (window as any).cartManager = new CartManager();
    } catch (error) {
        console.error('💥 Failed to initialize CartManager:', error);
    }
});