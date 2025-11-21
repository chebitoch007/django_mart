// frontend/src/payments/paypal.ts

import { formatCurrency, isPaypalCurrencySupported } from './utils.js';
import {
  startProcessingAnimation,
  stopProcessingAnimation,
  showPayPalStatus,
  showPayPalError,
  clearPayPalStatus,
  setSubmitButtonState,
  showPaymentError
} from './ui.js';
import { PaymentSystem } from './payments.js';
import { PaymentResponse, PayPalButtons } from '@/payments/types/payment.js';
import { storage } from './storage.js';

let paypalButtons: PayPalButtons | null = null;
let isInitializing: boolean = false;

export function initializePayPal(paymentSystem: PaymentSystem): void {
  // Prevent multiple simultaneous initializations
  if (isInitializing) {
    console.log('[PayPal] Already initializing, skipping...');
    return;
  }

  const state = paymentSystem.getState();

  // If already initialized and currency hasn't changed, skip
  if (state.paypalInitialized && paypalButtons) {
    console.log('[PayPal] Already initialized, skipping...');
    return;
  }

  isInitializing = true;
  clearPayPalStatus();

  const elements = paymentSystem.getElements();
  const config = paymentSystem.getConfig();

  const paypalButtonContainer = document.getElementById('paypal-button-container');

  // Clean up existing buttons if any
  if (paypalButtons) {
    try {
      paypalButtons.close();
    } catch (e) {
      console.warn('[PayPal] Error closing existing buttons:', e);
    }
    paypalButtons = null;
  }

  if (paypalButtonContainer) {
    paypalButtonContainer.innerHTML = '';
  }

  try {
    if (typeof window.paypal === 'undefined') {
      console.error('[PayPal] SDK not loaded');
      const fallback = document.getElementById('paypal-fallback');
      if (fallback) fallback.style.display = 'block';
      isInitializing = false;
      return;
    }

    // Calculate PayPal amount and currency
    let paypalCurrency = state.currentCurrency;
    let paypalAmount = state.currentConvertedAmount;

    if (!isPaypalCurrencySupported(state.currentCurrency)) {
      paypalCurrency = 'USD';
      const usdOption = Array.from(elements.currencySelector.options).find(
        (opt: HTMLOptionElement) => opt.value === 'USD'
      );
      if (usdOption) {
        const usdRate = parseFloat(usdOption.dataset.rate || '1');
        const baseAmount = parseFloat(config.cartTotalPrice);
        paypalAmount = baseAmount * usdRate;
      }

      showPayPalStatus(
        `Converting to USD ${formatCurrency(paypalAmount, 'USD')} for PayPal`,
        'info'
      );
    }

    console.log('[PayPal] Initializing with:', { amount: paypalAmount, currency: paypalCurrency });

    paypalButtons = window.paypal!.Buttons({
      onInit: function (data: any, actions: any) {
        console.log('[PayPal] onInit called');

        const enableCheck = () => {
          // Use the live element reference
          const isChecked = elements.termsCheckbox?.checked || false;
          console.log('[PayPal] Terms checked:', isChecked);

          if (isChecked) {
            actions.enable();
          } else {
            actions.disable();
          }
        };

        // Remove existing listeners by cloning the checkbox
        if (elements.termsCheckbox) {
          const oldCheckbox = elements.termsCheckbox;

          // ✅ FIX: Capture the state BEFORE cloning
          const wasChecked = oldCheckbox.checked;

          const newCheckbox = oldCheckbox.cloneNode(true) as HTMLInputElement;

          // ✅ FIX: Explicitly re-apply the checked state to the new node
          newCheckbox.checked = wasChecked;

          oldCheckbox.parentNode?.replaceChild(newCheckbox, oldCheckbox);
          elements.termsCheckbox = newCheckbox; // Updating the reference in elements object

          // Add new listener
          elements.termsCheckbox.addEventListener('change', enableCheck);
          console.log('[PayPal] Terms checkbox listener attached');
        }

        // Initial check
        enableCheck();
      },

      onClick: function (data: any, actions: any) {
        console.log('[PayPal] Button clicked');
        if (!elements.termsCheckbox.checked) {
          showPayPalError('You must agree to the terms and conditions');
          return actions.reject();
        }
        clearPayPalStatus();
        return actions.resolve();
      },

      createOrder: function (data: any, actions: any) {
        // Get fresh state in case currency changed
        const currentState = paymentSystem.getState();
        let orderCurrency = currentState.currentCurrency;
        let orderAmount = currentState.currentConvertedAmount;

        // Handle unsupported currencies
        if (!isPaypalCurrencySupported(currentState.currentCurrency)) {
          orderCurrency = 'USD';
          const usdOption = Array.from(elements.currencySelector.options).find(
            (opt: HTMLOptionElement) => opt.value === 'USD'
          );
          if (usdOption) {
            const usdRate = parseFloat(usdOption.dataset.rate || '1');
            const baseAmount = parseFloat(config.cartTotalPrice);
            orderAmount = baseAmount * usdRate;
          }
        }

        console.log('[PayPal] Creating order:', {
          amount: orderAmount.toFixed(2),
          currency: orderCurrency,
          orderId: config.orderId
        });

        return actions.order.create({
          purchase_units: [
            {
              amount: {
                value: orderAmount.toFixed(2),
                currency_code: orderCurrency
              },
              description: `Order #${config.orderId}`,
              custom_id: config.orderId
            }
          ]
        });
      },

      onApprove: function (data: any, actions: any) {
        console.log('[PayPal] Payment approved, capturing...');
        paymentSystem.setState({ paypalProcessing: true });
        startProcessingAnimation('paypal', elements.processingModal, elements.modalTitle, elements.modalText);

        return actions.order.capture().then(function (details: any) {
          console.log('[PayPal] Payment captured:', details);

          const orderIdInput = document.getElementById('paypalOrderId') as HTMLInputElement;
          const payerIdInput = document.getElementById('paypalPayerId') as HTMLInputElement;

          if (orderIdInput) orderIdInput.value = data.orderID;
          if (payerIdInput) payerIdInput.value = details.payer.payer_id;

          // Get the actual currency and amount used
          const currentState = paymentSystem.getState();
          let finalCurrency = currentState.currentCurrency;
          let finalAmount = currentState.currentConvertedAmount;
          let conversionRate = 1;

          if (!isPaypalCurrencySupported(currentState.currentCurrency)) {
            finalCurrency = 'USD';
            const usdOption = Array.from(elements.currencySelector.options).find(
              (opt: HTMLOptionElement) => opt.value === 'USD'
            );
            if (usdOption) {
              conversionRate = parseFloat(usdOption.dataset.rate || '1');
              const baseAmount = parseFloat(config.cartTotalPrice);
              finalAmount = baseAmount * conversionRate;
            }
          }

          const formData = new FormData();
          formData.append('csrfmiddlewaretoken', config.csrfToken);
          formData.append('order_id', config.orderId);
          formData.append('payment_method', 'paypal');
          formData.append('paypal_order_id', data.orderID);
          formData.append('paypal_payer_id', details.payer.payer_id);
          formData.append('amount', finalAmount.toFixed(2));
          formData.append('currency', finalCurrency);
          formData.append('conversion_rate', conversionRate.toString());

          submitPaymentForm(formData, paymentSystem);
        }).catch(function (err: Error) {
          console.error('[PayPal] Capture error:', err);
          stopProcessingAnimation(elements.processingModal);
          showPaymentError('Failed to complete PayPal payment. Please try again.', elements.paymentErrors);
          paymentSystem.setState({ paypalProcessing: false });
        });
      },

      onError: function (err: any) {
        console.error('[PayPal] Error:', err);
        showPayPalError('PayPal payment failed. Please try another method.');
        paymentSystem.setState({ paypalProcessing: false });
        isInitializing = false;
      },

      onCancel: function (data: any) {
        console.log('[PayPal] Payment canceled by user');
        paymentSystem.setState({ paypalProcessing: false });
        showPayPalStatus('Payment canceled', 'info');
      }
    });

    // Render buttons
    if (paypalButtons && paypalButtons.isEligible()) {
      paypalButtons.render('#paypal-button-container').then(() => {
        console.log('[PayPal] Buttons rendered successfully');
        paymentSystem.setState({ paypalInitialized: true });
        const fallback = document.getElementById('paypal-fallback');
        if (fallback) fallback.style.display = 'none';
        isInitializing = false;
      }).catch((err: Error) => {
        console.error('[PayPal] Error rendering buttons:', err);
        const fallback = document.getElementById('paypal-fallback');
        if (fallback) fallback.style.display = 'block';
        paymentSystem.setState({ paypalInitialized: false });
        isInitializing = false;
      });
    } else {
      console.warn('[PayPal] Buttons not eligible');
      const fallback = document.getElementById('paypal-fallback');
      if (fallback) fallback.style.display = 'block';
      isInitializing = false;
    }
  } catch (error) {
    console.error('[PayPal] Initialization error:', error);
    const fallback = document.getElementById('paypal-fallback');
    if (fallback) fallback.style.display = 'block';
    paymentSystem.setState({ paypalInitialized: false });
    isInitializing = false;
  }
}

export function cleanupPayPal(): void {
  console.log('[PayPal] Cleaning up...');

  if (paypalButtons) {
    try {
      paypalButtons.close();
    } catch (e) {
      console.warn('[PayPal] Error closing buttons:', e);
    }
    paypalButtons = null;
  }

  const container = document.getElementById('paypal-button-container');
  if (container) {
    container.innerHTML = '';
  }

  isInitializing = false;
  console.log('[PayPal] Cleanup complete');
}

function submitPaymentForm(formData: FormData, paymentSystem: PaymentSystem): void {
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

  function handlePaymentResponse(response: Response): Promise<void> {
    if (!response.ok) return Promise.reject(response);

    return response.json().then((data: PaymentResponse) => {
      if (data.success || data.status === 'success') {
        // Clear storage
        storage.removeItem('paymentFormState');
        storage.removeItem('lastCheckoutRequestId');
        storage.removeItem('lastPaystackReference');

        elements.modalTitle.textContent = 'Payment Successful!';
        elements.modalText.textContent = 'Redirecting you to your order confirmation...';

        paymentSystem.setState({ paypalProcessing: false });

        setTimeout(() => {
          stopProcessingAnimation(elements.processingModal);
          window.location.href = data.redirect_url || config.urls.orderSuccess;
        }, 1500);
      } else {
        stopProcessingAnimation(elements.processingModal);
        showPaymentError(data.error_message || data.message || 'Payment failed', elements.paymentErrors);
        setSubmitButtonState(false, elements.paymentSubmitButton);
        paymentSystem.setState({ paypalProcessing: false });
      }
    });
  }

  function handlePaymentError(error: any): void {
    console.error('[PayPal] Payment finalization error:', error);
    stopProcessingAnimation(elements.processingModal);
    setSubmitButtonState(false, elements.paymentSubmitButton);
    paymentSystem.setState({ paypalProcessing: false });

    if (error.json) {
      error.json().then((errorData: PaymentResponse) => {
        showPaymentError(errorData.error_message || errorData.message || 'Unexpected error occurred', elements.paymentErrors);
      }).catch(() => {
        showPaymentError('Network error. Please check your connection.', elements.paymentErrors);
      });
    } else {
      showPaymentError('Network error. Please check your connection.', elements.paymentErrors);
    }
  }
}

export function resetPayPalPaymentState(): void {
  try {
    cleanupPayPal();

    // Hide fallback message if visible
    const fallback = document.getElementById('paypal-fallback');
    if (fallback) fallback.style.display = 'none';

    // Clear status or errors
    clearPayPalStatus();

    console.info('[PayPal] Payment state reset successfully');
  } catch (error) {
    console.error('[PayPal] Error resetting payment state:', error);
  }
}