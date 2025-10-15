//mpesa.ts

import { validatePhoneNumber } from '../utils/utils.js';
import {
  setSubmitButtonState,
  startProcessingAnimation,
  stopProcessingAnimation,
  showPaymentError,
  showPaymentStatus
} from '../ui/ui.js';
import { PaymentSystem } from '../payments.js';
import { MpesaResponse, PaymentResponse } from '../types/payment.js';

export async function initializeMpesa(paymentSystem: PaymentSystem): Promise<boolean> {
  try {
    const state = paymentSystem.getState();
    const elements = paymentSystem.getElements();
    const config = paymentSystem.getConfig();

    // Validate phone
    const phoneNumber = elements.phoneInput.value.trim();
    const formattedPhone = validatePhoneNumber(phoneNumber);
    if (!formattedPhone) {
      showPaymentError('Please enter a valid phone number', elements.paymentErrors);
      return false;
    }

    // UI: lock submit, show animation
    setSubmitButtonState(true, elements.paymentSubmitButton);
    startProcessingAnimation('mpesa', elements.processingModal, elements.modalTitle, elements.modalText);

    // Build request payload
    const payload = {
      order_id: config.orderId,
      provider: 'MPESA',
      phone: formattedPhone,
      amount: state.currentConvertedAmount,
      currency: state.currentCurrency
    };

    console.info('[MPESA] Initiating payment request payload:', payload);

    // Use URL from config
    const url = config.urls.initiatePayment;

    const response = await fetch(url, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': config.csrfToken,
        'X-Requested-With': 'XMLHttpRequest'
      },
      body: JSON.stringify(payload)
    });

    const data: MpesaResponse = await response.json();
    console.info('[MPESA] Initiate response:', data);

    if (!response.ok) {
      // show server returned error
      stopProcessingAnimation(elements.processingModal);
      setSubmitButtonState(false, elements.paymentSubmitButton);
      const err = data?.error || data?.message || 'Failed to initiate M-Pesa payment';
      showPaymentError(err, elements.paymentErrors);
      return false;
    }

    if (data.success && data.checkout_request_id) {
      // Persist checkout_request_id into client state and hidden input for finalization
      paymentSystem.setState({ lastCheckoutRequestId: data.checkout_request_id });
      try {
        const hidden = document.getElementById('checkoutRequestId') as HTMLInputElement;
        if (hidden) hidden.value = data.checkout_request_id;
      } catch (e) { /* ignore */ }

      // Optionally store in localStorage for resilience
      localStorage.setItem('lastCheckoutRequestId', data.checkout_request_id);

      elements.modalTitle.textContent = 'Payment Sent to Phone';
      elements.modalText.textContent = 'Please check your phone and approve the M-Pesa prompt.';
      showPaymentStatus('M-Pesa payment requested — awaiting confirmation on phone.', elements.paymentStatus);

      // Start polling
      pollMpesaPaymentStatus(data.checkout_request_id, paymentSystem);

      return true;
    } else {
      stopProcessingAnimation(elements.processingModal);
      setSubmitButtonState(false, elements.paymentSubmitButton);
      const err = data.error || data.message || 'M-Pesa initiation failed';
      showPaymentError(err, elements.paymentErrors);
      return false;
    }
  } catch (error) {
    console.error('M-PESA error:', error);
    const err = error instanceof Error ? error : new Error('Unknown error');
    stopProcessingAnimation(paymentSystem.getElements().processingModal);
    showPaymentError(err.message || 'Network error. Please try again.', paymentSystem.getElements().paymentErrors);
    setSubmitButtonState(false, paymentSystem.getElements().paymentSubmitButton);
    return false;
  }
}

function pollMpesaPaymentStatus(checkoutRequestId: string, paymentSystem: PaymentSystem): void {
  const elements = paymentSystem.getElements();
  const config = paymentSystem.getConfig();

  const pollInterval = 3000;
  const maxAttempts = 40;
  let attempts = 0;

  const poller = setInterval(async () => {
    attempts++;
    if (attempts > maxAttempts) {
      clearInterval(poller);
      stopProcessingAnimation(elements.processingModal);
      setSubmitButtonState(false, elements.paymentSubmitButton);
      showPaymentError('Payment timed out. Please check your phone or try again.', elements.paymentErrors);
      return;
    }

    try {
      const statusUrl = new URL(config.urls.mpesaStatus, window.location.origin);
      statusUrl.searchParams.set('checkout_request_id', checkoutRequestId);

      const resp = await fetch(statusUrl.toString(), {
        method: 'GET',
        headers: { 'X-Requested-With': 'XMLHttpRequest' }
      });
      const json: MpesaResponse = await resp.json();
      console.info('[MPESA] poll status:', json);

      if (json.status === 'success' || json.status === 'completed') {
        clearInterval(poller);
        elements.modalTitle.textContent = 'Payment Confirmed';
        elements.modalText.textContent = 'Finalizing your order...';
        // proceed to finalize order on server
        finalizeMpesaPayment(checkoutRequestId, paymentSystem);
      } else if (json.status === 'failed' || json.status === 'error') {
        clearInterval(poller);
        stopProcessingAnimation(elements.processingModal);
        setSubmitButtonState(false, elements.paymentSubmitButton);
        showPaymentError(json.message || 'Payment failed', elements.paymentErrors);
      } else {
        // still pending: update UI optionally
        showPaymentStatus('Awaiting M-Pesa confirmation...', elements.paymentStatus);
      }
    } catch (err) {
      console.error('[MPESA] polling error', err);
      // continue polling but log
    }
  }, pollInterval);
}

function finalizeMpesaPayment(checkoutRequestId: string, paymentSystem: PaymentSystem): void {
  const elements = paymentSystem.getElements();
  const config = paymentSystem.getConfig();
  const state = paymentSystem.getState();

  // ✅ Fallbacks for missing checkoutRequestId
  const finalCheckoutRequestId =
    checkoutRequestId ||
    state.lastCheckoutRequestId ||
    (document.getElementById('checkoutRequestId') as HTMLInputElement)?.value ||
    localStorage.getItem('lastCheckoutRequestId');

  console.info('[MPESA] Finalizing payment with checkout_request_id:', finalCheckoutRequestId);

  if (!finalCheckoutRequestId) {
    stopProcessingAnimation(elements.processingModal);
    setSubmitButtonState(false, elements.paymentSubmitButton);
    showPaymentError('Missing M-Pesa transaction reference. Please retry.', elements.paymentErrors);
    return;
  }

  // ✅ Prepare request body
  const formData = new FormData();
  formData.append('csrfmiddlewaretoken', config.csrfToken);
  formData.append('order_id', config.orderId);
  formData.append('payment_method', 'mpesa');
  formData.append('checkout_request_id', finalCheckoutRequestId);
  formData.append('phone_number', elements.phoneInput.value.trim());
  formData.append('amount', state.currentConvertedAmount.toString());
  formData.append('currency', state.currentCurrency);
  formData.append('conversion_rate', state.currentRate.toString());

  // ✅ Send request
  fetch(config.urls.processPayment, {
    method: 'POST',
    headers: {
      'X-CSRFToken': config.csrfToken,
      'X-Requested-With': 'XMLHttpRequest'
    },
    body: formData
  })
    .then(async (resp) => {
      const data: PaymentResponse = await resp.json();
      console.info('[MPESA] finalize response:', data);

      if (!resp.ok) throw new Error(data.error_message || data.message || 'Failed to verify M-Pesa payment');

      if (data.success || data.status === 'success') {
        elements.modalTitle.textContent = 'Payment Successful!';
        elements.modalText.textContent = 'Redirecting to your order confirmation...';
        setTimeout(() => {
          stopProcessingAnimation(elements.processingModal);
          window.location.href = data.redirect_url || config.urls.orderSuccess;
        }, 1500);
      } else {
        stopProcessingAnimation(elements.processingModal);
        setSubmitButtonState(false, elements.paymentSubmitButton);
        showPaymentError(data.message || data.error_message || 'Payment verification failed', elements.paymentErrors);
      }
    })
    .catch((err: any) => {
      console.error('[MPESA] finalize error:', err);
      stopProcessingAnimation(elements.processingModal);
      setSubmitButtonState(false, elements.paymentSubmitButton);
      showPaymentError(err.message || 'Error finalizing payment', elements.paymentErrors);
    });
}