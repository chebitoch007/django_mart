// frontend/src/payments/payments.ts

import { storage } from './storage.js';
import { initializePaystack, resetPaystackPaymentState, checkExistingPaystackPayment } from './paystack.js';
import { initializeMpesa, resetMpesaPaymentState } from './mpesa.js';
import { initializePayPal, cleanupPayPal, resetPayPalPaymentState } from './paypal.js';
import {
  validatePhoneNumber,
  formatCurrency,
  saveFormState,
  restoreFormState,
  validateEmail,
  isPaystackCurrencySupported
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
  clearInputError
} from './ui.js';
import { PaymentConfig, PaymentState, PaymentElements, PaymentMethod } from '@/payments/types/payment.js';

export class PaymentSystem {
  private config: PaymentConfig;
  private state: PaymentState;
  private elements: PaymentElements;
  private isTransitioning: boolean = false;
  private originalTermsCheckbox: HTMLInputElement | null = null;

  constructor(config: PaymentConfig) {
    this.config = config;

    // ✅ CRITICAL FIX: robust parsing of the cart total
    const rawTotal = config.cartTotalPrice.toString().replace(/,/g, '');
    const baseAmount = parseFloat(rawTotal);

    console.log('[PaymentSystem] 🔧 Initializing with:', {
      rawInput: config.cartTotalPrice,
      parsedAmount: baseAmount,
      defaultCurrency: config.defaultCurrency
    });

    this.state = {
      currentMethod: 'mpesa',
      currentCurrency: config.defaultCurrency,
      currentRate: 1,
      currentConvertedAmount: baseAmount,
      paypalInitialized: false,
      paypalProcessing: false,
      processingStage: 0
    };

    this.elements = {} as PaymentElements;
    this.cacheElements();

    // Store original checkbox reference before any modifications
    this.originalTermsCheckbox = this.elements.termsCheckbox;

    this.addEventListeners();
    this.restoreState();

    // Initialize the initial method and force a calculation check
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

    // Input cleanup with real-time validation
    if (this.elements.phoneInput) {
      this.elements.phoneInput.addEventListener('input', () => {
        clearInputError(this.elements.phoneInput, this.elements.phoneError);
      });
      this.elements.phoneInput.addEventListener('blur', () => {
        if (this.state.currentMethod === 'mpesa' && this.elements.phoneInput.value.trim()) {
          const phone = validatePhoneNumber(this.elements.phoneInput.value.trim());
          if (!phone) {
            showInputError(
              this.elements.phoneInput,
              this.elements.phoneError,
              'Please enter a valid M-Pesa phone number (e.g., 712345678)'
            );
          }
        }
      });
    }

    if (this.elements.paystackEmailInput) {
      this.elements.paystackEmailInput.addEventListener('input', () => {
        clearInputError(this.elements.paystackEmailInput, this.elements.paystackEmailError);
      });
      this.elements.paystackEmailInput.addEventListener('blur', () => {
        if (this.state.currentMethod === 'paystack' && this.elements.paystackEmailInput.value.trim()) {
          if (!validateEmail(this.elements.paystackEmailInput.value.trim())) {
            showInputError(
              this.elements.paystackEmailInput,
              this.elements.paystackEmailError,
              'Please enter a valid email address'
            );
          }
        }
      });
    }

    this.initializeSummaryState();
  }

  private restoreState(): void {
    const savedState = restoreFormState();
    if (savedState.method) {
      this.state.currentMethod = savedState.method;
    }
    // Only restore currency if it exists in the dropdown options
    if (savedState.currency && this.elements.currencySelector.querySelector(`option[value="${savedState.currency}"]`)) {
      this.state.currentCurrency = savedState.currency;
      this.elements.currencySelector.value = savedState.currency;
    }
    if (savedState.phone && this.elements.phoneInput) {
      this.elements.phoneInput.value = savedState.phone;
    }
    if (savedState.email && this.elements.paystackEmailInput) {
      this.elements.paystackEmailInput.value = savedState.email;
    }
    if (typeof savedState.terms === 'boolean' && this.elements.termsCheckbox) {
      this.elements.termsCheckbox.checked = savedState.terms;
    }
  }

  private saveState(): void {
    // Always use the original checkbox reference for state
    const termsChecked = this.originalTermsCheckbox ? this.originalTermsCheckbox.checked : this.elements.termsCheckbox?.checked;

    saveFormState({
      method: this.state.currentMethod,
      currency: this.state.currentCurrency,
      phone: this.elements.phoneInput ? this.elements.phoneInput.value : undefined,
      email: this.elements.paystackEmailInput ? this.elements.paystackEmailInput.value : undefined,
      terms: termsChecked,
    });
  }

  /**
   * Enforce Currency Compatibility
   */
  private enforceProviderCurrency(method: PaymentMethod): void {
    const currentCurrency = this.elements.currencySelector.value;
    let targetCurrency = currentCurrency;

    // --- M-Pesa Logic ---
    if (method === 'mpesa' && currentCurrency !== 'KES') {
      if (this.elements.currencySelector.querySelector('option[value="KES"]')) {
        targetCurrency = 'KES';
        console.log('[PaymentSystem] 💱 Auto-switching to KES for M-Pesa');
      }
    }

    // --- PayPal Logic ---
    if (method === 'paypal' && currentCurrency === 'KES') {
      if (this.elements.currencySelector.querySelector('option[value="USD"]')) {
        targetCurrency = 'USD';
      } else if (this.elements.currencySelector.querySelector('option[value="EUR"]')) {
        targetCurrency = 'EUR';
      }

      if (targetCurrency !== 'KES') {
        console.log(`[PaymentSystem] 💱 Auto-switching to ${targetCurrency} for PayPal`);
      }
    }

    // --- Paystack Logic ---
    if (method === 'paystack') {
      if (!isPaystackCurrencySupported(currentCurrency)) {
        console.log(`[PaymentSystem] ⚠️ ${currentCurrency} not supported by Paystack.`);

        if (this.elements.currencySelector.querySelector('option[value="KES"]')) {
          targetCurrency = 'KES';
        }
        else if (this.elements.currencySelector.querySelector(`option[value="${this.config.defaultCurrency}"]`)) {
          targetCurrency = this.config.defaultCurrency;
        }
      }
    }

    // Apply switch if needed
    if (targetCurrency !== currentCurrency) {
      this.elements.currencySelector.value = targetCurrency;
      // Flash the tooltip
      if (this.elements.currencyTooltip && this.elements.tooltipText) {
        this.elements.tooltipText.innerHTML = `<i class="fas fa-info-circle"></i> Switched to <b>${targetCurrency}</b> for ${method} compatibility`;
        this.elements.currencyTooltip.style.display = 'flex';
        this.elements.currencyTooltip.classList.add('active');
        setTimeout(() => {
          this.elements.currencyTooltip.style.display = 'none';
          this.elements.currencyTooltip.classList.remove('active');
        }, 4000);
      }
      this.updateAmounts();
    }
  }

  private updatePaymentMethod(method: PaymentMethod): void {
    // Prevent concurrent transitions
    if (this.isTransitioning) return;

    console.log(`[PaymentSystem] 🔀 updatePaymentMethod called: ${this.state.currentMethod} → ${method}`);

    // Even if method is unchanged, we check currency compatibility
    if (this.state.currentMethod === method && this.state.processingStage === 0) {
      this.enforceProviderCurrency(method);
      return;
    }

    this.isTransitioning = true;

    // ✅ FIX 1: Read state from the LIVE element (this.elements.termsCheckbox),
    // NOT this.originalTermsCheckbox (which might be a dead DOM node).
    const termsWasChecked = this.elements.termsCheckbox ? this.elements.termsCheckbox.checked : false;

    // Cleanup previous method
    if (this.state.currentMethod === 'mpesa') {
      resetMpesaPaymentState();
    }
    if (this.state.currentMethod === 'paypal') {
      cleanupPayPal();
      this.state.paypalInitialized = false;
    }
    if (this.state.currentMethod === 'paystack') {
      resetPaystackPaymentState();
    }

    this.state.currentMethod = method;
    this.elements.selectedMethodInput.value = method;
    this.state.processingStage = 0;

    // Clear all error messages
    const errorSpan = this.elements.paymentErrors.querySelector('span');
    if (errorSpan) errorSpan.textContent = '';
    this.elements.paymentErrors.style.display = 'none';

    // Hide all sections first
    this.elements.mobileMoneySection.classList.remove('active');
    this.elements.paypalSection.classList.remove('active');
    this.elements.paystackSection.classList.remove('active');

    // Show the selected section
    if (method === 'mpesa') {
      this.elements.mobileMoneySection.classList.add('active');
    } else if (method === 'paypal') {
      this.elements.paypalSection.classList.add('active');
    } else if (method === 'paystack') {
      this.elements.paystackSection.classList.add('active');
    }

    // Show/hide submit button
    if (method === 'paypal') {
      this.elements.paymentSubmitButton.style.display = 'none';
    } else {
      this.elements.paymentSubmitButton.style.display = 'block';
    }

    // Update UI
    updatePaymentMethodUI(method, this.elements.paymentTabs, this.elements.selectedMethodName);
    updateSubmitButton(method, this.elements.submitText, this.elements.submitIcon);

    // ✅ FIX 2: Apply state to the LIVE element
    if (this.elements.termsCheckbox) {
      this.elements.termsCheckbox.checked = termsWasChecked;
    }

    // Check Currency Compatibility
    this.enforceProviderCurrency(method);

    // Initialize method-specific logic
    if (method === 'paypal') {
      const paypalStatus = document.getElementById('paypal-status');
      if (paypalStatus) {
        paypalStatus.style.display = 'none';
      }
      setTimeout(() => {
        initializePayPal(this);
        this.isTransitioning = false;
      }, 100);
    } else {
      if (method === 'paystack') {
        const paystackStatusEl = document.getElementById('paystack-status');
        if (paystackStatusEl) paystackStatusEl.style.display = 'none';
      }
      this.isTransitioning = false;
    }

    this.saveState();
  }

  private updateAmounts(): void {
    const selector = this.elements.currencySelector;
    const selectedOption = selector.options[selector.selectedIndex];

    const newCurrency = selectedOption.value;
    const rate = parseFloat(selectedOption.getAttribute('data-rate') || '1');

    const baseAmount = parseFloat(this.config.cartTotalPrice.toString().replace(/,/g, ''));

    console.log('[PaymentSystem] 💱 Calculation:', {
      base: baseAmount,
      rate: rate,
      target: newCurrency,
    });

    this.state.currentCurrency = newCurrency;
    this.state.currentRate = rate;
    this.state.currentConvertedAmount = baseAmount * rate;

    const currencySymbol = this.config.currencySymbols[newCurrency] || newCurrency;

    // Update hidden form fields
    this.elements.formCurrency.value = newCurrency;
    this.elements.formConversionRate.value = rate.toString();
    this.elements.formAmount.value = this.state.currentConvertedAmount.toFixed(2);

    // Update amount inputs
    const formattedPrice = `${currencySymbol} ${formatCurrency(this.state.currentConvertedAmount, newCurrency)}`;

    const amountInput = document.getElementById('amount') as HTMLInputElement;
    if (amountInput) {
      amountInput.value = formattedPrice;
    }

    const paystackAmountInput = document.getElementById('paystackAmount') as HTMLInputElement;
    if (paystackAmountInput) {
      paystackAmountInput.value = formattedPrice;
    }

    // Update currency symbols in summary
    document.querySelectorAll('.currency-symbol').forEach(el => {
      el.textContent = currencySymbol;
    });

    // Update summary totals
    const convertedAmountStr = formatCurrency(this.state.currentConvertedAmount, newCurrency);
    const subtotal = document.querySelector('.subtotal-amount');
    const total = document.querySelector('.total-amount');
    if (subtotal) subtotal.textContent = convertedAmountStr;
    if (total) total.textContent = convertedAmountStr;

    // Re-initialize PayPal if needed
    if (this.state.currentMethod === 'paypal' && this.state.paypalInitialized) {
      console.log('[PaymentSystem] 🔄 Currency changed, re-initializing PayPal...');
      cleanupPayPal();
      this.state.paypalInitialized = false;
      setTimeout(() => {
        initializePayPal(this);
      }, 100);
    }

    this.saveState();
  }

  private validateForm(): boolean {
    let isValid = true;

    // Clear previous errors
    showPaymentError('', this.elements.paymentErrors, false);

    // Get the current checkbox state
    const currentCheckbox = this.originalTermsCheckbox || this.elements.termsCheckbox;

    // 1. Terms check (required for all)
    if (!currentCheckbox || !currentCheckbox.checked) {
      showPaymentError('You must agree to the Terms of Service', this.elements.paymentErrors);
      return false;
    }

    // 2. Method-specific validation
    if (this.state.currentMethod === 'mpesa') {
      const phoneNumber = this.elements.phoneInput.value.trim();
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

      if (!emailValue || !validateEmail(emailValue)) {
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

    if (this.state.currentMethod === 'paypal') {
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

  public getOriginalTermsCheckbox(): HTMLInputElement | null {
    return this.originalTermsCheckbox;
  }
}

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