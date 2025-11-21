// frontend/src/payments/paystack.ts - FULLY FIXED VERSION

import { fetchWithTimeout, validateEmail } from './utils.js';
import {
  setSubmitButtonState,
  startProcessingAnimation,
  stopProcessingAnimation,
  showPaymentError,
  showPaystackStatus,
  clearPaystackStatus,
  showInputError
} from './ui.js';
import { PaymentSystem } from './payments.js';
import { storage } from './storage.js';

class PaystackPaymentManager {
  private static instance: PaystackPaymentManager;
  private paymentInProgress: boolean = false;
  private currentReference: string | null = null;

  private constructor() {}

  static getInstance(): PaystackPaymentManager {
    if (!PaystackPaymentManager.instance) {
      PaystackPaymentManager.instance = new PaystackPaymentManager();
    }
    return PaystackPaymentManager.instance;
  }

  getCurrentReference(): string | null {
    return this.currentReference;
  }

  setCurrentReference(ref: string): void {
    this.currentReference = ref;
  }

  isPaymentInProgress(): boolean {
    return this.paymentInProgress;
  }

  setPaymentInProgress(inProgress: boolean): void {
    this.paymentInProgress = inProgress;
  }

  reset(): void {
    this.paymentInProgress = false;
    this.currentReference = null;
    storage.removeItem('lastPaystackReference');
  }
}

const manager = PaystackPaymentManager.getInstance();

export async function initializePaystack(paymentSystem: PaymentSystem): Promise<boolean> {
  const state = paymentSystem.getState();
  const elements = paymentSystem.getElements();
  const config = paymentSystem.getConfig();

  console.log('[PAYSTACK] 🚀 Initialization started (Standard Redirect Flow)');

  // Clear previous status messages
  clearPaystackStatus();
  const span = elements.paymentErrors.querySelector('span');
  if (span) span.textContent = '';
  elements.paymentErrors.style.display = 'none';

  // Get and validate email from the input field
  const emailInput = elements.paystackEmailInput;

  if (!emailInput) {
    console.error('[PAYSTACK] ❌ Email input element not found');
    showPaymentError('Email input not found. Please refresh the page.', elements.paymentErrors);
    return false;
  }

  const email = emailInput.value.trim();

  if (!email) {
    console.warn('[PAYSTACK] ⚠️ Email is empty');
    showInputError(
      emailInput,
      elements.paystackEmailError,
      'A valid email address is required for Paystack payment.'
    );
    emailInput.focus();
    return false;
  }

  if (!validateEmail(email)) {
    console.warn('[PAYSTACK] ⚠️ Email format invalid:', email);
    showInputError(
      emailInput,
      elements.paystackEmailError,
      'Please enter a valid email address.'
    );
    emailInput.focus();
    return false;
  }

  console.log('[PAYSTACK] ✅ Email validated:', email);

  // Prepare button state
  setSubmitButtonState(true, elements.paymentSubmitButton);
  showPaystackStatus('Initializing secure payment...', 'info');

  console.log('[PAYSTACK] 📡 Sending initialization request to:', config.urls.initializePaystack);

  try {
    const response = await fetchWithTimeout(config.urls.initializePaystack!, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': config.csrfToken
      },
      body: JSON.stringify({
        order_id: config.orderId,
        amount: state.currentConvertedAmount,
        currency: state.currentCurrency,
        email: email
      })
    });

    const data = await response.json();

    if (response.ok && data.success && data.authorization_url) {
      console.log('[PAYSTACK] ✅ Backend initialization successful. Redirecting...');
      showPaystackStatus('Redirecting to secure payment page...', 'success');

      // Save reference in storage
      if (data.reference) {
        manager.setCurrentReference(data.reference);
        storage.setItem('lastPaystackReference', data.reference);
      }

      // Save email to form state for potential retry
      const currentFormState = storage.getItem('paymentFormState');
      const formState = currentFormState ? JSON.parse(currentFormState) : {};
      formState.email = email;
      storage.setItem('paymentFormState', JSON.stringify(formState));

      // Redirect user to the Paystack hosted payment page
      setTimeout(() => {
        window.location.href = data.authorization_url;
      }, 500);

      return new Promise(() => {}); // Never resolves as page will redirect
    } else {
      const message = data.error || data.error_message || data.message || 'Failed to initialize Paystack payment.';
      showPaymentError(message, elements.paymentErrors);
      setSubmitButtonState(false, elements.paymentSubmitButton);
      manager.reset();
      return false;
    }
  } catch (error) {
    console.error('[PAYSTACK] Initialization error:', error);
    const errorMessage = error instanceof Error ? error.message : 'Network error during payment initialization.';
    showPaymentError(errorMessage, elements.paymentErrors);
    setSubmitButtonState(false, elements.paymentSubmitButton);
    manager.reset();
    return false;
  }
}

export async function verifyPaystackPayment(
  reference: string,
  paymentSystem: PaymentSystem,
  retryCount: number = 0
): Promise<void> {
  const MAX_RETRIES = 20; // 20 retries * 3s = 60 seconds
  const elements = paymentSystem.getElements();
  const config = paymentSystem.getConfig();

  console.log(`[PAYSTACK] Verifying payment: ${reference} (Attempt ${retryCount + 1}/${MAX_RETRIES})`);

  // Ensure processing modal is visible
  if (!elements.processingModal.classList.contains('active')) {
    startProcessingAnimation('paystack', elements.processingModal, elements.modalTitle, elements.modalText);
  }

  setSubmitButtonState(true, elements.paymentSubmitButton);

  try {
    const response = await fetchWithTimeout(config.urls.paystackStatus!, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': config.csrfToken
      },
      body: JSON.stringify({ reference: reference })
    });

    const data = await response.json();

    if (data.status === 'completed' && data.order_id) {
      // Payment verified successfully
      console.log('[PAYSTACK] ✅ Payment completed!');
      stopProcessingAnimation(elements.processingModal);
      showPaystackStatus('Payment verified! Redirecting...', 'success');
      manager.reset();

      // Clear storage
      storage.removeItem('paymentFormState');
      storage.removeItem('lastCheckoutRequestId');
      storage.removeItem('lastPaystackReference');

      setTimeout(() => {
        window.location.href = config.urls.orderSuccess.replace(config.orderId, data.order_id);
      }, 1500);
    } else if (data.status === 'failed') {
      // Payment failed
      console.log('[PAYSTACK] ❌ Payment failed');
      stopProcessingAnimation(elements.processingModal);
      setSubmitButtonState(false, elements.paymentSubmitButton);
      manager.reset();
      showPaymentError(data.message || 'Payment verification failed. Please try again.', elements.paymentErrors);
    } else if (data.status === 'pending' || data.status === 'processing') {
      if (retryCount >= MAX_RETRIES) {
        // Give up after max retries
        console.warn('[PAYSTACK] ⏱️ Polling timeout. Payment still processing.');
        stopProcessingAnimation(elements.processingModal);
        setSubmitButtonState(false, elements.paymentSubmitButton);
        manager.reset();
        showPaymentError(
          'Payment is still processing. We will update your order once confirmed. Please check your order history or contact support if this persists.',
          elements.paymentErrors
        );
      } else {
        // Still processing - poll again after 3 seconds
        console.log('[PAYSTACK] ⏳ Payment still processing, polling again...');
        setTimeout(() => verifyPaystackPayment(reference, paymentSystem, retryCount + 1), 3000);
      }
    } else {
      // Unknown status
      console.error('[PAYSTACK] ❓ Unknown status:', data.status);
      stopProcessingAnimation(elements.processingModal);
      setSubmitButtonState(false, elements.paymentSubmitButton);
      manager.reset();
      const errorMsg = data.message || 'Unable to verify payment status. Please contact support.';
      showPaymentError(errorMsg, elements.paymentErrors);
    }
  } catch (error) {
    console.error('[PAYSTACK] Verification error:', error);
    stopProcessingAnimation(elements.processingModal);
    setSubmitButtonState(false, elements.paymentSubmitButton);
    manager.reset();
    const errorMessage = error instanceof Error ? error.message : 'Network error verifying payment.';
    showPaymentError(errorMessage, elements.paymentErrors);
  }
}

export function resetPaystackPaymentState(): void {
  manager.reset();
  console.info('[PAYSTACK] Payment state reset');
}

export function checkExistingPaystackPayment(paymentSystem: PaymentSystem): void {
  const existingReference = storage.getItem('lastPaystackReference');

  if (existingReference) {
    console.warn('[PAYSTACK] Found existing payment reference:', existingReference);
    const elements = paymentSystem.getElements();

    showPaystackStatus('Resuming previous payment session...', 'info');

    // Switch to Paystack method and start processing animation
    paymentSystem.setState({ currentMethod: 'paystack' });
    startProcessingAnimation('paystack', elements.processingModal, elements.modalTitle, elements.modalText);

    // Verify the payment status
    setTimeout(() => {
      verifyPaystackPayment(existingReference, paymentSystem, 0);
    }, 1000);
  }
}