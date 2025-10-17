// Enhanced Cart functionality with animations and microinteractions
import './cart-detail.css';

interface CartUpdateResponse {
    success: boolean;
    item_total: string;
    cart_total_price: string;
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

// [NEW] Toast notification interface
interface ToastOptions {
    message: string;
    type: 'success' | 'error' | 'warning';
    duration?: number;
}

class CartManager {
    private csrfToken: string;
    private activeRequests: Set<string> = new Set(); // [NEW] Track pending requests
    private toastContainer: HTMLElement | null = null; // [NEW] Toast container

    constructor() {
        console.log('🛒 CartManager initialized');
        this.csrfToken = this.getCSRFToken();
        this.initToastContainer(); // [NEW]
        this.initEventListeners();
        this.initStickyCheckoutBar(); // [NEW]
    }

    private getCSRFToken(): string {
        const tokenElement = document.querySelector('[name=csrfmiddlewaretoken]') as HTMLInputElement;
        if (!tokenElement) {
            console.warn('⚠️ CSRF token not found');
            throw new Error('CSRF token not found');
        }
        console.log('🔑 CSRF token retrieved');
        return tokenElement.value;
    }

    // [NEW] Initialize toast container
    private initToastContainer(): void {
        this.toastContainer = document.createElement('div');
        this.toastContainer.className = 'toast-container';
        this.toastContainer.setAttribute('aria-live', 'polite');
        this.toastContainer.setAttribute('aria-atomic', 'true');
        document.body.appendChild(this.toastContainer);
    }

    // [NEW] Initialize sticky checkout bar for mobile
    private initStickyCheckoutBar(): void {
        const cartTotal = document.getElementById('cart-total')?.textContent || 'KES 0';
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
            button.addEventListener('click', this.handleQuantityButtonClick.bind(this));
        });

        // Quantity input changes
        document.querySelectorAll('.quantity-input').forEach(input => {
            input.addEventListener('change', this.handleQuantityInputChange.bind(this));
        });

        // Remove item forms
        document.querySelectorAll('.cart-remove-form').forEach(form => {
            form.addEventListener('submit', this.handleRemoveItem.bind(this));
        });

        console.log('✅ Event listeners initialized');
    }

    private handleQuantityButtonClick(event: Event): void {
        const button = event.currentTarget as HTMLButtonElement;
        const form = button.closest('.quantity-form') as HTMLDivElement;
        const input = form?.querySelector('.quantity-input') as HTMLInputElement;
        const row = button.closest('.cart-card') as CartItemElement;

        if (!input || !row) {
            console.warn('⚠️ Could not find input or row for quantity button');
            return;
        }

        let newQuantity = parseInt(input.value);
        console.log(`🔄 Quantity button clicked. Current quantity: ${newQuantity}`);

        if (button.classList.contains('increase')) {
            newQuantity++;
            console.log(`➕ Increased quantity to: ${newQuantity}`);
        } else if (button.classList.contains('decrease') && newQuantity > 1) {
            newQuantity--;
            console.log(`➖ Decreased quantity to: ${newQuantity}`);
        }

        input.value = newQuantity.toString();
        this.updateCartItem(row.dataset.productId, newQuantity, input, row);
    }

    private handleQuantityInputChange(event: Event): void {
        const input = event.currentTarget as HTMLInputElement;
        const row = input.closest('.cart-card') as CartItemElement;

        if (!row) {
            console.warn('⚠️ Could not find row for quantity input');
            return;
        }

        let newQuantity = parseInt(input.value);
        console.log(`📝 Quantity input changed to: ${newQuantity}`);

        // Validate quantity
        if (isNaN(newQuantity) || newQuantity < 1) {
            newQuantity = 1;
            console.log('🛡️ Quantity normalized to minimum: 1');
        }

        const maxStock = parseInt(input.max) || parseInt(row.dataset.stock);
        if (newQuantity > maxStock) {
            newQuantity = maxStock;
            console.log(`🛡️ Quantity limited to available stock: ${maxStock}`);
            // [NEW] Show stock warning
            this.showStockWarningDynamic(row, maxStock);
        } else {
            // [NEW] Hide stock warning if quantity is valid
            this.hideStockWarningDynamic(row);
        }

        input.value = newQuantity.toString();
        this.updateCartItem(row.dataset.productId, newQuantity, input, row);
    }

    // [NEW] Show loading overlay on cart item
    private showLoadingOverlay(row: HTMLElement): void {
        if (row.querySelector('.loading-overlay')) return;

        const overlay = document.createElement('div');
        overlay.className = 'loading-overlay';
        overlay.innerHTML = `
            <div class="loading-spinner">
                <div class="spinner"></div>
            </div>
        `;
        row.appendChild(overlay);

        // Disable controls
        const input = row.querySelector('.quantity-input') as HTMLInputElement;
        const buttons = row.querySelectorAll('.quantity-btn');
        const removeBtn = row.querySelector('.cart-remove-btn') as HTMLButtonElement;

        if (input) input.disabled = true;
        buttons.forEach(btn => (btn as HTMLButtonElement).disabled = true);
        if (removeBtn) removeBtn.disabled = true;
    }

    // [NEW] Hide loading overlay
    private hideLoadingOverlay(row: HTMLElement): void {
        const overlay = row.querySelector('.loading-overlay');
        if (overlay) {
            overlay.classList.add('fade-out');
            setTimeout(() => overlay.remove(), 300);
        }

        // Re-enable controls
        const input = row.querySelector('.quantity-input') as HTMLInputElement;
        const buttons = row.querySelectorAll('.quantity-btn');
        const removeBtn = row.querySelector('.cart-remove-btn') as HTMLButtonElement;

        if (input) input.disabled = false;
        buttons.forEach(btn => (btn as HTMLButtonElement).disabled = false);
        if (removeBtn) removeBtn.disabled = false;
    }

    // [NEW] Show dynamic stock warning
    private showStockWarningDynamic(row: HTMLElement, maxStock: number): void {
        const quantityControl = row.querySelector('.quantity-control');
        if (!quantityControl) return;

        // Remove existing warning
        const existingWarning = quantityControl.querySelector('.stock-warning-dynamic');
        if (existingWarning) return;

        const warning = document.createElement('div');
        warning.className = 'stock-warning-dynamic';
        warning.setAttribute('role', 'alert');
        warning.innerHTML = `
            <svg viewBox="0 0 24 24" fill="none" aria-hidden="true" style="width:14px;height:14px;">
                <path d="M12 9v4" stroke="currentColor" stroke-width="1.2" stroke-linecap="round" stroke-linejoin="round"/>
                <path d="M12 17h.01" stroke="currentColor" stroke-width="1.2" stroke-linecap="round" stroke-linejoin="round"/>
            </svg>
            Only ${maxStock} available
        `;
        quantityControl.appendChild(warning);

        // Animate in
        setTimeout(() => warning.classList.add('show'), 10);
    }

    // [NEW] Hide dynamic stock warning
    private hideStockWarningDynamic(row: HTMLElement): void {
        const warning = row.querySelector('.stock-warning-dynamic');
        if (warning) {
            warning.classList.remove('show');
            setTimeout(() => warning.remove(), 300);
        }
    }

    private async updateCartItem(
        productId: string,
        quantity: number,
        input: HTMLInputElement,
        row: HTMLElement
    ): Promise<void> {
        console.log(`🔄 Updating cart item ${productId} to quantity ${quantity}`);

        // [NEW] Prevent duplicate requests
        if (this.activeRequests.has(productId)) {
            console.log('⏳ Request already in progress');
            return;
        }

        this.activeRequests.add(productId);
        this.showLoadingOverlay(row); // [NEW]

        try {
            const data = await this.makeCartUpdateRequest(productId, quantity);
            console.log('📦 Cart update response:', data);

            if (data.success) {
                await this.updateCartUI(data, productId, input); // [ANIM] Made async for animations
                this.showToast({ message: 'Cart updated successfully', type: 'success' }); // [NEW]
                console.log('✅ Cart UI updated successfully');
            } else if (data.message) {
                this.showToast({ message: data.message, type: 'error' }); // [NEW]
                console.warn('⚠️ Cart update warning:', data.message);
            }
        } catch (error) {
            console.error('❌ Cart update error:', error);
            this.showToast({ message: 'Error updating cart', type: 'error' }); // [NEW]
            // [NEW] Restore original value on error
            input.value = input.getAttribute('data-original-value') || '1';
        } finally {
            this.activeRequests.delete(productId);
            this.hideLoadingOverlay(row); // [NEW]
        }
    }

    private async makeCartUpdateRequest(productId: string, quantity: number): Promise<CartUpdateResponse> {
        const row = document.querySelector(`[data-product-id="${productId}"]`) as CartItemElement;
        const updateUrl = row?.dataset.updateUrl || `/cart/update/${productId}/`;

        console.log(`🌐 Making request to: ${updateUrl}`);

        const formData = new FormData();
        formData.append('quantity', quantity.toString());
        formData.append('csrfmiddlewaretoken', this.csrfToken);

        const response = await fetch(updateUrl, {
            method: 'POST',
            body: formData,
            headers: {
                'X-Requested-With': 'XMLHttpRequest'
            }
        });

        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        return await response.json();
    }

    // [ANIM] Enhanced updateCartUI with animations
    private async updateCartUI(data: CartUpdateResponse, productId: string, input: HTMLInputElement): Promise<void> {
        console.log('🎨 Updating cart UI with data:', data);

        // Update item total with animation
        const totalElement = document.getElementById(`total-${productId}`);
        if (totalElement) {
            const oldValue = this.parsePrice(totalElement.textContent || '0');
            const newValue = parseFloat(data.item_total);
            await this.animateNumber(totalElement, oldValue, newValue, 'KES ');
            console.log(`💰 Updated item total for ${productId}: KES ${data.item_total}`);
        }

        // Update cart totals with animation
        await this.updateCartTotals(data.cart_total_price);

        // Update cart count in header
        this.updateCartCount(data.cart_total_items);

        // Update max stock and input value
        input.max = data.product_stock.toString();
        input.value = data.item_quantity.toString();
        input.setAttribute('data-original-value', data.item_quantity.toString());
        console.log(`📊 Updated input max stock: ${data.product_stock}, quantity: ${data.item_quantity}`);
    }

    // [ANIM] Animate number changes
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

                // Ease out cubic
                const easeProgress = 1 - Math.pow(1 - progress, 3);
                const current = start + (diff * easeProgress);

                element.textContent = `${prefix}${this.formatNumber(Math.round(current))}${suffix}`;

                if (progress < 1) {
                    requestAnimationFrame(animate);
                } else {
                    resolve();
                }
            };

            requestAnimationFrame(animate);
        });
    }

    // [ANIM] Update cart totals with animation
    private async updateCartTotals(cartTotalPrice: string): Promise<void> {
        const subtotalElement = document.getElementById('cart-subtotal');
        const totalCartElement = document.getElementById('cart-total');
        const stickyTotalElement = document.getElementById('sticky-cart-total');

        const newValue = parseFloat(cartTotalPrice);

        if (subtotalElement) {
            const oldValue = this.parsePrice(subtotalElement.textContent || '0');
            await this.animateNumber(subtotalElement, oldValue, newValue, 'KES ');
        }

        if (totalCartElement) {
            const oldValue = this.parsePrice(totalCartElement.textContent || '0');
            await this.animateNumber(totalCartElement, oldValue, newValue, 'KES ');
        }

        if (stickyTotalElement) {
            const oldValue = this.parsePrice(stickyTotalElement.textContent || '0');
            await this.animateNumber(stickyTotalElement, oldValue, newValue, 'KES ');
        }

        console.log(`🛒 Updated cart totals: KES ${this.formatNumber(newValue)}`);
    }

    // [NEW] Parse price from formatted string
    private parsePrice(text: string): number {
        return parseFloat(text.replace(/[^0-9.-]+/g, '')) || 0;
    }

    private updateCartCount(totalItems: number): void {
        const cartCountElement = document.querySelector('.cart-item-count');
        if (cartCountElement) {
            const itemText = totalItems === 1 ? 'item' : 'items';
            cartCountElement.textContent = `${totalItems} ${itemText}`;
            console.log(`🔢 Updated cart count: ${totalItems} ${itemText}`);
        }
    }

    // [ANIM] Enhanced remove item with animation
    private async handleRemoveItem(event: Event): Promise<void> {
        event.preventDefault();
        console.log('🗑️ Remove item initiated');

        const form = event.currentTarget as HTMLFormElement;
        const row = form.closest('.cart-card') as HTMLElement;
        const productId = form.action.split('/').filter(Boolean).pop();

        if (!productId || !row) {
            console.error('❌ Could not extract product ID or find row');
            return;
        }

        console.log(`🗑️ Removing product: ${productId}`);

        // [NEW] Show loading overlay
        this.showLoadingOverlay(row);

        try {
            const response = await fetch(form.action, {
                method: 'POST',
                body: new FormData(form),
                headers: {
                    'X-Requested-With': 'XMLHttpRequest'
                }
            });

            const data = await response.json();
            console.log('🗑️ Remove item response:', data);

            if (data.success) {
                await this.removeCartItemRow(row, data); // [ANIM] Made async
                this.showToast({ message: 'Item removed from cart', type: 'success' }); // [NEW]
                console.log('✅ Item removed successfully');
            }
        } catch (error) {
            console.error('❌ Remove item error:', error);
            this.showToast({ message: 'Error removing item', type: 'error' }); // [NEW]
            this.hideLoadingOverlay(row);
        }
    }

    // [ANIM] Animate item removal
    private async removeCartItemRow(row: HTMLElement, data: any): Promise<void> {
        // Animate out
        row.classList.add('removing');

        await new Promise(resolve => setTimeout(resolve, 400));

        row.remove();
        console.log('🗑️ Cart item row removed from DOM');

        // Update cart totals
        await this.updateCartTotals(data.cart_total_price);
        this.updateCartCount(data.cart_total_items);

        // Show empty cart if needed
        if (data.cart_total_items === 0) {
            console.log('🛒 Cart is empty, reloading page');
            location.reload();
        }
    }

    // [NEW] Enhanced toast notification system
    private showToast(options: ToastOptions): void {
        const { message, type, duration = 3000 } = options;
        console.log(`📢 Showing ${type} toast: ${message}`);

        if (!this.toastContainer) return;

        const toast = document.createElement('div');
        toast.className = `toast toast-${type}`;
        toast.setAttribute('role', type === 'error' ? 'alert' : 'status');

        const icon = this.getToastIcon(type);
        toast.innerHTML = `
            <div class="toast-icon">${icon}</div>
            <div class="toast-message">${message}</div>
        `;

        this.toastContainer.appendChild(toast);

        // Trigger animation
        setTimeout(() => toast.classList.add('show'), 10);

        // Remove after duration
        setTimeout(() => {
            toast.classList.remove('show');
            toast.classList.add('hide');
            setTimeout(() => {
                toast.remove();
                console.log('📢 Toast removed');
            }, 300);
        }, duration);
    }

    // [NEW] Get icon for toast type
    private getToastIcon(type: string): string {
        const icons = {
            success: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M20 6L9 17l-5-5"/>
            </svg>`,
            error: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <circle cx="12" cy="12" r="10"/>
                <path d="M15 9l-6 6M9 9l6 6"/>
            </svg>`,
            warning: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/>
                <path d="M12 9v4M12 17h.01"/>
            </svg>`
        };
        return icons[type as keyof typeof icons] || icons.success;
    }

    private formatNumber(num: number): string {
        return num.toLocaleString('en-US');
    }
}

// Initialize cart manager when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    console.log('🚀 DOM loaded, initializing CartManager');
    try {
        (window as any).cartManager = new CartManager();
        console.log('🎉 CartManager initialized successfully');
    } catch (error) {
        console.error('💥 Failed to initialize CartManager:', error);
    }
});