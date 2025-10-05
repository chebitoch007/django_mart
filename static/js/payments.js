// static/js/payments.js
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

class PaymentSystem {
    constructor(config) {
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

        this.elements = {};
        this.init();
    }

    init() {
        this.cacheElements();
        this.bindEvents();
        this.restoreState();
        this.initializePaymentMethod(this.state.currentMethod);
    }

    cacheElements() {
        this.elements = {
            paymentForm: document.getElementById('paymentForm'),
            processingModal: document.getElementById('processingModal'),
            modalTitle: document.getElementById('modalTitle'),
            modalText: document.getElementById('modalText'),
            paymentStatus: document.getElementById('paymentStatus'),
            paymentErrors: document.getElementById('paymentErrors'),
            selectedMethodInput: document.getElementById('selectedMethod'),
            currencySelector: document.getElementById('currencySelector'),
            currencyTooltip: document.getElementById('currencyTooltip'),
            tooltipText: document.getElementById('tooltipText'),
            methodConfirmation: document.getElementById('methodConfirmation'),
            selectedMethodName: document.getElementById('selectedMethodName'),
            paymentSubmitButton: document.getElementById('paymentSubmitButton'),
            submitText: document.getElementById('submitText'),
            submitIcon: document.getElementById('submitIcon'),
            formCurrency: document.getElementById('formCurrency'),
            formConversionRate: document.getElementById('formConversionRate'),
            mobileMoneySection: document.getElementById('mobileMoneySection'),
            paypalSection: document.getElementById('paypalSection'),
            paymentTabs: document.querySelectorAll('.payment-tab'),
            phoneInput: document.getElementById('phoneNumber'),
            phoneError: document.getElementById('phoneError'),
            termsCheckbox: document.getElementById('termsAgreement'),
            summaryToggle: document.getElementById('summaryToggle'),
            summaryContent: document.getElementById('summaryContent')
        };
    }

    bindEvents() {
        // Payment method tabs
        this.elements.paymentTabs.forEach(tab => {
            tab.addEventListener('click', () => {
                if (!tab.classList.contains('active')) {
                    this.switchPaymentMethod(tab.dataset.method);
                }
            });
        });

        // Currency selector
        this.elements.currencySelector.addEventListener('change', (e) => {
            this.handleCurrencyChange(e.target);
        });

        // Phone input validation
        this.elements.phoneInput.addEventListener('input', (e) => {
            this.handlePhoneInput(e.target.value);
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

    restoreState() {
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

    switchPaymentMethod(method) {
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
            if (this.elements.termsCheckbox.checked) {
                setTimeout(() => initializePayPal(this), 400);
            }
        } else {
            hideCurrencyTooltip(this.elements.currencyTooltip);
            cleanupPayPal();
        }

        // Update server and save state
        updateServerPaymentMethod(method, this.config.csrfToken);
        saveFormState({
            method: method,
            currency: this.state.currentCurrency,
            phone: this.elements.phoneInput.value,
            terms: this.elements.termsCheckbox.checked
        });
    }

    togglePaymentSections(method) {
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

    handleCurrencyChange(selector) {
        const selectedOption = selector.options[selector.selectedIndex];
        const currency = selectedOption.value;
        const rate = parseFloat(selectedOption.dataset.rate);

        this.state.currentCurrency = currency;
        this.state.currentRate = rate;

        this.elements.formCurrency.value = currency;
        this.elements.formConversionRate.value = rate;

        // Update amounts in UI
        this.updateAmounts(rate, currency);

        // Handle PayPal currency changes
        if (this.state.currentMethod === 'paypal') {
            this.state.paypalInitialized = false;
            showCurrencyTooltip('paypal', currency, this.elements.currencyTooltip, this.elements.tooltipText);

            if (!this.isPaypalCurrencySupported(currency) && currency !== 'USD') {
                setTimeout(() => this.switchPaymentMethod('mpesa'), 1000);
            } else {
                setTimeout(() => initializePayPal(this), 500);
            }
        }

        saveFormState({
            method: this.state.currentMethod,
            currency: currency,
            phone: this.elements.phoneInput.value,
            terms: this.elements.termsCheckbox.checked
        });
    }

    updateAmounts(rate, currency) {
        const symbol = this.config.currencySymbols[currency] || currency;
        const baseTotal = parseFloat(this.config.cartTotalPrice);
        this.state.currentConvertedAmount = baseTotal * rate;

        // Update order items
        document.querySelectorAll('.order-item').forEach(item => {
            const basePrice = parseFloat(item.dataset.price);
            item.querySelector('.item-amount').textContent =
                formatCurrency(basePrice * rate, currency);
        });

        // Update summary
        document.querySelector('.subtotal-amount').textContent =
            formatCurrency(this.state.currentConvertedAmount, currency);
        document.querySelector('.total-amount').textContent =
            formatCurrency(this.state.currentConvertedAmount, currency);

        // Update form values
        this.elements.formAmount.value = this.state.currentConvertedAmount.toFixed(2);
        document.getElementById('amount').value =
            `${currency} ${formatCurrency(this.state.currentConvertedAmount, currency)}`;

        // Update currency symbols
        document.querySelectorAll('.currency-symbol').forEach(el => {
            el.textContent = symbol;
        });
    }

    handlePhoneInput(value) {
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

    handleTermsChange() {
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

    async handleFormSubmit(e) {
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
            document.getElementById('paypal-button-container').scrollIntoView({
                behavior: 'smooth',
                block: 'center'
            });
            return false;
        }

        // Handle M-Pesa
        if (method === 'mpesa') {
            await initializeMpesa(this);
        }
    }

    validateForm() {
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

    toggleSummary() {
        const isCollapsed = this.elements.summaryContent.classList.contains('collapsed');

        if (isCollapsed) {
            this.elements.summaryContent.classList.remove('collapsed');
            this.elements.summaryToggle.classList.remove('collapsed');
            this.elements.summaryToggle.querySelector('span').textContent = 'Hide Details';
            this.elements.summaryToggle.querySelector('i').style.transform = 'rotate(180deg)';
        } else {
            this.elements.summaryContent.classList.add('collapsed');
            this.elements.summaryToggle.classList.add('collapsed');
            this.elements.summaryToggle.querySelector('span').textContent = 'Show Details';
            this.elements.summaryToggle.querySelector('i').style.transform = 'rotate(0deg)';
        }
    }

    handleResize() {
        if (window.innerWidth <= 991 && !this.elements.summaryContent.classList.contains('collapsed')) {
            if (!this.elements.summaryToggle.classList.contains('initialized')) {
                this.elements.summaryContent.classList.add('collapsed');
                this.elements.summaryToggle.classList.add('collapsed');
                this.elements.summaryToggle.querySelector('span').textContent = 'Show Details';
                this.elements.summaryToggle.classList.add('initialized');
            }
        } else if (window.innerWidth > 991) {
            this.elements.summaryContent.classList.remove('collapsed');
            this.elements.summaryToggle.classList.remove('collapsed');
        }
    }

    isPaypalCurrencySupported(currency) {
        const paypalSupportedCurrencies = ['USD', 'EUR', 'GBP', 'CAD', 'AUD', 'JPY'];
        return paypalSupportedCurrencies.includes(currency);
    }

    initializePaymentMethod(method) {
        updatePaymentMethodUI(method, this.elements.paymentTabs, this.elements.selectedMethodName);
        this.switchPaymentMethod(method);

        // Initialize mobile summary
        if (window.innerWidth <= 991) {
            this.elements.summaryContent.classList.add('collapsed');
            this.elements.summaryToggle.classList.add('collapsed');
            this.elements.summaryToggle.querySelector('span').textContent = 'Show Details';
        }
    }

    // Public methods for other modules to access state
    getState() {
        return { ...this.state };
    }

    setState(newState) {
        this.state = { ...this.state, ...newState };
    }

    getElements() {
        return { ...this.elements };
    }

    getConfig() {
        return { ...this.config };
    }
}

// Export for use in other modules
export { PaymentSystem };

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', function() {
    const config = {
        cartTotalPrice: "{{ cart.total_price }}",
        defaultCurrency: '{{ default_currency|default:"USD" }}',
        csrfToken: "{{ csrf_token }}",
        currencySymbols: {
            'USD': '$', 'EUR': '€', 'GBP': '£',
            'KES': 'KSh', 'UGX': 'USh', 'TZS': 'TSh'
        },
        orderId: "{{ order.id }}",
        paypalClientId: "{{ PAYPAL_CLIENT_ID }}"
    };

    window.paymentSystem = new PaymentSystem(config);
});