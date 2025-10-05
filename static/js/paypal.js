// static/js/paypal.js
import { formatCurrency } from './utils.js';
import {
    startProcessingAnimation,
    stopProcessingAnimation,
    showPayPalStatus,
    showPayPalError,
    clearPayPalStatus
} from './ui.js';

let paypalButtons = null;

export function initializePayPal(paymentSystem) {
    clearPayPalStatus();

    const state = paymentSystem.getState();
    const elements = paymentSystem.getElements();
    const config = paymentSystem.getConfig();

    const paypalButtonContainer = document.getElementById('paypal-button-container');

    // Clean up existing buttons
    if (paypalButtons) {
        try {
            paypalButtons.close();
        } catch (e) {
            console.warn('Error closing PayPal buttons:', e);
        }
        paypalButtonContainer.innerHTML = '';
    }

    if (state.paypalInitialized) return;

    try {
        if (typeof paypal === 'undefined') {
            console.error('PayPal SDK not loaded');
            document.getElementById('paypal-fallback').style.display = 'block';
            return;
        }

        let paypalCurrency = state.currentCurrency;
        let paypalAmount = state.currentConvertedAmount;

        // Handle currency conversion for unsupported currencies
        if (!isPaypalCurrencySupported(state.currentCurrency) && state.currentCurrency !== 'USD') {
            paypalCurrency = 'USD';
            const usdOption = Array.from(elements.currencySelector.options).find(opt => opt.value === 'USD');
            if (usdOption) {
                const usdRate = parseFloat(usdOption.dataset.rate);
                const baseAmount = parseFloat(config.cartTotalPrice);
                paypalAmount = state.currentConvertedAmount / usdRate;

                showPayPalStatus(
                    `Your ${state.currentCurrency} ${formatCurrency(state.currentConvertedAmount, state.currentCurrency)} payment will be processed as USD ${formatCurrency(paypalAmount, 'USD')}.`,
                    'info'
                );
            }
        }

        paypalButtons = paypal.Buttons({
            onInit: function(data, actions) {
                actions.disable();

                const enableCheck = () => {
                    if (elements.termsCheckbox && elements.termsCheckbox.checked) {
                        actions.enable();
                    } else {
                        actions.disable();
                    }
                };

                elements.termsCheckbox?.addEventListener('change', enableCheck);
            },

            onClick: function(data, actions) {
                if (!elements.termsCheckbox.checked) {
                    showPayPalError('You must agree to the terms and conditions');
                    return actions.reject();
                }
            },

            createOrder: function(data, actions) {
                return actions.order.create({
                    purchase_units: [{
                        amount: {
                            value: paypalAmount.toFixed(2),
                            currency_code: paypalCurrency
                        }
                    }]
                });
            },

            onApprove: function(data, actions) {
                paymentSystem.setState({ paypalProcessing: true });
                startProcessingAnimation('paypal', elements.processingModal, elements.modalTitle, elements.modalText);

                return actions.order.capture().then(function(details) {
                    document.getElementById('paypalOrderId').value = data.orderID;
                    document.getElementById('paypalPayerId').value = details.payer.payer_id;

                    const formData = new FormData();
                    formData.append('csrfmiddlewaretoken', config.csrfToken);
                    formData.append('order_id', config.orderId);
                    formData.append('payment_method', 'paypal');
                    formData.append('paypal_order_id', data.orderID);
                    formData.append('paypal_payer_id', details.payer.payer_id);
                    formData.append('amount', paypalAmount.toFixed(2));
                    formData.append('currency', paypalCurrency);

                    if (!isPaypalCurrencySupported(state.currentCurrency) && state.currentCurrency !== 'USD') {
                        const usdOption = Array.from(elements.currencySelector.options).find(opt => opt.value === 'USD');
                        formData.append('conversion_rate', parseFloat(usdOption.dataset.rate));
                    } else {
                        formData.append('conversion_rate', '1');
                    }

                    submitPaymentForm(formData, paymentSystem);
                }).catch(function(err) {
                    console.error('PayPal capture error:', err);
                    stopProcessingAnimation(elements.processingModal);
                    showPaymentError('Failed to complete PayPal payment. Please try again.', elements.paymentErrors);
                    paymentSystem.setState({ paypalProcessing: false });
                });
            },

            onError: function(err) {
                console.error('PayPal error:', err);
                showPayPalError('PayPal payment failed. Please try another method.');
                paymentSystem.setState({ paypalProcessing: false });
            },

            onCancel: function(data) {
                paymentSystem.setState({ paypalProcessing: false });
                showPayPalStatus('Payment canceled', 'info');
            }
        });

        if (paypalButtons.isEligible()) {
            paypalButtons.render('#paypal-button-container').then(() => {
                console.log('PayPal buttons rendered successfully');
                paymentSystem.setState({ paypalInitialized: true });
                document.getElementById('paypal-fallback').style.display = 'none';
            }).catch(err => {
                console.error('Error rendering PayPal buttons', err);
                document.getElementById('paypal-fallback').style.display = 'block';
            });
        } else {
            console.log('PayPal buttons not eligible');
            document.getElementById('paypal-fallback').style.display = 'block';
        }
    } catch (error) {
        console.error('PayPal initialization error:', error);
        document.getElementById('paypal-fallback').style.display = 'block';
    }
}

export function cleanupPayPal() {
    if (paypalButtons) {
        try {
            paypalButtons.close();
        } catch (e) {
            console.log('Error closing PayPal buttons:', e);
        }
        document.getElementById('paypal-button-container').innerHTML = '';
        paypalButtons = null;
    }
}

function isPaypalCurrencySupported(currency) {
    const paypalSupportedCurrencies = ['USD', 'EUR', 'GBP', 'CAD', 'AUD', 'JPY'];
    return paypalSupportedCurrencies.includes(currency);
}

function submitPaymentForm(formData, paymentSystem) {
    const elements = paymentSystem.getElements();
    const config = paymentSystem.getConfig();

    fetch(config.urls.processPayment, {
        method: 'POST',
        body: formData,
        headers: {
            'X-CSRFToken': config.csrfToken,
            'X-Requested-With': 'XMLHttpRequest'
        }
    })
    .then(handlePaymentResponse)
    .catch(handlePaymentError);

    function handlePaymentResponse(response) {
        if (!response.ok) return Promise.reject(response);
        return response.json().then(data => {
            if (data.success) {
                localStorage.removeItem('paymentFormState');
                elements.modalTitle.textContent = 'Payment Successful!';
                elements.modalText.textContent = 'Redirecting you to your order confirmation...';
                setTimeout(() => {
                    stopProcessingAnimation(elements.processingModal);
                    window.location.href = data.redirect_url || config.urls.orderSuccess;
                }, 2000);
            } else {
                stopProcessingAnimation(elements.processingModal);
                showPaymentError(data.error_message || 'Payment failed', elements.paymentErrors);
                setSubmitButtonState(false, elements.paymentSubmitButton);
            }
        });
    }

    function handlePaymentError(error) {
        stopProcessingAnimation(elements.processingModal);
        setSubmitButtonState(false, elements.paymentSubmitButton);

        if (error.json) {
            error.json().then(errorData => {
                showPaymentError(errorData.error_message || 'Unexpected error occurred', elements.paymentErrors);
            }).catch(() => {
                showPaymentError('Network error. Please check your connection.', elements.paymentErrors);
            });
        } else {
            showPaymentError('Network error. Please check your connection.', elements.paymentErrors);
        }
    }
}