// frontend/src/payments/utils.ts - FULLY FIXED VERSION

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

// Email validation
export function validateEmail(email: string): boolean {
  if (!email) return false;
  const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
  return emailRegex.test(email.trim());
}

// Currency formatting
export function formatCurrency(amount: number, currency: string): string {
  const decimalPlaces = currency === 'UGX' || currency === 'TZS' ? 0 : 2;
  return amount.toLocaleString('en-US', {
    minimumFractionDigits: decimalPlaces,
    maximumFractionDigits: decimalPlaces
  });
}

// Form state management
interface FormState {
  method?: PaymentMethod;
  currency?: string;
  phone?: string;
  email?: string;
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
  } catch (error: any) {
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
    'paypal': 'PayPal',
    'paystack': 'Paystack'
  };
  return methodNames[method] || method;
}

// Check if PayPal supports currency
export function isPaypalCurrencySupported(currency: string): boolean {
  const paypalSupportedCurrencies = [
    'USD', 'EUR', 'GBP', 'CAD', 'AUD', 'JPY', 'CHF',
    'HKD', 'SGD', 'SEK', 'DKK', 'PLN', 'NOK', 'HUF',
    'CZK', 'ILS', 'MXN', 'NZD', 'BRL', 'PHP', 'TWD',
    'THB', 'TRY', 'RUB', 'CNY', 'INR', 'MYR'
  ];
  return paypalSupportedCurrencies.includes(currency.toUpperCase());
}

// Check if Paystack supports currency
export function isPaystackCurrencySupported(currency: string): boolean {
  const paystackSupportedCurrencies = ['NGN', 'GHS', 'ZAR', 'USD', 'KES'];
  return paystackSupportedCurrencies.includes(currency.toUpperCase());
}

// Amount validation
export function validateAmount(amount: number): boolean {
  return amount > 0 && amount < 10000000; // Reasonable upper limit
}

// Input sanitization
export function sanitizeInput(input: string): string {
  return input.trim().replace(/[<>]/g, '');
}

// Debounce function for input validation
export function debounce<T extends (...args: any[]) => any>(
  func: T,
  wait: number
): (...args: Parameters<T>) => void {
  let timeout: ReturnType<typeof setTimeout> | null = null;

  return function executedFunction(...args: Parameters<T>) {
    const later = () => {
      timeout = null;
      func(...args);
    };

    if (timeout !== null) {
      clearTimeout(timeout);
    }
    timeout = setTimeout(later, wait);
  };
}