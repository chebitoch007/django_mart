// frontend/src/payments/paystack.ts

import { fetchWithTimeout } from './utils.js';
import {
  setSubmitButtonState,
  startProcessingAnimation,
  stopProcessingAnimation,
  showPaymentError,
  showPaymentStatus,
  showPaystackStatus,
  clearPaystackStatus
} from './ui.js';
import { PaymentSystem } from './payments.js';
import { storage } from './storage.js';

// Paystack types
interface PaystackPopup {
  setup(config: PaystackConfig): void;
  resumeTransaction(accessCode: string): void;
  newTransaction(config: PaystackConfig): void;
  openIframe(): void;
}

interface PaystackConfig {
  key: string;
  email: string;
  amount: number;
  currency: string;
  ref: string;
  onClose: () => void;
  callback: (response: PaystackResponse) => void;
}

interface PaystackResponse {
  reference: string;
  status: string;
  message: string;
  trans: string;
  transaction: string;
  trxref: string;
}

declare global {
  interface Window {
    PaystackPop?: {
      setup(config: PaystackConfig): PaystackPopup;
    };
  }
}

class PaystackPaymentManager {
  private static instance: PaystackPaymentManager;
  private paymentInProgress: boolean = false;
  private currentReference: string | null = null;
  private popup: PaystackPopup | null = null;

  private constructor() {}

  static getInstance(): PaystackPaymentManager {
    if (!PaystackPaymentManager.instance) {
      PaystackPaymentManager.instance = new PaystackPaymentManager();
    }
    return PaystackPaymentManager.instance;
  }

  getPopup(): PaystackPopup | null {
    return this.popup;
  }

  setPopup(popup: PaystackPopup): void {
    this.popup = popup;
    this.paymentInProgress = true;
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

  reset(): void {
    this.paymentInProgress = false;
    this.currentReference = null;
    this.popup = null;
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

  // Get validated email from the input field
  const emailInput = elements.paystackEmailInput;

  if (!emailInput) {
    console.error('[PAYSTACK] ❌ Email input element not found');
    showPaymentError('Email input not found. Please refresh the page.', elements.paymentErrors);
    return false;
  }

  const email = emailInput.value.trim();

  if (!email) {
    console.warn('[PAYSTACK] ⚠️ Email is empty');
    showPaymentError('A valid email address is required for Paystack payment.', elements.paymentErrors);
    emailInput.focus();
    return false;
  }

  const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
  if (!emailRegex.test(email)) {
    console.warn('[PAYSTACK] ⚠️ Email format invalid:', email);
    showPaymentError('Please enter a valid email address.', elements.paymentErrors);
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

    // *** THIS IS THE FIX ***
    // We check for the authorization_url provided by the backend.
    if (response.ok && data.success && data.authorization_url) {

      console.log('[PAYSTACK] ✅ Backend initialization successful. Redirecting...');
      showPaystackStatus('Redirecting to secure payment page...', 'success');

      // Save reference in storage in case user returns without paying
      if (data.reference) {
        manager.setCurrentReference(data.reference);
        storage.setItem('lastPaystackReference', data.reference);
      }

      // Redirect user to the Paystack hosted payment page.
      window.location.href = data.authorization_url;

      // We return a promise that never resolves, because the page is about to unload.
      return new Promise(() => {});

    } else {
      // Handle error from our backend
      const message = data.error_message || data.message || 'Failed to initialize Paystack payment.';
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

// Function to verify payment status with the backend
// <-- MODIFIED: Added retryCount parameter -->
export async function verifyPaystackPayment(
  reference: string,
  paymentSystem: PaymentSystem,
  retryCount: number = 0
): Promise<void> {
  // <-- MODIFIED: Added max retries -->
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
      stopProcessingAnimation(elements.processingModal);
      showPaystackStatus('Payment verified! Redirecting...', 'success');
      manager.reset();

      setTimeout(() => {
        window.location.href = config.urls.orderSuccess.replace(config.orderId, data.order_id);
      }, 1500);

    } else if (data.status === 'failed') {
      // Payment failed
      stopProcessingAnimation(elements.processingModal);
      setSubmitButtonState(false, elements.paymentSubmitButton);
      manager.reset();
      showPaymentError(data.message || 'Payment verification failed. Please try again.', elements.paymentErrors);

    } else if (data.status === 'pending' || data.status === 'processing') {

      // <-- MODIFIED: Added retry limit logic -->
      if (retryCount >= MAX_RETRIES) {
        // Give up
        console.warn('[PAYSTACK] Polling timeout. Recommending user to check history.');
        stopProcessingAnimation(elements.processingModal);
        setSubmitButtonState(false, elements.paymentSubmitButton);
        manager.reset();
        // Show a more helpful message
        showPaymentError(
          'Payment is still processing. We will update your order history once confirmed. Please contact support if this persists.',
          elements.paymentErrors
        );
      } else {
        // Still processing - poll again after 3 seconds
        console.log('[PAYSTACK] Payment still processing, polling again...');
        setTimeout(() => verifyPaystackPayment(reference, paymentSystem, retryCount + 1), 3000); // Pass incremented count
      }
      // <-- END MODIFICATION -->

    } else {
      // Unknown status
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
  storage.removeItem('lastPaystackReference');
  console.info('[PAYSTACK] Payment state reset');
}

// Check for existing payment on page load
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
      // <-- MODIFIED: Pass initial retry count -->
      verifyPaystackPayment(existingReference, paymentSystem, 0);
    }, 1000);
  }
}