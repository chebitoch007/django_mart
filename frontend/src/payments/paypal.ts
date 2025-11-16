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

// ❌ REMOVED unused variables
// let paymentInProgress = false;
// let finalizationInProgress = false;

let paypalButtons: PayPalButtons | null = null;

export function initializePayPal(paymentSystem: PaymentSystem): void {
  clearPayPalStatus();

  const state = paymentSystem.getState();
  const elements = paymentSystem.getElements();
  const config = paymentSystem.getConfig();

  const paypalButtonContainer = document.getElementById('paypal-button-container');

  // Clean up existing buttons if any
  if (paypalButtons) {
    try {
      paypalButtons.close();
    } catch (e) {
      console.warn('Error closing PayPal buttons:', e);
    }
    if (paypalButtonContainer) paypalButtonContainer.innerHTML = '';
  }

  if (state.paypalInitialized) return;

  try {
    if (typeof window.paypal === 'undefined') {
      console.error('PayPal SDK not loaded');
      const fallback = document.getElementById('paypal-fallback');
      if (fallback) fallback.style.display = 'block';
      return;
    }

    let paypalCurrency = state.currentCurrency;
    let paypalAmount = state.currentConvertedAmount;

    if (!isPaypalCurrencySupported(state.currentCurrency) && state.currentCurrency !== 'USD') {
      showPayPalStatus(
        `Your ${state.currentCurrency} ${formatCurrency(state.currentConvertedAmount, state.currentCurrency)} payment will be processed as USD ...`,
        'info'
      );
    }

    paypalButtons = window.paypal!.Buttons({
      onInit: function (data: any, actions: any) {
        console.log('[PayPal] onInit called, terms checkbox:', elements.termsCheckbox?.checked);

        // Check initial state
        const enableCheck = () => {
          const isChecked = elements.termsCheckbox?.checked || false;
          console.log('[PayPal] Enable check - Terms checked:', isChecked);

          if (isChecked) {
            actions.enable();
            console.log('[PayPal] Buttons ENABLED');
          } else {
            actions.disable();
            console.log('[PayPal] Buttons DISABLED');
          }
        };

        // Remove any existing listener to prevent duplicates
        if (elements.termsCheckbox) {
          // Clone the checkbox to remove all event listeners
          const oldCheckbox = elements.termsCheckbox;
          const newCheckbox = oldCheckbox.cloneNode(true) as HTMLInputElement;
          oldCheckbox.parentNode?.replaceChild(newCheckbox, oldCheckbox);

          // Update reference
          elements.termsCheckbox = newCheckbox;

          // Add new listener
          elements.termsCheckbox.addEventListener('change', enableCheck);
          console.log('[PayPal] Terms checkbox listener attached');
        }

        // Initial check
        enableCheck();
      },


      onClick: function (data: any, actions: any) {
        if (!elements.termsCheckbox.checked) {
          showPayPalError('You must agree to the terms and conditions');
          return actions.reject();
        }
      },

      // New dynamic createOrder logic
      createOrder: function (data: any, actions: any) {
        const state = paymentSystem.getState();
        const config = paymentSystem.getConfig();

        let paypalCurrency = state.currentCurrency;
        let paypalAmount = state.currentConvertedAmount;

        // Handle unsupported currencies again (USD fallback)
        if (!isPaypalCurrencySupported(state.currentCurrency) && state.currentCurrency !== 'USD') {
          paypalCurrency = 'USD';
          const usdOption = Array.from(elements.currencySelector.options).find(
            (opt: HTMLOptionElement) => opt.value === 'USD'
          );
          if (usdOption) {
            const usdRate = parseFloat(usdOption.dataset.rate || '1');
            const baseAmount = parseFloat(config.cartTotalPrice);
            paypalAmount = baseAmount * usdRate;
          }
        }

        console.log('Creating PayPal order:', {
          amount: paypalAmount,
          currency: paypalCurrency,
          orderId: config.orderId
        });

        return actions.order.create({
          purchase_units: [
            {
              amount: {
                value: paypalAmount.toFixed(2),
                currency_code: paypalCurrency
              },
              description: `Order #${config.orderId}`,
              custom_id: config.orderId
            }
          ]
        });
      },

      onApprove: function (data: any, actions: any) {
        paymentSystem.setState({ paypalProcessing: true });
        startProcessingAnimation('paypal', elements.processingModal, elements.modalTitle, elements.modalText);

        return actions.order.capture().then(function (details: any) {
          const orderIdInput = document.getElementById('paypalOrderId') as HTMLInputElement;
          const payerIdInput = document.getElementById('paypalPayerId') as HTMLInputElement;

          if (orderIdInput) orderIdInput.value = data.orderID;
          if (payerIdInput) payerIdInput.value = details.payer.payer_id;

          const formData = new FormData();
          formData.append('csrfmiddlewaretoken', config.csrfToken);
          formData.append('order_id', config.orderId);
          formData.append('payment_method', 'paypal');
          formData.append('paypal_order_id', data.orderID);
          formData.append('paypal_payer_id', details.payer.payer_id);
          formData.append('amount', paypalAmount.toFixed(2));
          formData.append('currency', paypalCurrency);

          // Include conversion rate if applicable
          if (!isPaypalCurrencySupported(state.currentCurrency) && state.currentCurrency !== 'USD') {
            const usdOption = Array.from(elements.currencySelector.options).find(
              (opt: HTMLOptionElement) => opt.value === 'USD'
            );
            formData.append('conversion_rate', parseFloat(usdOption?.dataset.rate || '1').toString());
          } else {
            formData.append('conversion_rate', '1');
          }

          submitPaymentForm(formData, paymentSystem);
        }).catch(function (err: Error) {
          console.error('PayPal capture error:', err);
          stopProcessingAnimation(elements.processingModal);
          showPaymentError('Failed to complete PayPal payment. Please try again.', elements.paymentErrors);
          paymentSystem.setState({ paypalProcessing: false });
        });
      },

      onError: function (err: any) {
        console.error('PayPal error:', err);
        showPayPalError('PayPal payment failed. Please try another method.');
        paymentSystem.setState({ paypalProcessing: false });
      },

      onCancel: function (data: any) {
        paymentSystem.setState({ paypalProcessing: false });
        showPayPalStatus('Payment canceled', 'info');
      }
    });

    // Render buttons
    if (paypalButtons && paypalButtons.isEligible()) {
      paypalButtons.render('#paypal-button-container').then(() => {
        console.log('PayPal buttons rendered successfully');
        paymentSystem.setState({ paypalInitialized: true });
        const fallback = document.getElementById('paypal-fallback');
        if (fallback) fallback.style.display = 'none';
      }).catch((err: Error) => {
        console.error('Error rendering PayPal buttons', err);
        const fallback = document.getElementById('paypal-fallback');
        if (fallback) fallback.style.display = 'block';
      });
    } else {
      console.log('PayPal buttons not eligible');
      const fallback = document.getElementById('paypal-fallback');
      if (fallback) fallback.style.display = 'block';
    }
  } catch (error) {
    console.error('PayPal initialization error:', error);
    const fallback = document.getElementById('paypal-fallback');
    if (fallback) fallback.style.display = 'block';
  }
}

export function cleanupPayPal(): void {
  if (paypalButtons) {
    try {
      paypalButtons.close();
    } catch (e) {
      console.log('Error closing PayPal buttons:', e);
    }
    const container = document.getElementById('paypal-button-container');
    if (container) container.innerHTML = '';
    paypalButtons = null;
  }
}

// --- Helper functions ---
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
      if (data.success) {
        // Clear safe storage
        storage.removeItem('paymentFormState');
        storage.removeItem('lastCheckoutRequestId');

        elements.modalTitle.textContent = 'Payment Successful!';
        elements.modalText.textContent = 'Redirecting you to your order confirmation...';

        // Reset state before redirect
        paymentSystem.setState({ paypalProcessing: false });

        setTimeout(() => {
          stopProcessingAnimation(elements.processingModal);
          window.location.href = data.redirect_url || config.urls.orderSuccess;
        }, 2000);
      } else {
        stopProcessingAnimation(elements.processingModal);
        showPaymentError(data.error_message || 'Payment failed', elements.paymentErrors);
        setSubmitButtonState(false, elements.paymentSubmitButton);
        paymentSystem.setState({ paypalProcessing: false }); // Reset state on failure
      }
    });
  }

  function handlePaymentError(error: any): void {
    stopProcessingAnimation(elements.processingModal);
    setSubmitButtonState(false, elements.paymentSubmitButton);
    paymentSystem.setState({ paypalProcessing: false }); // Reset state on error

    if (error.json) {
      error.json().then((errorData: PaymentResponse) => {
        showPaymentError(errorData.error_message || 'Unexpected error occurred', elements.paymentErrors);
      }).catch(() => {
        showPaymentError('Network error. Please check your connection.', elements.paymentErrors);
      });
    } else {
      showPaymentError('Network error. Please check your connection.', elements.paymentErrors);
    }
  }
}


// --- Reset PayPal State ---
export function resetPayPalPaymentState(): void {
  try {
    // Clear the PayPal button container
    const paypalContainer = document.getElementById('paypal-button-container');
    if (paypalContainer) paypalContainer.innerHTML = '';

    // Hide fallback message if visible
    const fallback = document.getElementById('paypal-fallback');
    if (fallback) fallback.style.display = 'none';

    // Clear status or errors
    clearPayPalStatus();

    // Reset internal PayPal state
    paypalButtons = null;
    console.info('[PayPal] Payment state reset successfully.');
  } catch (error) {
    console.error('[PayPal] Error resetting payment state:', error);
  }
}