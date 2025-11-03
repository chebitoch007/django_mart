// ===================================================================
// UPDATED: utils.ts - Replace localStorage with safe storage
// ===================================================================


import { PaymentMethod } from '@/payments/types/payment.js';
import { storage } from './storage.js';

// Phone number validation
export function validatePhoneNumber(phoneNumber: string): string | false {
  if (!phoneNumber) return false;

  const cleanPhone = phoneNumber.trim().replace(/\s+/g, '');
  const phoneRegex = /^(?:254|\+254|0)?(7[0-9]{8})$/;
  const match = cleanPhone.match(phoneRegex);

  if (!match) return false;
  return `254${match[1]}`;
}

// Currency formatting
export function formatCurrency(amount: number, currency: string): string {
  const decimalPlaces = currency === 'UGX' || currency === 'TZS' ? 0 : 2;
  return amount.toLocaleString('en-US', {
    minimumFractionDigits: decimalPlaces,
    maximumFractionDigits: decimalPlaces
  });
}

// Form state management - NOW USING SAFE STORAGE
interface FormState {
  method?: PaymentMethod;
  currency?: string;
  phone?: string;
  terms?: boolean;
}

export function saveFormState(state: FormState): void {
  try {
    storage.setItem('paymentFormState', JSON.stringify(state));
  } catch (error) {
    console.warn('[Storage] Failed to save form state:', error);
  }
}

export function restoreFormState(): FormState {
  try {
    const saved = storage.getItem('paymentFormState');
    return saved ? JSON.parse(saved) : {};
  } catch (error) {
    console.warn('[Storage] Failed to restore form state:', error);
    return {};
  }
}

// Fetch with timeout
export async function fetchWithTimeout(
  url: string,
  options: RequestInit = {},
  timeoutMs: number = 30000
): Promise<Response> {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), timeoutMs);

  try {
    const response = await fetch(url, {
      ...options,
      signal: controller.signal
    });
    clearTimeout(timeout);
    return response;
  } catch (error) {
    clearTimeout(timeout);
    if (error.name === 'AbortError') {
      throw new Error('Request timed out. Please check your connection.');
    }
    throw error;
  }
}

// Payment method display names
export function getMethodDisplayName(method: PaymentMethod): string {
  const methodNames: Record<PaymentMethod, string> = {
    'mpesa': 'M-Pesa',
    'paypal': 'PayPal'
  };
  return methodNames[method] || method;
}

// Check if PayPal supports currency
export function isPaypalCurrencySupported(currency: string): boolean {
  const paypalSupportedCurrencies = ['USD', 'EUR', 'GBP', 'CAD', 'AUD', 'JPY'];
  return paypalSupportedCurrencies.includes(currency);
}