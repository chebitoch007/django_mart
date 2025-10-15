// Cart functionality with TypeScript and logging - No module exports

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

class CartManager {
    private csrfToken: string;

    constructor() {
        console.log('🛒 CartManager initialized');
        this.csrfToken = this.getCSRFToken();
        this.initEventListeners();
    }

    private getCSRFToken(): string {
        const tokenElement = document.querySelector('[name=csrfmiddlewaretoken]') as HTMLInputElement;
        if (!tokenElement) {
            console.warn('⚠️ CSRF token not found');
            throw new Error('CSRF token not found');
        }
        console.log('🔐 CSRF token retrieved');
        return tokenElement.value;
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
        const row = form?.closest('.cart-item-row') as CartItemElement;

        if (!input || !row) {
            console.warn('❌ Could not find input or row for quantity button');
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
        this.updateCartItem(row.dataset.productId, newQuantity, input);
    }

    private handleQuantityInputChange(event: Event): void {
        const input = event.currentTarget as HTMLInputElement;
        const row = input.closest('.cart-item-row') as CartItemElement;

        if (!row) {
            console.warn('❌ Could not find row for quantity input');
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
        }

        input.value = newQuantity.toString();
        this.updateCartItem(row.dataset.productId, newQuantity, input);
    }

    private async updateCartItem(productId: string, quantity: number, input: HTMLInputElement): Promise<void> {
        console.log(`🔄 Updating cart item ${productId} to quantity ${quantity}`);

        try {
            const data = await this.makeCartUpdateRequest(productId, quantity);
            console.log('📦 Cart update response:', data);

            if (data.success) {
                this.updateCartUI(data, productId, input);
                this.showNotification('Cart updated successfully', 'success');
                console.log('✅ Cart UI updated successfully');
            } else if (data.message) {
                this.showNotification(data.message, 'error');
                console.warn('⚠️ Cart update warning:', data.message);
            }
        } catch (error) {
            console.error('❌ Cart update error:', error);
            this.showNotification('Error updating cart', 'error');
        }
    }

    private async makeCartUpdateRequest(productId: string, quantity: number): Promise<CartUpdateResponse> {
        // Use the URL from the data attribute
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

    private updateCartUI(data: CartUpdateResponse, productId: string, input: HTMLInputElement): void {
        console.log('🎨 Updating cart UI with data:', data);

        // Update item total
        const totalElement = document.getElementById(`total-${productId}`);
        if (totalElement) {
            totalElement.textContent = `KES ${this.formatNumber(parseFloat(data.item_total))}`;
            console.log(`💰 Updated item total for ${productId}: KES ${data.item_total}`);
        }

        // Update cart totals
        this.updateCartTotals(data.cart_total_price);

        // Update cart count in header
        this.updateCartCount(data.cart_total_items);

        // Update max stock and input value
        input.max = data.product_stock.toString();
        input.value = data.item_quantity.toString();
        console.log(`📊 Updated input max stock: ${data.product_stock}, quantity: ${data.item_quantity}`);

        // Show stock warning if needed
        this.updateStockWarnings(input, data.product_stock);
    }

    private updateCartTotals(cartTotalPrice: string): void {
        const subtotalElement = document.getElementById('cart-subtotal');
        const totalCartElement = document.getElementById('cart-total');

        if (subtotalElement && totalCartElement) {
            const formattedTotal = `KES ${this.formatNumber(parseFloat(cartTotalPrice))}`;
            subtotalElement.textContent = formattedTotal;
            totalCartElement.textContent = formattedTotal;
            console.log(`🛒 Updated cart totals: ${formattedTotal}`);
        }
    }

    private updateCartCount(totalItems: number): void {
        const cartCountElement = document.querySelector('.cart-item-count');
        if (cartCountElement) {
            const itemText = totalItems === 1 ? 'item' : 'items';
            cartCountElement.textContent = `${totalItems} ${itemText}`;
            console.log(`🔢 Updated cart count: ${totalItems} ${itemText}`);
        }
    }

    private updateStockWarnings(input: HTMLInputElement, maxStock: number): void {
        const formRow = input.closest('.cart-item-cell');
        if (!formRow) return;

        // Remove existing warnings
        const existingWarnings = formRow.querySelectorAll('.stock-warning');
        existingWarnings.forEach(el => el.remove());

        // Add new warning if needed
        if (parseInt(input.value) >= maxStock) {
            this.showStockWarning(input, maxStock);
            console.log(`⚠️ Showing stock warning for max stock: ${maxStock}`);
        }
    }

    private showStockWarning(input: HTMLInputElement, maxStock: number): void {
        const formRow = input.closest('.cart-item-cell');
        if (!formRow) return;

        const warning = document.createElement('div');
        warning.className = 'stock-warning';
        warning.innerHTML = `<i class="fas fa-exclamation-triangle"></i> Only ${maxStock} available`;
        formRow.appendChild(warning);
    }

    private async handleRemoveItem(event: Event): Promise<void> {
        event.preventDefault();
        console.log('🗑️ Remove item initiated');

        const form = event.currentTarget as HTMLFormElement;
        const productId = form.action.split('/').filter(Boolean).pop();

        if (!productId) {
            console.error('❌ Could not extract product ID from form action');
            return;
        }

        console.log(`🗑️ Removing product: ${productId}`);

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
                this.removeCartItemRow(form, data);
                this.showNotification('Item removed from cart', 'success');
                console.log('✅ Item removed successfully');
            }
        } catch (error) {
            console.error('❌ Remove item error:', error);
            this.showNotification('Error removing item', 'error');
        }
    }

    private removeCartItemRow(form: HTMLFormElement, data: any): void {
        const row = form.closest('.cart-item-row');
        if (row) {
            row.remove();
            console.log('🗑️ Cart item row removed from DOM');
        }

        // Update cart totals
        this.updateCartTotals(data.cart_total_price);
        this.updateCartCount(data.cart_total_items);

        // Show empty cart if needed
        if (data.cart_total_items === 0) {
            console.log('🛒 Cart is empty, reloading page');
            location.reload();
        }
    }

    private showNotification(message: string, type: 'success' | 'error'): void {
        console.log(`📢 Showing ${type} notification: ${message}`);

        // Remove existing toasts
        document.querySelectorAll('.toast').forEach(toast => toast.remove());

        // Create toast element
        const toast = document.createElement('div');
        toast.className = `toast ${type}`;
        toast.textContent = message;

        document.body.appendChild(toast);

        // Remove after 3 seconds
        setTimeout(() => {
            toast.style.animation = 'fadeOut 0.3s forwards';
            toast.addEventListener('animationend', () => {
                toast.remove();
                console.log('📢 Notification removed');
            });
        }, 2700);
    }

    private formatNumber(num: number): string {
        return num.toLocaleString('en-US');
    }
}

// Initialize cart manager when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    console.log('🚀 DOM loaded, initializing CartManager');
    try {
        // Use type assertion to avoid TypeScript errors
        (window as any).cartManager = new CartManager();
        console.log('🎉 CartManager initialized successfully');
    } catch (error) {
        console.error('💥 Failed to initialize CartManager:', error);
    }
});