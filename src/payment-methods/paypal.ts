// paypal.ts
import { formatCurrency, isPaypalCurrencySupported } from '../utils/utils.js';
import {
  startProcessingAnimation,
  stopProcessingAnimation,
  showPayPalStatus,
  showPayPalError,
  clearPayPalStatus
} from '../ui/ui.js';
import { PaymentSystem } from '../payments.js';
import { PaymentResponse, PayPalButtons } from '../types/payment.js';

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

    // Handle currency conversion for unsupported currencies
    if (!isPaypalCurrencySupported(state.currentCurrency) && state.currentCurrency !== 'USD') {
      paypalCurrency = 'USD';
      const usdOption = Array.from(elements.currencySelector.options).find(
        (opt: HTMLOptionElement) => opt.value === 'USD'
      );
      if (usdOption) {
        const usdRate = parseFloat(usdOption.dataset.rate || '1');
        const baseAmount = parseFloat(config.cartTotalPrice);
        paypalAmount = baseAmount * usdRate;

        showPayPalStatus(
          `Your ${state.currentCurrency} ${formatCurrency(state.currentConvertedAmount, state.currentCurrency)} payment will be processed as USD ${formatCurrency(paypalAmount, 'USD')}.`,
          'info'
        );
      }
    }

    // ✅ Updated PayPal button configuration
    paypalButtons = window.paypal!.Buttons({
      onInit: function (data: any, actions: any) {
        actions.disable();
        const enableCheck = () => {
          if (elements.termsCheckbox && elements.termsCheckbox.checked) actions.enable();
          else actions.disable();
        };
        elements.termsCheckbox?.addEventListener('change', enableCheck);
      },

      onClick: function (data: any, actions: any) {
        if (!elements.termsCheckbox.checked) {
          showPayPalError('You must agree to the terms and conditions');
          return actions.reject();
        }
      },

      // ✅ New dynamic createOrder logic
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

  function handlePaymentError(error: any): void {
    stopProcessingAnimation(elements.processingModal);
    setSubmitButtonState(false, elements.paymentSubmitButton);

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

function setSubmitButtonState(loading: boolean, button: HTMLButtonElement): void {
  button.classList.toggle('loading', loading);
  button.disabled = loading;
}

function showPaymentError(message: string, container: HTMLElement): void {
  const span = container.querySelector('span');
  if (span) span.textContent = message;
  container.style.display = 'flex';
}
