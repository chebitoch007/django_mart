// PayPal SDK types
interface PayPalWindow extends Window {
  paypal?: {
    Buttons: {
      (options: PayPalButtonOptions): PayPalButtons;
      isEligible(): boolean;
    };
  };
}

interface PayPalButtonOptions {
  onInit: (data: any, actions: PayPalActions) => void;
  onClick: (data: any, actions: PayPalActions) => void;
  createOrder: (data: any, actions: PayPalActions) => Promise<string>;
  onApprove: (data: PayPalApproveData, actions: PayPalActions) => Promise<void>;
  onError: (err: any) => void;
  onCancel: (data: any) => void;
}

interface PayPalActions {
  disable(): void;
  enable(): void;
  reject(): void;
  order: {
    create(purchaseUnits: PurchaseUnit[]): Promise<string>;
    capture(): Promise<PayPalOrderDetails>;
  };
}

interface PayPalApproveData {
  orderID: string;
}

interface PayPalOrderDetails {
  payer: {
    payer_id: string;
  };
}

interface PurchaseUnit {
  amount: {
    value: string;
    currency_code: string;
  };
}

interface PayPalButtons {
  render(container: string): Promise<void>;
  close(): void;
  isEligible(): boolean;
}

// Payment System Types
interface PaymentConfig {
  urls: {
    initiatePayment: string;
    processPayment: string;
    mpesaStatus: string;
    orderSuccess: string;
    initializePaystack?: string; // Add this
    paystackStatus?: string; // Add this
  };
  cartTotalPrice: string;
  defaultCurrency: string;
  csrfToken: string;
  currencySymbols: Record<string, string>;
  orderId: string;
  paypalClientId: string;
  paystackPublicKey: string;
  currencyOptions: CurrencyOption[];
}

interface CurrencyOption {
  code: string;
  name: string;
  symbol: string;
  rate: number;
}


interface PaymentState {
  currentMethod: PaymentMethod;
  currentCurrency: string;
  currentRate: number;
  currentConvertedAmount: number;
  paypalInitialized: boolean;
  paypalProcessing: boolean;
  processingStage: number;
}

interface PaymentElements {
  paymentForm: HTMLFormElement;
  processingModal: HTMLElement;
  modalTitle: HTMLElement;
  modalText: HTMLElement;
  paymentStatus: HTMLElement;
  paystackStatus: HTMLElement;
  paymentErrors: HTMLElement;
  selectedMethodInput: HTMLInputElement;
  currencySelector: HTMLSelectElement;
  currencyTooltip: HTMLElement;
  tooltipText: HTMLElement;
  methodConfirmation: HTMLElement;
  selectedMethodName: HTMLElement;
  paymentSubmitButton: HTMLButtonElement;
  submitText: HTMLElement;
  submitIcon: HTMLElement;
  formCurrency: HTMLInputElement;
  formConversionRate: HTMLInputElement;
  formAmount: HTMLInputElement;
  mobileMoneySection: HTMLElement;
  paystackSection: HTMLElement;
  paypalSection: HTMLElement;
  paymentTabs: NodeListOf<HTMLElement>;
  phoneInput: HTMLInputElement;
  phoneError: HTMLElement;
  termsCheckbox: HTMLInputElement;
  summaryToggle: HTMLElement;
  summaryContent: HTMLElement;
  paystackEmailInput: HTMLInputElement; // ✅ ADDED
  paystackEmailError: HTMLElement; // ✅ ADDED
}

type PaymentMethod = 'mpesa' | 'paypal' | 'paystack';
type PaymentStatusType = 'info' | 'error' | 'success';

interface ProcessingStage {
  title: string;
  text: string;
}

interface MpesaResponse {
  success: boolean;
  checkout_request_id?: string;
  error?: string;
  message?: string;
  status?: string;
}

interface PaymentResponse {
  success: boolean;
  redirect_url?: string;
  error_message?: string;
  message?: string;
  status?: string;
}


declare global {
  interface Window {
    paymentSystem: any; // We'll fix this type later
    paymentConfig: PaymentConfig;
    paypal?: any;
  }
}

export type {
  PaymentConfig,
  PaymentState,
  PaymentElements,
  PaymentMethod,
  PaymentStatusType,
  ProcessingStage,
  MpesaResponse,
  PaymentResponse,
  CurrencyOption
};