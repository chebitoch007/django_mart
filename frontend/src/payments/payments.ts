import { initializeMpesa } from './mpesa.js';
import { initializePayPal, cleanupPayPal } from './paypal.js';
import {
  validatePhoneNumber,
  formatCurrency,
  saveFormState,
  restoreFormState,
  updateServerPaymentMethod
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
    this.init();
  }

  private init(): void {
    this.cacheElements();
    this.bindEvents();
    this.restoreState();
    this.initializePaymentMethod(this.state.currentMethod);
  }

  private cacheElements(): void {
    this.elements = {
      formAmount: document.getElementById('formAmount') as HTMLInputElement,
      paymentForm: document.getElementById('paymentForm') as HTMLFormElement,
      processingModal: document.getElementById('processingModal') as HTMLElement,
      modalTitle: document.getElementById('modalTitle') as HTMLElement,
      modalText: document.getElementById('modalText') as HTMLElement,
      paymentStatus: document.getElementById('paymentStatus') as HTMLElement,
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
      mobileMoneySection: document.getElementById('mobileMoneySection') as HTMLElement,
      paypalSection: document.getElementById('paypalSection') as HTMLElement,
      paymentTabs: document.querySelectorAll('.payment-tab'),
      phoneInput: document.getElementById('phoneNumber') as HTMLInputElement,
      phoneError: document.getElementById('phoneError') as HTMLElement,
      termsCheckbox: document.getElementById('termsAgreement') as HTMLInputElement,
      summaryToggle: document.getElementById('summaryToggle') as HTMLElement,
      summaryContent: document.getElementById('summaryContent') as HTMLElement
    };
  }

  private bindEvents(): void {
    // Payment method tabs
    this.elements.paymentTabs.forEach(tab => {
      tab.addEventListener('click', () => {
        if (!tab.classList.contains('active')) {
          this.switchPaymentMethod(tab.dataset.method as PaymentMethod);
        }
      });
    });

    // Currency selector
    this.elements.currencySelector.addEventListener('change', (e) => {
      this.handleCurrencyChange(e.target as HTMLSelectElement);
    });

    // Phone input validation
    this.elements.phoneInput.addEventListener('input', (e) => {
      this.handlePhoneInput((e.target as HTMLInputElement).value);
    });

    // Terms agreement
    this.elements.termsCheckbox.addEventListener('change', () => {
      this.handleTermsChange();
    });

    // Form submission
    this.elements.paymentForm.addEventListener('submit', (e) => {
      this.handleFormSubmit(e);
    });

    // Mobile summary toggle
    this.elements.summaryToggle.addEventListener('click', () => {
      this.toggleSummary();
    });

    // Window resize for responsive behavior
    window.addEventListener('resize', () => {
      this.handleResize();
    });
  }

  private restoreState(): void {
    const savedState = restoreFormState();
    this.state.currentMethod = savedState.method || 'mpesa';
    this.state.currentCurrency = savedState.currency || this.config.defaultCurrency;

    if (savedState.phone) {
      this.elements.phoneInput.value = savedState.phone;
    }
    if (savedState.terms) {
      this.elements.termsCheckbox.checked = true;
    }
  }

  private switchPaymentMethod(method: PaymentMethod): void {
    this.state.currentMethod = method;

    // Update UI
    updatePaymentMethodUI(method, this.elements.paymentTabs, this.elements.selectedMethodName);
    updateSubmitButton(method, this.elements.submitText, this.elements.submitIcon);
    this.elements.selectedMethodInput.value = method;

    // Handle section transitions
    this.togglePaymentSections(method);

    // Handle method-specific initialization
    if (method === 'paypal') {
      showCurrencyTooltip(method, this.state.currentCurrency, this.elements.currencyTooltip, this.elements.tooltipText);
      console.log("Switching to PayPal... Terms checked?", this.elements.termsCheckbox.checked);
      if (this.elements.termsCheckbox.checked) {
        console.log("✅ Initializing PayPal...");
        setTimeout(() => initializePayPal(this), 400);
      } else {
        console.warn("⚠️ PayPal not initialized because terms are unchecked.");
      }
    }
    else {
      hideCurrencyTooltip(this.elements.currencyTooltip);
      cleanupPayPal();
    }

    // Update server and save state
    saveFormState({
      method: method,
      currency: this.state.currentCurrency,
      phone: this.elements.phoneInput.value,
      terms: this.elements.termsCheckbox.checked
    });
  }

  private togglePaymentSections(method: PaymentMethod): void {
    if (method === 'paypal') {
      this.elements.mobileMoneySection.classList.remove('active');
      setTimeout(() => {
        this.elements.mobileMoneySection.style.display = 'none';
        this.elements.paypalSection.style.display = 'block';
        setTimeout(() => this.elements.paypalSection.classList.add('active'), 50);
      }, 300);
    } else {
      this.elements.paypalSection.classList.remove('active');
      setTimeout(() => {
        this.elements.paypalSection.style.display = 'none';
        this.elements.mobileMoneySection.style.display = 'block';
        setTimeout(() => this.elements.mobileMoneySection.classList.add('active'), 50);
      }, 300);
    }
  }

  private handleCurrencyChange(selector: HTMLSelectElement): void {
    const selectedOption = selector.options[selector.selectedIndex];
    const currency = selectedOption.value;
    const rate = parseFloat(selectedOption.dataset.rate || '1');

    this.state.currentCurrency = currency;
    this.state.currentRate = rate;

    this.elements.formCurrency.value = currency;
    this.elements.formConversionRate.value = rate.toString();

    // Update amounts in UI
    this.updateAmounts(rate, currency);

    // Handle PayPal currency changes
    if (this.state.currentMethod === 'paypal') {
      this.state.paypalInitialized = false;
      showCurrencyTooltip('paypal', currency, this.elements.currencyTooltip, this.elements.tooltipText);

      setTimeout(() => initializePayPal(this), 500);
    }

    saveFormState({
      method: this.state.currentMethod,
      currency: currency,
      phone: this.elements.phoneInput.value,
      terms: this.elements.termsCheckbox.checked
    });
  }

  private updateAmounts(rate: number, currency: string): void {
    const symbol = this.config.currencySymbols[currency] || currency;
    const baseTotal = parseFloat(this.config.cartTotalPrice);
    this.state.currentConvertedAmount = baseTotal * rate;

    // Update order items
    document.querySelectorAll('.order-item').forEach(item => {
      const basePrice = parseFloat((item as HTMLElement).dataset.price || '0');
      const amountElement = item.querySelector('.item-amount');
      if (amountElement) {
        amountElement.textContent = formatCurrency(basePrice * rate, currency);
      }
    });

    // Update summary
    const subtotalElement = document.querySelector('.subtotal-amount');
    const totalElement = document.querySelector('.total-amount');

    if (subtotalElement) {
      subtotalElement.textContent = formatCurrency(this.state.currentConvertedAmount, currency);
    }
    if (totalElement) {
      totalElement.textContent = formatCurrency(this.state.currentConvertedAmount, currency);
    }

    // Update form values
    this.elements.formAmount.value = this.state.currentConvertedAmount.toFixed(2);
    const amountInput = document.getElementById('amount') as HTMLInputElement;
    if (amountInput) {
      amountInput.value = `${currency} ${formatCurrency(this.state.currentConvertedAmount, currency)}`;
    }

    // Update currency symbols
    document.querySelectorAll('.currency-symbol').forEach(el => {
      el.textContent = symbol;
    });
  }

  private handlePhoneInput(value: string): void {
    if (value && validatePhoneNumber(value)) {
      clearInputError(this.elements.phoneInput, this.elements.phoneError);
    }
    saveFormState({
      method: this.state.currentMethod,
      currency: this.state.currentCurrency,
      phone: value,
      terms: this.elements.termsCheckbox.checked
    });
  }

  private handleTermsChange(): void {
    saveFormState({
      method: this.state.currentMethod,
      currency: this.state.currentCurrency,
      phone: this.elements.phoneInput.value,
      terms: this.elements.termsCheckbox.checked
    });

    if (this.state.currentMethod === 'paypal') {
      if (this.elements.termsCheckbox.checked) {
        setTimeout(() => initializePayPal(this), 300);
      }
    }
  }

  private async handleFormSubmit(e: Event): Promise<void> {
    e.preventDefault();

    // Hide previous errors
    this.elements.paymentErrors.style.display = 'none';

    // Validate form
    if (!this.validateForm()) {
      return;
    }

    const method = this.state.currentMethod;

    // For PayPal, show message to use the PayPal button
    if (method === 'paypal') {
      const paypalContainer = document.getElementById('paypal-button-container');
      if (paypalContainer) {
        paypalContainer.scrollIntoView({
          behavior: 'smooth',
          block: 'center'
        });
      }
      return;
    }

    // Handle M-Pesa
    if (method === 'mpesa') {
      await initializeMpesa(this);
    }
  }

  private validateForm(): boolean {
    let isValid = true;

    if (this.state.currentMethod === 'mpesa') {
      const phoneValue = this.elements.phoneInput.value.trim();
      if (!validatePhoneNumber(phoneValue)) {
        showInputError(
          this.elements.phoneInput,
          this.elements.phoneError,
          'Please enter a valid phone number (e.g. 712345678)'
        );
        isValid = false;
      } else {
        clearInputError(this.elements.phoneInput, this.elements.phoneError);
      }
    }

    if (!this.elements.termsCheckbox.checked) {
      showPaymentError('You must agree to the terms and conditions', this.elements.paymentErrors);
      isValid = false;
    }

    return isValid;
  }

  private toggleSummary(): void {
    const isCollapsed = this.elements.summaryContent.classList.contains('collapsed');

    if (isCollapsed) {
      this.elements.summaryContent.classList.remove('collapsed');
      this.elements.summaryToggle.classList.remove('collapsed');
      const span = this.elements.summaryToggle.querySelector('span');
      if (span) span.textContent = 'Hide Details';
      const icon = this.elements.summaryToggle.querySelector('i');
      if (icon) (icon as HTMLElement).style.transform = 'rotate(180deg)';
    } else {
      this.elements.summaryContent.classList.add('collapsed');
      this.elements.summaryToggle.classList.add('collapsed');
      const span = this.elements.summaryToggle.querySelector('span');
      if (span) span.textContent = 'Show Details';
      const icon = this.elements.summaryToggle.querySelector('i');
      if (icon) (icon as HTMLElement).style.transform = 'rotate(0deg)';
    }
  }

  private handleResize(): void {
    if (window.innerWidth <= 991 && !this.elements.summaryContent.classList.contains('collapsed')) {
      if (!this.elements.summaryToggle.classList.contains('initialized')) {
        this.elements.summaryContent.classList.add('collapsed');
        this.elements.summaryToggle.classList.add('collapsed');
        const span = this.elements.summaryToggle.querySelector('span');
        if (span) span.textContent = 'Show Details';
        this.elements.summaryToggle.classList.add('initialized');
      }
    } else if (window.innerWidth > 991) {
      this.elements.summaryContent.classList.remove('collapsed');
      this.elements.summaryToggle.classList.remove('collapsed');
    }
  }

  private isPaypalCurrencySupported(currency: string): boolean {
    const paypalSupportedCurrencies = ['USD', 'EUR', 'GBP', 'CAD', 'AUD', 'JPY'];
    return paypalSupportedCurrencies.includes(currency);
  }

  private initializePaymentMethod(method: PaymentMethod): void {
    updatePaymentMethodUI(method, this.elements.paymentTabs, this.elements.selectedMethodName);
    this.switchPaymentMethod(method);

    // Initialize mobile summary
    if (window.innerWidth <= 991) {
      this.elements.summaryContent.classList.add('collapsed');
      this.elements.summaryToggle.classList.add('collapsed');
      const span = this.elements.summaryToggle.querySelector('span');
      if (span) span.textContent = 'Show Details';
    }
  }

  // Public methods for other modules to access state
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
  // require that template injected config exists
  if (typeof window.paymentConfig === 'undefined') {
    console.error('paymentConfig missing. Make sure checkout template injects it.');
    return;
  }

  const cfg = window.paymentConfig;

  const config: PaymentConfig = {
    cartTotalPrice: cfg.cartTotalPrice,
    defaultCurrency: cfg.defaultCurrency,
    csrfToken: cfg.csrfToken,
    currencySymbols: {
      'USD': '$', 'EUR': '€', 'GBP': '£',
      'KES': 'KSh', 'UGX': 'USh', 'TZS': 'TSh'
    },
    orderId: cfg.orderId,
    paypalClientId: cfg.paypalClientId,
    urls: cfg.urls
  };

  window.paymentSystem = new PaymentSystem(config);
});