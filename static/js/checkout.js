// checkout.js

/**
 * Checkout page JavaScript for handling payment processing, currency updates, and UI interactions.
 * @module checkout
 */

/** @constant {boolean} DEBUG - Enable debug logging */
const DEBUG = true;

/** @constant {string} STRIPE_PUBLISHABLE_KEY - Stripe publishable key from settings */
const STRIPE_PUBLISHABLE_KEY = '{{ settings.STRIPE_PUBLISHABLE_KEY }}';

/** @constant {string} PAYMENT_URL - URL for processing payments */
const PAYMENT_URL = "{% url 'payment:process_payment' order.id %}";

/** @constant {string} SUCCESS_URL - URL for successful payment redirect */
const SUCCESS_URL = "{% url 'orders:success' %}";

/** @constant {number} CART_TOTAL - Total cart amount */
const CART_TOTAL = parseFloat("{{ cart.total_price }}");

/** @constant {string} DEFAULT_CURRENCY - Default currency code */
const DEFAULT_CURRENCY = '{{ default_currency|default:"USD" }}';

/** @constant {Object} CURRENCY_SYMBOLS - Currency symbols mapping */
const CURRENCY_SYMBOLS = {
    'USD': '$', 'EUR': '€', 'GBP': '£',
    'KES': 'KSh', 'UGX': 'USh', 'TZS': 'TSh'
};

/**
 * Logs debug messages if DEBUG is true
 * @param {string} message - Message to log
 * @param {any} [data] - Optional data to log
 */
function debugLog(message, data = null) {
    if (DEBUG) {
        console.log(`[DEBUG] ${message}`, data);
    }
}

/**
 * Sanitizes input to prevent XSS
 * @param {string} input - Input string to sanitize
 * @returns {string} Sanitized string
 */
function sanitizeInput(input) {
    const div = document.createElement('div');
    div.textContent = input;
    return div.innerHTML;
}

/**
 * Debounces a function to limit how often it can run
 * @param {Function} func - Function to debounce
 * @param {number} wait - Wait time in milliseconds
 * @returns {Function} Debounced function
 */
function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}

/** @type {Object} DOM Elements cache */
const DOM = {
    paymentForm: document.getElementById('paymentForm'),
    processingModal: document.getElementById('processingModal'),
    paymentStatus: document.getElementById('paymentStatus'),
    paymentErrors: document.getElementById('paymentErrors'),
    currencySelector: document.getElementById('currencySelector'),
    amountDisplay: document.getElementById('amountDisplay'),
    paymentSections: {
        mobileMoney: document.getElementById('mobileMoneySection'),
        card: document.getElementById('cardPaymentSection'),
        paypal: document.getElementById('paypalSection'),
        paypalContainer: document.getElementById('paypal-button-container')
    },
    paymentTabs: document.querySelectorAll('.payment-tab'),
    orderItems: document.querySelectorAll('.order-item'),
    currencySymbols: document.querySelectorAll('.currency-symbol'),
    subtotalAmount: document.querySelector('.subtotal-amount'),
    totalAmount: document.querySelector('.total-amount'),
    selectedMethod: document.getElementById('selectedMethod'),
    methodConfirmation: document.getElementById('methodConfirmation'),
    selectedMethodName: document.getElementById('selectedMethodName'),
    phoneNumber: document.getElementById('phoneNumber'),
    cardName: document.getElementById('cardName'),
    termsAgreement: document.getElementById('termsAgreement'),
    submitButton: document.getElementById('paymentSubmitButton'),
    currencyLoading: document.getElementById('currencyLoading')
};

/** @type {Object} State variables */
const state = {
    currentRate: 1,
    currentCurrency: DEFAULT_CURRENCY,
    paypalButtons: null,
    stripe: null,
    cardElement: null,
    isStripeInitialized: false
};

/**
 * Updates currency symbols in the UI
 * @param {string} currency - Currency code
 * @returns {string} Currency symbol
 */
function updateCurrencySymbols(currency) {
    const symbol = CURRENCY_SYMBOLS[currency] || currency;
    DOM.currencySymbols.forEach(el => {
        el.textContent = symbol;
    });
    return symbol;
}

/**
 * Formats amount for display
 * @param {number} amount - Amount to format
 * @param {string} currency - Currency code
 * @returns {string} Formatted amount
 */
function formatCurrency(amount, currency) {
    const decimalPlaces = ['UGX', 'TZS'].includes(currency) ? 0 : 2;
    return amount.toLocaleString('en-US', {
        minimumFractionDigits: decimalPlaces,
        maximumFractionDigits: decimalPlaces
    });
}

/**
 * Updates all amounts based on currency and rate
 * @param {number} rate - Conversion rate
 * @param {string} currency - Currency code
 */
function updateAmounts(rate, currency) {
    state.currentRate = rate;
    state.currentCurrency = currency;
    const convertedAmount = CART_TOTAL * rate;
    const formattedAmount = formatCurrency(convertedAmount, currency);

    // Update form fields
    document.getElementById('hiddenAmount').value = convertedAmount.toFixed(2);
    document.getElementById('formCurrency').value = currency;
    document.getElementById('formConversionRate').value = rate;

    // Update UI
    DOM.amountDisplay.innerHTML = `<strong>${currency} ${formattedAmount}</strong>`;
    updateCurrencySymbols(currency);

    // Update order summary
    DOM.orderItems.forEach(item => {
        const basePrice = parseFloat(item.dataset.price);
        const convertedPrice = basePrice * rate;
        item.querySelector('.item-amount').textContent = formatCurrency(convertedPrice, currency);
    });

    // Update subtotal and total
    DOM.subtotalAmount.textContent = formatCurrency(convertedAmount, currency);
    DOM.totalAmount.textContent = formatCurrency(convertedAmount, currency);
}

/**
 * Switches payment method and updates UI
 * @param {string} method - Payment method (mpesa, airtel, card, paypal)
 */
function switchPaymentMethod(method) {
    debugLog('Switching payment method', method);

    // Update tab states
    DOM.paymentTabs.forEach(tab => {
        const isActive = tab.dataset.method === method;
        tab.classList.toggle('active', isActive);
        tab.setAttribute('aria-selected', isActive.toString());
        tab.tabIndex = isActive ? 0 : -1;
        if (isActive) tab.focus();
    });

    // Toggle form sections
    const isMobileMoney = ['mpesa', 'airtel'].includes(method);
    DOM.paymentSections.mobileMoney.classList.toggle('active', isMobileMoney);
    DOM.paymentSections.mobileMoney.style.display = isMobileMoney ? 'block' : 'none';
    DOM.paymentSections.card.classList.toggle('active', method === 'card');
    DOM.paymentSections.card.style.display = method === 'card' ? 'block' : 'none';
    DOM.paymentSections.paypal.classList.toggle('active', method === 'paypal');
    DOM.paymentSections.paypal.style.display = method === 'paypal' ? 'block' : 'none';

    // Toggle submit button
    DOM.submitButton.style.display = method === 'paypal' ? 'none' : 'block';

    // Update hidden input
    DOM.selectedMethod.value = method;

    // Show confirmation
    const methodNames = {
        'mpesa': 'M-Pesa', 'airtel': 'Airtel Money',
        'card': 'Credit/Debit Card', 'paypal': 'PayPal'
    };
    DOM.selectedMethodName.textContent = methodNames[method];
    DOM.methodConfirmation.style.display = 'flex';

    // Initialize payment processors
    if (method === 'paypal' && window.paypalLoaded) {
        initializePayPalButton();
    } else if (method === 'paypal') {
        DOM.paymentSections.paypalContainer.innerHTML = '<p>PayPal is loading...</p>';
    }
    if (method === 'card' && !state.isStripeInitialized && window.stripeLoaded) {
        initializeStripe();
    } else if (method === 'card' && !window.stripeLoaded) {
        DOM.paymentSections.card.innerHTML = '<p>Card payment is loading...</p>';
    }
}

/**
 * Initializes Stripe card element
 */
function initializeStripe() {
    if (!STRIPE_PUBLISHABLE_KEY) {
        debugLog('Stripe publishable key not configured');
        DOM.paymentSections.card.innerHTML = '<p>Card payment is not available at the moment.</p>';
        return;
    }

    state.stripe = Stripe(STRIPE_PUBLISHABLE_KEY);
    const elements = state.stripe.elements();

    const style = {
        base: {
            fontSize: '16px',
            color: '#1e293b',
            fontFamily: '"Inter", sans-serif',
            '::placeholder': {
                color: '#aab7c4',
            },
        },
        invalid: {
            color: '#fa755a',
            iconColor: '#fa755a'
        }
    };

    state.cardElement = elements.create('card', {
        style: style,
        hidePostalCode: true
    });

    state.cardElement.mount('#stripeCardElement');

    state.cardElement.on('change', function(event) {
        const displayError = document.getElementById('card-errors');
        displayError.textContent = event.error ? event.error.message : '';
        displayError.style.display = event.error ? 'block' : 'none';
        displayError.setAttribute('aria-live', 'assertive');
    });

    state.isStripeInitialized = true;
}

/**
 * Initializes PayPal button
 */
function initializePayPalButton() {
    if (!window.paypalLoaded) {
        DOM.paymentSections.paypalContainer.innerHTML = '<p>PayPal is loading...</p>';
        return;
    }

    // Clean up existing button
    if (state.paypalButtons) {
        try {
            state.paypalButtons.close();
            DOM.paymentSections.paypalContainer.innerHTML = '';
        } catch (e) {
            debugLog('Error cleaning PayPal button', e);
        }
    }

    state.paypalButtons = paypal.Buttons({
        createOrder: (_, actions) => actions.order.create({
            purchase_units: [{
                amount: {
                    currency_code: state.currentCurrency,
                    value: (CART_TOTAL * state.currentRate).toFixed(2)
                }
            }]
        }),
        onApprove: (data, actions) => {
            actions.order.capture().then(details => {
                document.getElementById('paypalOrderId').value = data.orderID;
                document.getElementById('paypalPayerId').value = details.payer.payer_id;
                submitPaymentForm(new FormData(DOM.paymentForm));
            });
        },
        onError: err => {
            const statusElement = document.getElementById('paypal-status');
            statusElement.textContent = 'PayPal payment failed. Please try again or use another method.';
            statusElement.style.display = 'block';
            statusElement.setAttribute('aria-live', 'assertive');
        }
    });

    if (state.paypalButtons.isEligible()) {
        state.paypalButtons.render('#paypal-button-container');
    } else {
        DOM.paymentSections.paypalContainer.innerHTML = '<p>PayPal is not available. Please choose another method.</p>';
    }
}

/**
 * Validates phone number input
 * @returns {boolean} Whether the phone number is valid
 */
function validatePhoneNumber() {
    if (!DOM.phoneNumber) return true;
    const input = DOM.phoneNumber;
    const error = document.getElementById('phoneError');
    const isValid = /^[0-9]{9,10}$/.test(input.value);
    input.classList.toggle('invalid', !isValid);
    error.textContent = isValid ? '' : 'Please enter a valid phone number (9-10 digits)';
    error.style.display = isValid ? 'none' : 'block';
    error.setAttribute('aria-live', 'assertive');
    if (!isValid) input.focus();
    return isValid;
}

/**
 * Validates card name input
 * @returns {boolean} Whether the card name is valid
 */
function validateCardName() {
    if (!DOM.cardName) return true;
    const input = DOM.cardName;
    const error = document.getElementById('cardNameError');
    const isValid = input.value.trim().length >= 3;
    input.classList.toggle('invalid', !isValid);
    error.textContent = isValid ? '' : 'Please enter a valid name (at least 3 characters)';
    error.style.display = isValid ? 'none' : 'block';
    error.setAttribute('aria-live', 'assertive');
    if (!isValid) input.focus();
    return isValid;
}

/**
 * Handles form submission
 * @param {Event} e - Form submission event
 */
async function handleFormSubmit(e) {
    e.preventDefault();
    const method = DOM.selectedMethod.value;

    // Reset UI
    DOM.paymentStatus.style.display = 'none';
    DOM.paymentErrors.style.display = 'none';
    document.querySelectorAll('.invalid, .error-text').forEach(el => {
        el.classList.remove('invalid');
        el.style.display = 'none';
    });

    // Handle PayPal
    if (method === 'paypal') {
        DOM.paymentErrors.textContent = 'Please complete the PayPal payment process';
        DOM.paymentErrors.style.display = 'block';
        DOM.paymentErrors.setAttribute('aria-live', 'assertive');
        return;
    }

    // Handle Stripe card payment
    if (method === 'card') {
        if (!validateCardName()) return;
        if (!state.stripe || !state.cardElement) {
            DOM.paymentErrors.textContent = 'Card payment system is not available. Please try another method.';
            DOM.paymentErrors.style.display = 'block';
            DOM.paymentErrors.setAttribute('aria-live', 'assertive');
            return;
        }

        DOM.submitButton.setAttribute('aria-busy', 'true');
        DOM.processingModal.classList.add('active');

        try {
            const { paymentMethod, error } = await state.stripe.createPaymentMethod({
                type: 'card',
                card: state.cardElement,
                billing_details: {
                    name: sanitizeInput(DOM.cardName.value.trim())
                }
            });

            if (error) {
                DOM.processingModal.classList.remove('active');
                document.getElementById('card-errors').textContent = error.message;
                document.getElementById('card-errors').style.display = 'block';
                document.getElementById('card-errors').setAttribute('aria-live', 'assertive');
                DOM.submitButton.setAttribute('aria-busy', 'false');
                return;
            }

            document.getElementById('stripePaymentMethodId').value = paymentMethod.id;
            submitPaymentForm(new FormData(DOM.paymentForm));
        } catch (err) {
            debugLog('Stripe error:', err);
            DOM.processingModal.classList.remove('active');
            document.getElementById('card-errors').textContent = 'Payment processing failed. Please try again.';
            document.getElementById('card-errors').style.display = 'block';
            document.getElementById('card-errors').setAttribute('aria-live', 'assertive');
            DOM.submitButton.setAttribute('aria-busy', 'false');
        }
        return;
    }

    // Validate mobile money
    if (['mpesa', 'airtel'].includes(method) && !validatePhoneNumber()) {
        return;
    }

    // Check terms agreement
    if (!DOM.termsAgreement.checked) {
        const termsError = document.getElementById('termsError');
        termsError.textContent = 'You must agree to the terms and conditions';
        termsError.style.display = 'block';
        termsError.setAttribute('aria-live', 'assertive');
        DOM.termsAgreement.focus();
        return;
    }

    submitPaymentForm(new FormData(DOM.paymentForm));
}

/**
 * Submits payment form data to the server
 * @param {FormData} formData - Form data to submit
 */
function submitPaymentForm(formData) {
    DOM.submitButton.setAttribute('aria-busy', 'true');
    DOM.processingModal.classList.add('active');
    DOM.paymentStatus.style.display = 'block';
    DOM.paymentStatus.textContent = 'Processing your payment...';
    DOM.paymentStatus.setAttribute('aria-live', 'assertive');

    fetch(PAYMENT_URL, {
        method: 'POST',
        body: formData,
        headers: {
            'X-CSRFToken': "{{ csrf_token }}",
            'X-Requested-With': 'XMLHttpRequest',
            'X-Debug': DEBUG.toString()
        }
    })
    .then(async response => {
        const data = await response.json();

        if (data.requires_action && data.payment_intent_client_secret) {
            return handle3DSecureAuthentication(data.payment_intent_client_secret, formData);
        }

        if (data.success) {
            DOM.paymentStatus.innerHTML = 'Payment successful! Redirecting...';
            setTimeout(() => {
                window.location.href = data.redirect_url || SUCCESS_URL;
            }, 2000);
        } else {
            throw new Error(data.error_message || 'Payment processing failed');
        }
    })
    .catch(error => {
        debugLog('Payment error', error);
        DOM.processingModal.classList.remove('active');
        DOM.paymentErrors.textContent = error.message || 'An unexpected error occurred. Please try again.';
        DOM.paymentErrors.style.display = 'block';
        DOM.paymentErrors.setAttribute('aria-live', 'assertive');
        DOM.submitButton.setAttribute('aria-busy', 'false');
    });
}

/**
 * Handles 3D Secure authentication for Stripe
 * @param {string} clientSecret - Payment intent client secret
 * @param {FormData} formData - Form data
 */
function handle3DSecureAuthentication(clientSecret, formData) {
    return state.stripe.handleCardAction(clientSecret).then(result => {
        if (result.error) {
            throw new Error(result.error.message);
        }

        document.getElementById('stripePaymentIntentId').value = result.paymentIntent.id;

        return fetch(PAYMENT_URL, {
            method: 'POST',
            body: new FormData(DOM.paymentForm),
            headers: {
                'X-CSRFToken': "{{ csrf_token }}",
                'X-Requested-With': 'XMLHttpRequest',
                'X-Debug': DEBUG.toString()
            }
        });
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            DOM.paymentStatus.innerHTML = 'Payment successful! Redirecting...';
            setTimeout(() => {
                window.location.href = data.redirect_url || SUCCESS_URL;
            }, 2000);
        } else {
            throw new Error(data.error_message || 'Payment processing failed');
        }
    })
    .catch(error => {
        debugLog('3DS error', error);
        DOM.processingModal.classList.remove('active');
        DOM.paymentErrors.textContent = error.message || '3D Secure authentication failed';
        DOM.paymentErrors.style.display = 'block';
        DOM.paymentErrors.setAttribute('aria-live', 'assertive');
        DOM.submitButton.setAttribute('aria-busy', 'false');
    });
}

/**
 * Initializes the checkout page
 */
function initializePage() {
    if (!DOM.paymentForm) {
        debugLog('Payment form not found');
        return;
    }

    // Set initial values
    const initialOption = DOM.currencySelector.options[DOM.currencySelector.selectedIndex];
    const initialRate = parseFloat(initialOption.dataset.rate) || 1;
    const initialCurrency = initialOption.value || DEFAULT_CURRENCY;
    updateAmounts(initialRate, initialCurrency);

    // Set payment method
    const defaultMethod = "{{ firstof prioritized_methods.0 'card' }}";
    switchPaymentMethod(defaultMethod);

    // Event listeners
    DOM.currencySelector.addEventListener('change', debounce(function() {
        DOM.currencyLoading.style.display = 'inline-block';
        const option = this.options[this.selectedIndex];
        const rate = parseFloat(option.dataset.rate) || 1;
        const currency = option.value || DEFAULT_CURRENCY;
        updateAmounts(rate, currency);
        if (DOM.selectedMethod.value === 'paypal') {
            initializePayPalButton();
        }
        setTimeout(() => {
            DOM.currencyLoading.style.display = 'none';
        }, 500);
    }, 300));

    DOM.paymentTabs.forEach(tab => {
        tab.addEventListener('click', () => switchPaymentMethod(tab.dataset.method));
        tab.addEventListener('keydown', e => {
            if (e.key === 'Enter' || e.key === ' ') {
                e.preventDefault();
                switchPaymentMethod(tab.dataset.method);
            }
        });
    });

    DOM.paymentForm.addEventListener('submit', handleFormSubmit);
    if (DOM.phoneNumber) DOM.phoneNumber.addEventListener('input', debounce(validatePhoneNumber, 300));
    if (DOM.cardName) DOM.cardName.addEventListener('input', debounce(validateCardName, 300));
}

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', initializePage);