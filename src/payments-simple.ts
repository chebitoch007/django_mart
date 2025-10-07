// src/payments-simple.ts - Non-module version for debugging

// Simple payment system that doesn't use ES6 modules
class SimplePaymentSystem {
  private config: any;

  constructor() {
    this.config = this.getConfig();
    this.init();
  }

  private getConfig(): any {
    // Get config from window object or form data
    if (typeof window !== 'undefined' && (window as any).paymentConfig) {
      return (window as any).paymentConfig;
    }

    // Fallback config
    return {
      orderId: this.getOrderId(),
      cartTotalPrice: this.getAmount(),
      defaultCurrency: this.getCurrency(),
      csrfToken: this.getCSRFToken(),
      urls: {
        initiatePayment: '/payment/initiate/',
        processPayment: '/payment/process/',
        mpesaStatus: '/payment/mpesa-status/',
        orderSuccess: '/orders/success/'
      }
    };
  }

  private init(): void {
    console.log('SimplePaymentSystem initialized', this.config);
    this.bindEvents();
  }

  private bindEvents(): void {
    const form = document.getElementById('paymentForm') as HTMLFormElement;
    if (form) {
      form.addEventListener('submit', (e) => this.handleFormSubmit(e));
    }

    // Bind method tabs
    const tabs = document.querySelectorAll('.payment-tab');
    tabs.forEach(tab => {
      tab.addEventListener('click', () => {
        const method = tab.getAttribute('data-method');
        if (method) {
          this.switchPaymentMethod(method);
        }
      });
    });

    // Bind terms checkbox for PayPal
    const termsCheckbox = document.getElementById('termsAgreement') as HTMLInputElement;
    if (termsCheckbox) {
      termsCheckbox.addEventListener('change', () => {
        this.handleTermsChange();
      });
    }
  }

  private switchPaymentMethod(method: string): void {
    console.log('Switching to method:', method);

    // Update UI
    const tabs = document.querySelectorAll('.payment-tab');
    tabs.forEach(tab => {
      tab.classList.toggle('active', tab.getAttribute('data-method') === method);
    });

    const methodName = document.getElementById('selectedMethodName');
    if (methodName) methodName.textContent = method === 'paypal' ? 'PayPal' : 'M-Pesa';

    const methodInput = document.getElementById('selectedMethod') as HTMLInputElement;
    if (methodInput) methodInput.value = method;

    // Update submit button text
    const submitText = document.getElementById('submitText');
    if (submitText) {
      submitText.textContent = method === 'paypal' ? 'Pay with PayPal' : 'Pay with M-Pesa';
    }

    // Show/hide sections
    const mobileSection = document.getElementById('mobileMoneySection');
    const paypalSection = document.getElementById('paypalSection');

    if (method === 'paypal') {
      if (mobileSection) mobileSection.style.display = 'none';
      if (paypalSection) paypalSection.style.display = 'block';

      // Initialize PayPal if terms are checked
      const termsCheckbox = document.getElementById('termsAgreement') as HTMLInputElement;
      if (termsCheckbox && termsCheckbox.checked) {
        this.initializePayPal();
      }
    } else {
      if (mobileSection) mobileSection.style.display = 'block';
      if (paypalSection) paypalSection.style.display = 'none';
    }
  }

  private handleTermsChange(): void {
    const methodInput = document.getElementById('selectedMethod') as HTMLInputElement;
    const method = methodInput?.value || 'mpesa';

    if (method === 'paypal') {
      const termsCheckbox = document.getElementById('termsAgreement') as HTMLInputElement;
      if (termsCheckbox && termsCheckbox.checked) {
        this.initializePayPal();
      }
    }
  }

  private initializePayPal(): void {
    console.log('Initializing PayPal...');
    // For now, just log - we'll implement PayPal later
    const paypalContainer = document.getElementById('paypal-button-container');
    if (paypalContainer) {
      paypalContainer.innerHTML = '<div class="alert alert-info">PayPal will be initialized when you agree to terms</div>';
    }
  }

  private async handleFormSubmit(e: Event): Promise<void> {
    e.preventDefault();
    console.log('Form submission intercepted');

    const methodInput = document.getElementById('selectedMethod') as HTMLInputElement;
    const method = methodInput?.value || 'mpesa';

    if (method === 'paypal') {
      alert('Please use the PayPal button above');
      const paypalContainer = document.getElementById('paypal-button-container');
      if (paypalContainer) {
        paypalContainer.scrollIntoView({ behavior: 'smooth', block: 'center' });
      }
      return;
    }

    if (method === 'mpesa') {
      await this.handleMpesaPayment();
    }
  }

  private async handleMpesaPayment(): Promise<void> {
    console.log('Initiating M-Pesa payment');

    const phoneInput = document.getElementById('phoneNumber') as HTMLInputElement;
    const phone = phoneInput?.value.trim();

    if (!phone || !this.validatePhone(phone)) {
      alert('Please enter a valid phone number (e.g., 712345678)');
      return;
    }

    // Show processing
    this.showProcessing('mpesa');

    try {
      // Format phone number
      const formattedPhone = this.formatPhoneNumber(phone);
      if (!formattedPhone) {
        throw new Error('Invalid phone number format');
      }

      // Get amount and currency
      const amount = this.getAmount();
      const currency = this.getCurrency();
      const orderId = this.getOrderId();

      console.log('M-Pesa request:', {
        order_id: orderId,
        provider: 'MPESA',
        phone: formattedPhone,
        amount: amount,
        currency: currency
      });

      // Call M-Pesa initiation endpoint
      const response = await fetch('/payment/initiate/', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': this.getCSRFToken(),
          'X-Requested-With': 'XMLHttpRequest'
        },
        body: JSON.stringify({
          order_id: orderId,
          provider: 'MPESA',
          phone: formattedPhone,
          amount: amount,
          currency: currency
        })
      });

      const data = await response.json();
      console.log('M-Pesa response:', data);

      if (data.success && data.checkout_request_id) {
        // Set the checkout_request_id in the hidden field
        const checkoutInput = document.getElementById('checkoutRequestId') as HTMLInputElement;
        if (checkoutInput) {
          checkoutInput.value = data.checkout_request_id;
        }

        // Update processing modal
        this.updateProcessingModal('Payment Sent to Phone', 'Please check your phone and approve the M-Pesa prompt.');

        // Start polling for status
        this.pollMpesaStatus(data.checkout_request_id);

      } else {
        const errorMsg = data.error || data.message || 'Failed to initiate M-Pesa payment';
        alert('M-Pesa Error: ' + errorMsg);
        this.hideProcessing();
      }
    } catch (error) {
      console.error('M-Pesa error:', error);
      alert('Network error. Please try again.');
      this.hideProcessing();
    }
  }

  private validatePhone(phone: string): boolean {
    const cleanPhone = phone.trim().replace(/\s+/g, '');
    const phoneRegex = /^(?:254|\+254|0)?(7[0-9]{8})$/;
    return phoneRegex.test(cleanPhone);
  }

  private formatPhoneNumber(phone: string): string {
    const cleanPhone = phone.trim().replace(/\s+/g, '');
    const match = cleanPhone.match(/^(?:254|\+254|0)?(7[0-9]{8})$/);
    return match ? `254${match[1]}` : '';
  }

  private getCSRFToken(): string {
    const input = document.querySelector('[name=csrfmiddlewaretoken]') as HTMLInputElement;
    return input?.value || '';
  }

  private getOrderId(): string {
    const input = document.getElementById('orderId') as HTMLInputElement;
    return input?.value || this.config.orderId || '';
  }

  private getAmount(): string {
    const input = document.getElementById('formAmount') as HTMLInputElement;
    return input?.value || this.config.cartTotalPrice || '';
  }

  private getCurrency(): string {
    const input = document.getElementById('formCurrency') as HTMLInputElement;
    return input?.value || this.config.defaultCurrency || 'KES';
  }

  private showProcessing(method: string): void {
    const modal = document.getElementById('processingModal');
    if (modal) {
      modal.classList.add('active');
      this.updateProcessingModal('Processing Payment', 'Please wait while we process your payment...');
    }
  }

  private updateProcessingModal(title: string, text: string): void {
    const modalTitle = document.getElementById('modalTitle');
    const modalText = document.getElementById('modalText');

    if (modalTitle) modalTitle.textContent = title;
    if (modalText) modalText.textContent = text;
  }

  private hideProcessing(): void {
    const modal = document.getElementById('processingModal');
    if (modal) modal.classList.remove('active');
  }

  private pollMpesaStatus(checkoutRequestId: string): void {
    console.log('Starting M-Pesa status polling for:', checkoutRequestId);

    const pollInterval = 3000; // 3 seconds
    const maxAttempts = 40; // 2 minutes total
    let attempts = 0;

    const poller = setInterval(async () => {
      attempts++;

      if (attempts > maxAttempts) {
        clearInterval(poller);
        this.updateProcessingModal('Payment Timeout', 'Payment timed out. Please check your phone or try again.');
        setTimeout(() => {
          this.hideProcessing();
        }, 5000);
        return;
      }

      try {
        const statusUrl = `/payment/mpesa-status/?checkout_request_id=${checkoutRequestId}`;
        const response = await fetch(statusUrl, {
          headers: { 'X-Requested-With': 'XMLHttpRequest' }
        });

        const data = await response.json();
        console.log('M-Pesa status:', data);

        if (data.status === 'success' || data.status === 'completed') {
          clearInterval(poller);
          this.updateProcessingModal('Payment Confirmed', 'Finalizing your order...');

          // Submit the form to finalize payment
          setTimeout(() => {
            this.finalizeMpesaPayment(checkoutRequestId);
          }, 2000);

        } else if (data.status === 'failed' || data.status === 'error') {
          clearInterval(poller);
          this.updateProcessingModal('Payment Failed', data.message || 'Payment failed');
          setTimeout(() => {
            this.hideProcessing();
          }, 5000);
        }
        // Otherwise continue polling
      } catch (error) {
        console.error('Polling error:', error);
      }
    }, pollInterval);
  }

  private finalizeMpesaPayment(checkoutRequestId: string): void {
    console.log('Finalizing M-Pesa payment:', checkoutRequestId);

    // Set the checkout_request_id in the form
    const checkoutInput = document.getElementById('checkoutRequestId') as HTMLInputElement;
    if (checkoutInput) {
      checkoutInput.value = checkoutRequestId;
    }

    // Set other required form values
    const amountInput = document.getElementById('formAmount') as HTMLInputElement;
    if (amountInput && !amountInput.value) {
      amountInput.value = this.getAmount();
    }

    const phoneInput = document.getElementById('phoneNumber') as HTMLInputElement;
    const phoneValue = phoneInput?.value || '';

    // Add phone number to form if not already there
    if (phoneValue && !document.querySelector('[name="phone_number"]')) {
      const hiddenPhone = document.createElement('input');
      hiddenPhone.type = 'hidden';
      hiddenPhone.name = 'phone_number';
      hiddenPhone.value = phoneValue;
      document.getElementById('paymentForm')?.appendChild(hiddenPhone);
    }

    // Submit the form
    const form = document.getElementById('paymentForm') as HTMLFormElement;
    if (form) {
      console.log('Submitting final payment form...');
      form.submit();
    } else {
      console.error('Payment form not found');
      this.hideProcessing();
    }
  }
}

// Initialize when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
  console.log('Initializing SimplePaymentSystem...');
  new SimplePaymentSystem();
});