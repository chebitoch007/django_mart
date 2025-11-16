// frontend/src/payments/payments.ts - FIXED VERSION

import { storage } from './storage.js';
import { initializePaystack, resetPaystackPaymentState, checkExistingPaystackPayment } from './paystack.js';
import { initializeMpesa, resetMpesaPaymentState } from './mpesa.js';
import { initializePayPal, cleanupPayPal, resetPayPalPaymentState } from './paypal.js';
import {
  validatePhoneNumber,
  formatCurrency,
  saveFormState,
  restoreFormState
} from './utils.js';
import {
  showPaymentStatus,
  showPaymentError,
  setSubmitButtonState,
  startProcessingAnimation,
  stopProcessingAnimation,
  updatePaymentMethodUI,
  updateSubmitButton,
  showCurrencyTooltip,
  hideCurrencyTooltip,
  showInputError,
  clearInputError,
  showPaystackStatus
} from './ui.js';
import { PaymentConfig, PaymentState, PaymentElements, PaymentMethod } from '@/payments/types/payment.js';

export class PaymentSystem {
  private config: PaymentConfig;
  private state: PaymentState;
  private elements: PaymentElements;

  constructor(config: PaymentConfig) {
    this.config = config;
    this.state = {
      currentMethod: 'mpesa',
      currentCurrency: config.defaultCurrency,
      currentRate: 1,
      currentConvertedAmount: parseFloat(config.cartTotalPrice),
      paypalInitialized: false,
      paypalProcessing: false,
      processingStage: 0
    };

    this.elements = {} as PaymentElements;
    this.cacheElements();
    this.addEventListeners();
    this.restoreState();

    // Initialize the initial method
    this.updatePaymentMethod(this.state.currentMethod);
    this.updateAmounts();

    // Check for existing payments
    checkExistingPaystackPayment(this);
  }

  private cacheElements(): void {
    const paymentForm = document.getElementById('paymentForm') as HTMLFormElement;
    if (!paymentForm) {
      console.error('Payment form element not found.');
      return;
    }

    this.elements = {
      paymentForm: paymentForm,
      processingModal: document.getElementById('processingModal') as HTMLElement,
      modalTitle: document.getElementById('modalTitle') as HTMLElement,
      modalText: document.getElementById('modalText') as HTMLElement,
      paymentStatus: document.getElementById('payment-status') as HTMLElement,
      paystackStatus: document.getElementById('paystack-status') as HTMLElement,
      paymentErrors: document.getElementById('paymentErrors') as HTMLElement,
      selectedMethodInput: document.getElementById('selectedMethod') as HTMLInputElement,
      currencySelector: document.getElementById('currencySelector') as HTMLSelectElement,
      currencyTooltip: document.getElementById('currencyTooltip') as HTMLElement,
      tooltipText: document.getElementById('tooltipText') as HTMLElement,
      methodConfirmation: document.getElementById('methodConfirmation') as HTMLElement,
      selectedMethodName: document.getElementById('selectedMethodName') as HTMLElement,
      paymentSubmitButton: document.getElementById('paymentSubmitButton') as HTMLButtonElement,
      submitText: document.getElementById('submitText') as HTMLElement,
      submitIcon: document.getElementById('submitIcon') as HTMLElement,
      formCurrency: document.getElementById('formCurrency') as HTMLInputElement,
      formConversionRate: document.getElementById('formConversionRate') as HTMLInputElement,
      formAmount: document.getElementById('formAmount') as HTMLInputElement,
      mobileMoneySection: document.getElementById('mpesaSection') as HTMLElement,
      paystackSection: document.getElementById('paystackSection') as HTMLElement,
      paypalSection: document.getElementById('paypalSection') as HTMLElement,
      paymentTabs: document.querySelectorAll('.payment-tabs .payment-tab') as NodeListOf<HTMLElement>,
      phoneInput: document.getElementById('phoneNumber') as HTMLInputElement,
      phoneError: document.getElementById('phoneError') as HTMLElement,
      termsCheckbox: document.getElementById('termsAgreement') as HTMLInputElement,
      summaryToggle: document.getElementById('summaryToggle') as HTMLElement,
      summaryContent: document.getElementById('summaryContent') as HTMLElement,
      paystackEmailInput: document.getElementById('paystackEmail') as HTMLInputElement,
      paystackEmailError: document.getElementById('paystackEmailError') as HTMLElement
    };
  }

  private addEventListeners(): void {
    // Payment method tabs
    this.elements.paymentTabs.forEach(tab => {
      tab.addEventListener('click', () => {
        const method = tab.getAttribute('data-method') as PaymentMethod;
        this.updatePaymentMethod(method);
      });
    });

    // Currency selector
    this.elements.currencySelector.addEventListener('change', () => this.updateAmounts());
    this.elements.currencySelector.addEventListener('mouseover', () => {
      showCurrencyTooltip(
        this.state.currentMethod,
        this.state.currentCurrency,
        this.elements.currencyTooltip,
        this.elements.tooltipText
      );
    });
    this.elements.currencySelector.addEventListener('mouseout', () => {
      hideCurrencyTooltip(this.elements.currencyTooltip);
    });

    // Submit form
    this.elements.paymentForm.addEventListener('submit', (e) => this.handleFormSubmit(e));

    // Summary toggle
    this.elements.summaryToggle.addEventListener('click', () => this.toggleSummary());

    // Input cleanup
    if (this.elements.phoneInput) {
      this.elements.phoneInput.addEventListener('input', () =>
        clearInputError(this.elements.phoneInput, this.elements.phoneError)
      );
    }
    if (this.elements.paystackEmailInput) {
      this.elements.paystackEmailInput.addEventListener('input', () =>
        clearInputError(this.elements.paystackEmailInput, this.elements.paystackEmailError)
      );
    }

    this.initializeSummaryState();
  }

  private restoreState(): void {
    const savedState = restoreFormState();
    if (savedState.method) {
      this.state.currentMethod = savedState.method;
    }
    if (savedState.currency) {
      this.state.currentCurrency = savedState.currency;
      this.elements.currencySelector.value = savedState.currency;
    }
    if (savedState.phone && this.elements.phoneInput) {
      this.elements.phoneInput.value = savedState.phone;
    }
    if (savedState.terms && this.elements.termsCheckbox) {
      this.elements.termsCheckbox.checked = savedState.terms;
    }
  }

  private saveState(): void {
    saveFormState({
      method: this.state.currentMethod,
      currency: this.state.currentCurrency,
      phone: this.elements.phoneInput ? this.elements.phoneInput.value : undefined,
      terms: this.elements.termsCheckbox ? this.elements.termsCheckbox.checked : undefined,
    });
  }

  private updatePaymentMethod(method: PaymentMethod): void {
    console.log(`[PaymentSystem] 🔀 updatePaymentMethod called: ${this.state.currentMethod} → ${method}`);

    if (this.state.currentMethod === method) {
      console.log(`[PaymentSystem] ⏭️  Method unchanged, skipping`);
      return;
    }

    console.log(`[PaymentSystem] 🧹 Cleaning up previous method: ${this.state.currentMethod}`);

    // Reset previous method
    if (this.state.currentMethod === 'mpesa') {
      console.log('[PaymentSystem] Resetting M-Pesa state');
      resetMpesaPaymentState();
    }
    if (this.state.currentMethod === 'paypal') {
      console.log('[PaymentSystem] Cleaning up PayPal');
      cleanupPayPal();
      this.setState({ paypalInitialized: false }); // *** THIS IS THE FIX ***
    }
    if (this.state.currentMethod === 'paystack') {
      console.log('[PaymentSystem] Resetting Paystack state');
      resetPaystackPaymentState();
    }

    this.state.currentMethod = method;
    this.elements.selectedMethodInput.value = method;
    this.state.processingStage = 0;

    console.log(`[PaymentSystem] ✅ Current method updated to: ${method}`);

    // Clear all error messages
    const errorSpan = this.elements.paymentErrors.querySelector('span');
    if (errorSpan) errorSpan.textContent = '';
    this.elements.paymentErrors.style.display = 'none';
    console.log('[PaymentSystem] 🧹 Error messages cleared');

    // Show/hide sections
    console.log('[PaymentSystem] 🎨 Updating section visibility...');
    this.elements.mobileMoneySection.classList.toggle('active', method === 'mpesa');
    this.elements.paypalSection.classList.toggle('active', method === 'paypal');
    this.elements.paystackSection.classList.toggle('active', method === 'paystack');

    console.log(`[PaymentSystem] Section visibility: M-Pesa=${this.elements.mobileMoneySection.style.display}, PayPal=${this.elements.paypalSection.style.display}, Paystack=${this.elements.paystackSection.style.display}`);

    // Show/hide submit button
    if (method === 'paypal') {
      console.log('[PaymentSystem] 👁️  Hiding submit button for PayPal');
      this.elements.paymentSubmitButton.style.display = 'none';
    } else {
      console.log('[PaymentSystem] 👁️  Showing submit button for', method);
      this.elements.paymentSubmitButton.style.display = 'block';
    }

    // Update UI
    console.log('[PaymentSystem] 🎨 Updating UI elements...');
    updatePaymentMethodUI(method, this.elements.paymentTabs, this.elements.selectedMethodName);
    updateSubmitButton(method, this.elements.submitText, this.elements.submitIcon);

    // Initialize method-specific logic
    if (method === 'paypal') {
      console.log('[PaymentSystem] 💳 Initializing PayPal...');
      console.log('[PaymentSystem] PayPal initialized flag:', this.state.paypalInitialized);

      // Clear PayPal status
      const paypalStatus = document.getElementById('paypal-status');
      if (paypalStatus) {
        paypalStatus.style.display = 'none';
        console.log('[PaymentSystem] PayPal status cleared');
      }

      // Initialize PayPal
      initializePayPal(this);
    } else if (method === 'paystack') {
      console.log('[PaymentSystem] 💳 Switching to Paystack');

      // Clear Paystack status
      const paystackStatusEl = document.getElementById('paystack-status');
      if (paystackStatusEl) {
        paystackStatusEl.style.display = 'none';
        console.log('[PaymentSystem] Paystack status cleared');
      }
    } else if (method === 'mpesa') {
      console.log('[PaymentSystem] 📱 Switching to M-Pesa');
    }

    this.saveState();
    console.log(`[PaymentSystem] ✅ Method switch complete: ${method}`);
  }

  private updateAmounts(): void {
    const selector = this.elements.currencySelector;
    const selectedOption = selector.options[selector.selectedIndex];

    const newCurrency = selectedOption.value;
    const rate = parseFloat(selectedOption.getAttribute('data-rate') || '1');

    this.state.currentCurrency = newCurrency;
    this.state.currentRate = rate;

    const cartTotal = parseFloat(this.config.cartTotalPrice);
    this.state.currentConvertedAmount = cartTotal * rate;

    const currency = this.config.currencySymbols[newCurrency] || newCurrency;

    // Update hidden form fields
    this.elements.formCurrency.value = newCurrency;
    this.elements.formConversionRate.value = rate.toString();
    this.elements.formAmount.value = this.state.currentConvertedAmount.toFixed(2);

    // Update amount inputs
    const amountInput = document.getElementById('amount') as HTMLInputElement;
    if (amountInput) {
      amountInput.value = `${currency} ${formatCurrency(this.state.currentConvertedAmount, newCurrency)}`;
    }

    const paystackAmountInput = document.getElementById('paystackAmount') as HTMLInputElement;
    if (paystackAmountInput) {
      paystackAmountInput.value = `${currency} ${formatCurrency(this.state.currentConvertedAmount, newCurrency)}`;
    }

    // Update currency symbols in summary
    document.querySelectorAll('.currency-symbol').forEach(el => {
      el.textContent = currency;
    });

    const convertedAmountStr = formatCurrency(this.state.currentConvertedAmount, newCurrency);
    const subtotal = document.querySelector('.subtotal-amount');
    const total = document.querySelector('.total-amount');
    if (subtotal) subtotal.textContent = convertedAmountStr;
    if (total) total.textContent = convertedAmountStr;

    // Re-initialize PayPal if it's the current method
    if (this.state.currentMethod === 'paypal') {
      cleanupPayPal();
      this.state.paypalInitialized = false;
      initializePayPal(this);
    }

    this.saveState();
  }

  private validateForm(): boolean {
    let isValid = true;

    // Clear previous errors
    showPaymentError('', this.elements.paymentErrors, false);

    // 1. Terms check (required for all)
    if (!this.elements.termsCheckbox.checked) {
      showPaymentError('You must agree to the Terms of Service', this.elements.paymentErrors);
      return false;
    }

    // 2. Method-specific validation
    if (this.state.currentMethod === 'mpesa') {
      const phoneNumber = this.elements.phoneInput.value;
      const cleanPhone = validatePhoneNumber(phoneNumber);

      if (!cleanPhone) {
        showInputError(
          this.elements.phoneInput,
          this.elements.phoneError,
          'Please enter a valid M-Pesa phone number (e.g., 712345678)'
        );
        isValid = false;
      } else {
        this.elements.phoneInput.value = cleanPhone;
        clearInputError(this.elements.phoneInput, this.elements.phoneError);
      }
    }

    if (this.state.currentMethod === 'paystack') {
      const emailValue = this.elements.paystackEmailInput.value.trim();
      const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

      if (!emailValue || !emailRegex.test(emailValue)) {
        showInputError(
          this.elements.paystackEmailInput,
          this.elements.paystackEmailError,
          'Please enter a valid email address'
        );
        isValid = false;
      } else {
        clearInputError(this.elements.paystackEmailInput, this.elements.paystackEmailError);
      }
    }

    // PayPal validation is handled by PayPal SDK
    if (this.state.currentMethod === 'paypal') {
      // Don't show error, PayPal handles its own flow
      return true;
    }

    return isValid;
  }

  private async handleFormSubmit(e: Event): Promise<void> {
    e.preventDefault();

    if (!this.validateForm()) {
      return;
    }

    const method = this.state.currentMethod;

    if (method === 'mpesa') {
      await initializeMpesa(this);
    } else if (method === 'paystack') {
      await initializePaystack(this);
    } else if (method === 'paypal') {
      // PayPal submission is handled by PayPal SDK buttons
      // This should never be reached since submit button is hidden for PayPal
      console.warn('PayPal form submitted directly - should use PayPal buttons');
    }
  }

  private toggleSummary(): void {
    this.elements.summaryContent.classList.toggle('collapsed');
    this.elements.summaryToggle.classList.toggle('collapsed');

    const span = this.elements.summaryToggle.querySelector('span');
    const icon = this.elements.summaryToggle.querySelector('i');

    if (span) {
      span.textContent = this.elements.summaryContent.classList.contains('collapsed')
        ? 'Show Details'
        : 'Hide Details';
    }
    if (icon) {
      icon.classList.toggle('fa-chevron-down');
      icon.classList.toggle('fa-chevron-up');
    }
  }

  private initializeSummaryState(): void {
    if (window.innerWidth <= 991) {
      this.elements.summaryContent.classList.add('collapsed');
      this.elements.summaryToggle.classList.add('collapsed');
      const icon = this.elements.summaryToggle.querySelector('i');
      if (icon) {
        icon.classList.remove('fa-chevron-down');
        icon.classList.add('fa-chevron-up');
      }
    }
  }

  // Public methods
  public getState(): PaymentState {
    return { ...this.state };
  }

  public setState(newState: Partial<PaymentState>): void {
    this.state = { ...this.state, ...newState };
  }

  public getElements(): PaymentElements {
    return { ...this.elements };
  }

  public getConfig(): PaymentConfig {
    return { ...this.config };
  }
}

// Initialize when DOM is loaded
document.addEventListener('DOMContentLoaded', function () {
  if (typeof window.paymentConfig === 'undefined') {
    console.error('paymentConfig missing. Make sure checkout template injects it.');
    return;
  }

  const cfg = window.paymentConfig;

  const currencySymbols: Record<string, string> = {
    'USD': '$', 'EUR': '€', 'GBP': '£',
    'KES': 'KSh', 'UGX': 'USh', 'TZS': 'TSh',
    'NGN': '₦', 'GHS': 'GH₵'
  };

  const config: PaymentConfig = {
    cartTotalPrice: cfg.cartTotalPrice,
    defaultCurrency: cfg.defaultCurrency,
    csrfToken: cfg.csrfToken,
    currencySymbols: currencySymbols,
    orderId: cfg.orderId,
    paypalClientId: cfg.paypalClientId,
    paystackPublicKey: cfg.paystackPublicKey,
    urls: cfg.urls,
    currencyOptions: Array.from(document.getElementById('currencySelector')!.querySelectorAll('option')).map(option => ({
      code: option.value,
      name: option.textContent!.split(' - ')[1] || option.value,
      symbol: currencySymbols[option.value] || option.value,
      rate: parseFloat(option.getAttribute('data-rate') || '1'),
    }))
  };

  window.paymentSystem = new PaymentSystem(config);

  const symbol = config.currencySymbols[config.defaultCurrency] || config.defaultCurrency;
  document.querySelectorAll('.currency-symbol').forEach(el => {
    el.textContent = symbol;
  });
});