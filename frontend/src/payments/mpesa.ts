import { validatePhoneNumber, fetchWithTimeout } from './utils.js';
import {
  setSubmitButtonState,
  startProcessingAnimation,
  stopProcessingAnimation,
  showPaymentError,
  showPaymentStatus
} from './ui.js';
import { PaymentSystem } from './payments.js';
import { MpesaResponse, PaymentResponse } from '@/payments/types/payment.ts';
import { storage } from './storage.js';

// ✅ Singleton state management
class MpesaPaymentManager {
  private static instance: MpesaPaymentManager;
  private paymentInProgress: boolean = false;
  private finalizationInProgress: boolean = false;
  private activePoller: number | null = null;
  private currentCheckoutRequestId: string | null = null;

  private constructor() {}

  static getInstance(): MpesaPaymentManager {
    if (!MpesaPaymentManager.instance) {
      MpesaPaymentManager.instance = new MpesaPaymentManager();
    }
    return MpesaPaymentManager.instance;
  }

  isPaymentInProgress(): boolean {
    return this.paymentInProgress || this.finalizationInProgress;
  }

  startPayment(checkoutRequestId: string): void {
    this.paymentInProgress = true;
    this.currentCheckoutRequestId = checkoutRequestId;
  }

  startFinalization(): boolean {
    if (this.finalizationInProgress) {
      console.warn('[MPESA] Finalization already in progress');
      return false;
    }
    this.finalizationInProgress = true;
    return true;
  }

  reset(): void {
    this.paymentInProgress = false;
    this.finalizationInProgress = false;
    this.currentCheckoutRequestId = null;
    if (this.activePoller !== null) {
      clearInterval(this.activePoller);
      this.activePoller = null;
    }
  }

  setPoller(pollerId: number): void {
    this.activePoller = pollerId;
  }

  clearPoller(): void {
    if (this.activePoller !== null) {
      clearInterval(this.activePoller);
      this.activePoller = null;
    }
  }
}

const manager = MpesaPaymentManager.getInstance();

export async function initializeMpesa(paymentSystem: PaymentSystem): Promise {
  if (manager.isPaymentInProgress()) {
    console.warn('[MPESA] Payment already in progress');
    return false;
  }

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

    const payload = {
      order_id: config.orderId,
      provider: 'MPESA',
      phone: formattedPhone,
      amount: state.currentConvertedAmount,
      currency: state.currentCurrency
    };

    const response = await fetchWithTimeout(
      config.urls.initiatePayment,
      {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': config.csrfToken,
          'X-Requested-With': 'XMLHttpRequest'
        },
        body: JSON.stringify(payload)
      },
      30000
    );

    const data: MpesaResponse = await response.json();

    if (!response.ok || !data.success || !data.checkout_request_id) {
      stopProcessingAnimation(elements.processingModal);
      setSubmitButtonState(false, elements.paymentSubmitButton);
      showPaymentError(data?.error || 'Failed to initiate M-Pesa payment', elements.paymentErrors);
      return false;
    }

    // ✅ Mark payment as started
    manager.startPayment(data.checkout_request_id);

    paymentSystem.setState({ lastCheckoutRequestId: data.checkout_request_id });

    const hidden = document.getElementById('checkoutRequestId') as HTMLInputElement;
    if (hidden) hidden.value = data.checkout_request_id;

    storage.setItem('lastCheckoutRequestId', data.checkout_request_id);

    elements.modalTitle.textContent = 'Payment Sent to Phone';
    elements.modalText.textContent = 'Please check your phone and approve the M-Pesa prompt.';

    pollMpesaPaymentStatus(data.checkout_request_id, paymentSystem);
    return true;

  } catch (error) {
    console.error('[MPESA] Error:', error);
    stopProcessingAnimation(paymentSystem.getElements().processingModal);
    setSubmitButtonState(false, paymentSystem.getElements().paymentSubmitButton);
    manager.reset();

    const errorMessage = error instanceof Error ? error.message : 'Network error. Please try again.';
    showPaymentError(errorMessage, paymentSystem.getElements().paymentErrors);
    return false;
  }
}

function pollMpesaPaymentStatus(checkoutRequestId: string, paymentSystem: PaymentSystem): void {
  const elements = paymentSystem.getElements();
  const config = paymentSystem.getConfig();

  manager.clearPoller();

  const pollInterval = 3000;
  const maxAttempts = 40;
  let attempts = 0;

  const pollerId = window.setInterval(async () => {
    attempts++;

    if (attempts > maxAttempts) {
      manager.clearPoller();
      stopProcessingAnimation(elements.processingModal);
      setSubmitButtonState(false, elements.paymentSubmitButton);
      manager.reset();
      showPaymentError('Payment timed out. Please try again.', elements.paymentErrors);
      return;
    }

    try {
      const statusUrl = new URL(config.urls.mpesaStatus, window.location.origin);
      statusUrl.searchParams.set('checkout_request_id', checkoutRequestId);

      const resp = await fetch(statusUrl.toString(), {
        method: 'GET',
        headers: { 'X-Requested-With': 'XMLHttpRequest' }
      });

      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);

      const json: MpesaResponse = await resp.json();

      if (json.status === 'success' || json.status === 'completed') {
        manager.clearPoller();
        elements.modalTitle.textContent = 'Payment Confirmed!';
        elements.modalText.textContent = 'Finalizing your order...';
        finalizeMpesaPayment(checkoutRequestId, paymentSystem);

      } else if (json.status === 'failed' || json.status === 'cancelled') {
        manager.clearPoller();
        stopProcessingAnimation(elements.processingModal);
        setSubmitButtonState(false, elements.paymentSubmitButton);
        manager.reset();
        showPaymentError(json.message || 'Payment failed', elements.paymentErrors);
      }

    } catch (err) {
      console.error('[MPESA] polling error', err);
    }
  }, pollInterval);

  manager.setPoller(pollerId);
}

function finalizeMpesaPayment(checkoutRequestId: string, paymentSystem: PaymentSystem): void {
  // ✅ Prevent duplicate finalization
  if (!manager.startFinalization()) {
    return;
  }

  const elements = paymentSystem.getElements();
  const config = paymentSystem.getConfig();
  const state = paymentSystem.getState();

  const formData = new FormData();
  formData.append('csrfmiddlewaretoken', config.csrfToken);
  formData.append('order_id', config.orderId);
  formData.append('payment_method', 'mpesa');
  formData.append('checkout_request_id', checkoutRequestId);
  formData.append('phone_number', elements.phoneInput.value.trim());
  formData.append('amount', state.currentConvertedAmount.toString());
  formData.append('currency', state.currentCurrency);
  formData.append('conversion_rate', state.currentRate.toString());

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

      if (data.success || data.status === 'success' || data.message?.includes('already')) {
        storage.removeItem('lastCheckoutRequestId');
        storage.removeItem('paymentFormState');
        manager.reset();

        elements.modalTitle.textContent = 'Payment Successful!';
        elements.modalText.textContent = 'Redirecting...';

        setTimeout(() => {
          stopProcessingAnimation(elements.processingModal);
          window.location.href = data.redirect_url || config.urls.orderSuccess;
        }, 1500);
      } else {
        throw new Error(data.message || 'Payment verification failed');
      }
    })
    .catch((err: any) => {
      console.error('[MPESA] finalize error:', err);
      stopProcessingAnimation(elements.processingModal);
      setSubmitButtonState(false, elements.paymentSubmitButton);
      manager.reset();
      showPaymentError(err.message || 'Error finalizing payment', elements.paymentErrors);
    });
}

export function resetMpesaPaymentState(): void {
  manager.reset();
  console.info('[MPESA] Payment state reset');
}