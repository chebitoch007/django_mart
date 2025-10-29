//mpesa.ts

import { validatePhoneNumber } from './utils.js';
import {
  setSubmitButtonState,
  startProcessingAnimation,
  stopProcessingAnimation,
  showPaymentError,
  showPaymentStatus
} from './ui.js';
import { PaymentSystem } from './payments.js';
import { MpesaResponse, PaymentResponse } from '@/payments/types/payment.ts';

// ✅ Global flag to prevent duplicate payment attempts
let paymentInProgress = false;
let activePoller: number | null = null;

export async function initializeMpesa(paymentSystem: PaymentSystem): Promise<boolean> {
  // ✅ CRITICAL: Prevent duplicate payments
  if (paymentInProgress) {
    console.warn('[MPESA] Payment already in progress, ignoring duplicate attempt');
    return false;
  }

  try {
    paymentInProgress = true;
    const state = paymentSystem.getState();
    const elements = paymentSystem.getElements();
    const config = paymentSystem.getConfig();

    // Validate phone
    const phoneNumber = elements.phoneInput.value.trim();
    const formattedPhone = validatePhoneNumber(phoneNumber);
    if (!formattedPhone) {
      showPaymentError('Please enter a valid phone number', elements.paymentErrors);
      paymentInProgress = false;
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
      paymentInProgress = false;
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
      showPaymentStatus('M-Pesa payment requested – awaiting confirmation on phone.', elements.paymentStatus);

      // Start polling
      pollMpesaPaymentStatus(data.checkout_request_id, paymentSystem);

      return true;
    } else {
      stopProcessingAnimation(elements.processingModal);
      setSubmitButtonState(false, elements.paymentSubmitButton);
      paymentInProgress = false;
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
    paymentInProgress = false;
    return false;
  }
}

function pollMpesaPaymentStatus(checkoutRequestId: string, paymentSystem: PaymentSystem): void {
  const elements = paymentSystem.getElements();
  const config = paymentSystem.getConfig();

  // ✅ Clear any existing poller
  if (activePoller !== null) {
    clearInterval(activePoller);
    activePoller = null;
  }

  const pollInterval = 3000;
  const maxAttempts = 40; // 2 minutes total
  let attempts = 0;

  activePoller = window.setInterval(async () => {
    attempts++;

    // Update UI with attempt count
    if (attempts % 5 === 0) { // Every 15 seconds
      showPaymentStatus(`Still waiting for payment confirmation... (${attempts}/${maxAttempts})`, elements.paymentStatus);
    }

    if (attempts > maxAttempts) {
      if (activePoller !== null) clearInterval(activePoller);
      activePoller = null;
      stopProcessingAnimation(elements.processingModal);
      setSubmitButtonState(false, elements.paymentSubmitButton);
      paymentInProgress = false;
      showPaymentError(
        'Payment timed out. Please check your phone to complete the M-Pesa payment, or try again.',
        elements.paymentErrors
      );
      return;
    }

    try {
      const statusUrl = new URL(config.urls.mpesaStatus, window.location.origin);
      statusUrl.searchParams.set('checkout_request_id', checkoutRequestId);

      const resp = await fetch(statusUrl.toString(), {
        method: 'GET',
        headers: { 'X-Requested-With': 'XMLHttpRequest' }
      });

      if (!resp.ok) {
        throw new Error(`HTTP ${resp.status}`);
      }

      const json: MpesaResponse = await resp.json();
      console.info('[MPESA] poll status:', json, `Attempt: ${attempts}/${maxAttempts}`);

      if (json.status === 'success' || json.status === 'completed') {
        // ✅ Stop polling immediately
        if (activePoller !== null) clearInterval(activePoller);
        activePoller = null;

        elements.modalTitle.textContent = 'Payment Confirmed!';
        elements.modalText.textContent = 'Finalizing your order...';
        showPaymentStatus('Payment confirmed! Finalizing order...', elements.paymentStatus);

        // ✅ Finalize payment (only once)
        finalizeMpesaPayment(checkoutRequestId, paymentSystem);

      } else if (json.status === 'failed' || json.status === 'cancelled' || json.status === 'error') {
        // ✅ Stop polling on failure
        if (activePoller !== null) clearInterval(activePoller);
        activePoller = null;

        stopProcessingAnimation(elements.processingModal);
        setSubmitButtonState(false, elements.paymentSubmitButton);
        paymentInProgress = false;
        showPaymentError(
          json.message || 'Payment failed or was cancelled. Please try again.',
          elements.paymentErrors
        );
      } else {
        // Still processing - update status message occasionally
        if (attempts === 1) {
          showPaymentStatus('Payment initiated. Please check your phone and enter your M-Pesa PIN.', elements.paymentStatus);
        }
      }
    } catch (err) {
      console.error('[MPESA] polling error', err);
      // Don't stop on network errors, just log and continue
      if (attempts % 10 === 0) { // Log every 30 seconds
        showPaymentStatus('Having trouble checking payment status. Still trying...', elements.paymentStatus);
      }
    }
  }, pollInterval);
}

// ✅ Prevent duplicate finalization
let finalizationInProgress = false;

function finalizeMpesaPayment(checkoutRequestId: string, paymentSystem: PaymentSystem): void {
  // ✅ CRITICAL: Prevent duplicate finalization calls
  if (finalizationInProgress) {
    console.warn('[MPESA] Finalization already in progress, ignoring duplicate call');
    return;
  }

  finalizationInProgress = true;

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
    paymentInProgress = false;
    finalizationInProgress = false;
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

      if (!resp.ok) {
        // ✅ Check if already processed (not an error)
        if (data.message && data.message.includes('already')) {
          console.info('[MPESA] Order already processed, redirecting...');
          elements.modalTitle.textContent = 'Payment Complete!';
          elements.modalText.textContent = 'Redirecting to your order...';
          setTimeout(() => {
            stopProcessingAnimation(elements.processingModal);
            window.location.href = data.redirect_url || config.urls.orderSuccess;
          }, 1000);
          return;
        }
        throw new Error(data.error_message || data.message || 'Failed to verify M-Pesa payment');
      }

      if (data.success || data.status === 'success') {
        // ✅ Clear localStorage
        localStorage.removeItem('lastCheckoutRequestId');
        localStorage.removeItem('paymentFormState');

        elements.modalTitle.textContent = 'Payment Successful!';
        elements.modalText.textContent = 'Redirecting to your order confirmation...';

        setTimeout(() => {
          stopProcessingAnimation(elements.processingModal);
          window.location.href = data.redirect_url || config.urls.orderSuccess;
        }, 1500);
      } else {
        stopProcessingAnimation(elements.processingModal);
        setSubmitButtonState(false, elements.paymentSubmitButton);
        paymentInProgress = false;
        finalizationInProgress = false;
        showPaymentError(data.message || data.error_message || 'Payment verification failed', elements.paymentErrors);
      }
    })
    .catch((err: any) => {
      console.error('[MPESA] finalize error:', err);
      stopProcessingAnimation(elements.processingModal);
      setSubmitButtonState(false, elements.paymentSubmitButton);
      paymentInProgress = false;
      finalizationInProgress = false;
      showPaymentError(err.message || 'Error finalizing payment', elements.paymentErrors);
    });
}

// ✅ Export function to reset payment state (for retry scenarios)
export function resetMpesaPaymentState(): void {
  paymentInProgress = false;
  finalizationInProgress = false;
  if (activePoller !== null) {
    clearInterval(activePoller);
    activePoller = null;
  }
  console.info('[MPESA] Payment state reset');
}