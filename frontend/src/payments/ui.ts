import { PaymentMethod, PaymentStatusType, ProcessingStage } from '@/payments/types/payment.js';
import { getMethodDisplayName, isPaypalCurrencySupported } from './utils.js';

// Processing stages for different payment methods
const processingStages: Record<PaymentMethod, ProcessingStage[]> = {
  mpesa: [
    { title: 'Connecting to M-Pesa', text: 'Establishing secure connection with Safaricom...' },
    { title: 'Sending Payment Request', text: 'Your phone will receive a payment prompt shortly...' },
    { title: 'Awaiting Confirmation', text: 'Please check your phone and enter your M-Pesa PIN to complete the payment...' },
    { title: 'Verifying Payment', text: 'Confirming your payment with M-Pesa...' },
    { title: 'Finalizing Transaction', text: 'Processing payment confirmation and updating your order...' }
  ],
  paypal: [
    { title: 'Connecting to PayPal', text: 'Establishing secure connection...' },
    { title: 'Processing Payment', text: 'Completing your PayPal transaction...' },
    { title: 'Finalizing Order', text: 'Confirming payment and updating your order...' }
  ]
};

// Payment method UI updates
export function updatePaymentMethodUI(
  method: PaymentMethod,
  paymentTabs: NodeListOf<HTMLElement>,
  selectedMethodName: HTMLElement
): void {
  paymentTabs.forEach(tab => {
    tab.classList.toggle('active', tab.dataset.method === method);
  });
  selectedMethodName.textContent = getMethodDisplayName(method);
}

export function updateSubmitButton(
  method: PaymentMethod,
  submitText: HTMLElement,
  submitIcon: HTMLElement
): void {
  const buttonTexts: Record<PaymentMethod, { text: string; icon: string }> = {
    mpesa: { text: 'Pay with M-Pesa', icon: 'fas fa-mobile-alt' },
    paypal: { text: 'Pay with PayPal', icon: 'fab fa-paypal' }
  };

  const config = buttonTexts[method];
  submitText.textContent = config.text;
  submitIcon.className = config.icon;
}

// Currency tooltip management
export function showCurrencyTooltip(
  method: PaymentMethod,
  currency: string,
  currencyTooltip: HTMLElement,
  tooltipText: HTMLElement
): void {
  if (method === 'paypal' && !isPaypalCurrencySupported(currency)) {
    tooltipText.textContent = `Don't worry! PayPal doesn't support ${currency}, but we'll automatically convert your payment to USD at the current exchange rate.`;
    currencyTooltip.style.display = 'flex';
  } else {
    hideCurrencyTooltip(currencyTooltip);
  }
}

export function hideCurrencyTooltip(currencyTooltip: HTMLElement): void {
  currencyTooltip.style.display = 'none';
}

// Processing animation
export function startProcessingAnimation(
  method: PaymentMethod,
  processingModal: HTMLElement,
  modalTitle: HTMLElement,
  modalText: HTMLElement
): void {
  processingModal.classList.add('active');
  let processingStage = 0;

  function updateStage(): void {
    const stages = processingStages[method] || processingStages.mpesa;
    if (processingStage < stages.length) {
      const stage = stages[processingStage];
      modalTitle.textContent = stage.title;
      modalText.textContent = stage.text;
      processingStage++;

      if (processingStage < stages.length) {
        setTimeout(updateStage, 2000);
      }
    }
  }

  updateStage();
}

export function stopProcessingAnimation(processingModal: HTMLElement): void {
  processingModal.classList.remove('active');
}

// Status and error messages
export function showPaymentStatus(message: string, paymentStatus: HTMLElement): void {
  const span = paymentStatus.querySelector('span');
  if (span) span.textContent = message;
  paymentStatus.className = 'payment-status info';
  paymentStatus.style.display = 'flex';
}

export function showPaymentError(message: string, paymentErrors: HTMLElement): void {
  const span = paymentErrors.querySelector('span');
  if (span) span.textContent = message;
  paymentErrors.style.display = 'flex';
}

export function showPayPalStatus(message: string, type: PaymentStatusType): void {
  const paypalStatus = document.getElementById('paypal-status');
  if (!paypalStatus) return;

  const span = paypalStatus.querySelector('span');
  if (span) span.textContent = message;
  paypalStatus.className = `payment-status ${type}`;
  paypalStatus.style.display = 'flex';
}

export function showPayPalError(message: string): void {
  const paypalStatus = document.getElementById('paypal-status');
  if (!paypalStatus) return;

  const span = paypalStatus.querySelector('span');
  if (span) span.textContent = message;
  paypalStatus.className = 'payment-status error';
  paypalStatus.style.display = 'flex';
}

export function clearPayPalStatus(): void {
  const paypalStatus = document.getElementById('paypal-status');
  if (!paypalStatus) return;

  paypalStatus.style.display = 'none';
  const span = paypalStatus.querySelector('span');
  if (span) span.textContent = '';
}

// Input validation UI
export function showInputError(input: HTMLElement, errorElement: HTMLElement, message: string): void {
  input.classList.add('input-error');
  input.classList.remove('input-success');

  const existingSpan = errorElement.querySelector('span');
  if (existingSpan) {
    existingSpan.textContent = message;
  } else {
    errorElement.innerHTML = `<i class="fas fa-exclamation-circle"></i> ${message}`;
  }
  errorElement.classList.add('show');
}

export function clearInputError(input: HTMLElement, errorElement: HTMLElement): void {
  input.classList.remove('input-error');
  input.classList.add('input-success');
  errorElement.classList.remove('show');
}

// Button state management
export function setSubmitButtonState(loading: boolean, paymentSubmitButton: HTMLButtonElement): void {
  if (loading) {
    paymentSubmitButton.classList.add('loading');
    paymentSubmitButton.disabled = true;
  } else {
    paymentSubmitButton.classList.remove('loading');
    paymentSubmitButton.disabled = false;
  }
}