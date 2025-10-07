// Phone number validation
export function validatePhoneNumber(phoneNumber) {
    if (!phoneNumber)
        return false;
    const cleanPhone = phoneNumber.trim().replace(/\s+/g, '');
    const phoneRegex = /^(?:254|\+254|0)?(7[0-9]{8})$/;
    const match = cleanPhone.match(phoneRegex);
    if (!match)
        return false;
    return `254${match[1]}`;
}
// Currency formatting
export function formatCurrency(amount, currency) {
    const decimalPlaces = currency === 'UGX' || currency === 'TZS' ? 0 : 2;
    return amount.toLocaleString('en-US', {
        minimumFractionDigits: decimalPlaces,
        maximumFractionDigits: decimalPlaces
    });
}
export function saveFormState(state) {
    localStorage.setItem('paymentFormState', JSON.stringify(state));
}
export function restoreFormState() {
    return JSON.parse(localStorage.getItem('paymentFormState') || '{}');
}
// Server communication
export function updateServerPaymentMethod(method, csrfToken) {
    // This would be updated with your actual endpoint
    fetch('/api/update-payment-method', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/x-www-form-urlencoded',
            'X-CSRFToken': csrfToken
        },
        body: `method=${method}`
    }).catch(console.error);
}
// Payment method display names
export function getMethodDisplayName(method) {
    const methodNames = {
        'mpesa': 'M-Pesa',
        'paypal': 'PayPal'
    };
    return methodNames[method] || method;
}
// Check if PayPal supports currency
export function isPaypalCurrencySupported(currency) {
    const paypalSupportedCurrencies = ['USD', 'EUR', 'GBP', 'CAD', 'AUD', 'JPY'];
    return paypalSupportedCurrencies.includes(currency);
}
//# sourceMappingURL=utils.js.map