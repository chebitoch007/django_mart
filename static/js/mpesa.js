// static/js/mpesa.js
import { validatePhoneNumber } from './utils.js';
import {
    setSubmitButtonState,
    startProcessingAnimation,
    stopProcessingAnimation,
    showPaymentError
} from './ui.js';

export async function initializeMpesa(paymentSystem) {
    try {
        const state = paymentSystem.getState();
        const elements = paymentSystem.getElements();
        const config = paymentSystem.getConfig();

        const phoneNumber = elements.phoneInput.value.trim();
        const formattedPhone = validatePhoneNumber(phoneNumber);

        if (!formattedPhone) {
            showPaymentError('Please enter a valid phone number', elements.paymentErrors);
            return false;
        }

        setSubmitButtonState(true, elements.paymentSubmitButton);
        startProcessingAnimation('mpesa', elements.processingModal, elements.modalTitle, elements.modalText);

        const response = await fetch('{% url "payment:initiate_payment" %}', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': config.csrfToken
            },
            body: JSON.stringify({
                phone: formattedPhone,
                amount: state.currentConvertedAmount,
                order_id: config.orderId,
                currency: state.currentCurrency,
                provider: 'MPESA'
            })
        });

        const data = await response.json();
        if (data.success) {
            elements.modalTitle.textContent = 'Payment Sent to Phone';
            elements.modalText.textContent = 'Please check your phone and complete the M-Pesa transaction.';
            pollMpesaPaymentStatus(data.checkout_request_id, paymentSystem);
            return true;
        } else {
            throw new Error(data.error || 'Failed to initiate payment');
        }
    } catch (error) {
        console.error('M-PESA error:', error);
        stopProcessingAnimation(elements.processingModal);
        showPaymentError(error.message || 'Network error. Please try again.', elements.paymentErrors);
        setSubmitButtonState(false, elements.paymentSubmitButton);
        return false;
    }
}

function pollMpesaPaymentStatus(checkoutRequestId, paymentSystem) {
    const pollInterval = 3000;
    const maxAttempts = 20;
    let attempts = 0;

    const elements = paymentSystem.getElements();
    const config = paymentSystem.getConfig();

    const poller = setInterval(() => {
        attempts++;

        if (attempts > maxAttempts) {
            clearInterval(poller);
            stopProcessingAnimation(elements.processingModal);
            showPaymentError('Payment timed out. Please check your phone or try again.', elements.paymentErrors);
            setSubmitButtonState(false, elements.paymentSubmitButton);
            return;
        }

        fetch(`{% url 'payment:mpesa_status' %}?checkout_request_id=${checkoutRequestId}`)
            .then(response => response.json())
            .then(data => {
                if (data.status === 'success') {
                    clearInterval(poller);
                    elements.modalTitle.textContent = 'Payment Confirmed';
                    elements.modalText.textContent = 'Finalizing your order...';
                    finalizeMpesaPayment(checkoutRequestId, paymentSystem);
                } else if (data.status === 'failed') {
                    clearInterval(poller);
                    stopProcessingAnimation(elements.processingModal);
                    showPaymentError(data.message || 'Payment failed', elements.paymentErrors);
                    setSubmitButtonState(false, elements.paymentSubmitButton);
                }
            })
            .catch(error => {
                console.error("Polling error:", error);
            });
    }, pollInterval);
}

function finalizeMpesaPayment(checkoutRequestId, paymentSystem) {
    const state = paymentSystem.getState();
    const elements = paymentSystem.getElements();
    const config = paymentSystem.getConfig();

    fetch(`/payment/process-payment/${config.orderId}/`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/x-www-form-urlencoded',
            'X-CSRFToken': config.csrfToken
        },
        body: new URLSearchParams({
            order_id: config.orderId,
            payment_method: 'mpesa',
            checkout_request_id: checkoutRequestId,
            phone_number: elements.phoneInput.value,
            amount: elements.formAmount.value,
            currency: state.currentCurrency,
            conversion_rate: 1
        })
    })
    .then(res => res.json())
    .then(data => {
        if (data.success) {
            elements.modalTitle.textContent = 'Payment Successful!';
            elements.modalText.textContent = 'Redirecting you to your order confirmation...';
            setTimeout(() => {
                stopProcessingAnimation(elements.processingModal);
                window.location.href = data.redirect_url;
            }, 2000);
        } else {
            stopProcessingAnimation(elements.processingModal);
            showPaymentError(data.error_message || 'Payment verification failed', elements.paymentErrors);
            setSubmitButtonState(false, elements.paymentSubmitButton);
        }
    })
    .catch(error => {
        console.error('Finalization error:', error);
        stopProcessingAnimation(elements.processingModal);
        showPaymentError('Error finalizing payment', elements.paymentErrors);
        setSubmitButtonState(false, elements.paymentSubmitButton);
    });
}