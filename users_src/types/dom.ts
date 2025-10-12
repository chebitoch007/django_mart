// Extended DOM types
interface BootstrapModal {
    show(): void;
    hide(): void;
    dispose(): void;
}

interface Bootstrap {
    Modal: {
        new (element: HTMLElement): BootstrapModal;
    };
}

declare global {
    interface Window {
        bootstrap: Bootstrap;
    }
}

// Form field interfaces
interface FormField extends HTMLInputElement {
    value: string;
}

interface PasswordRequirements {
    length: boolean;
    number: boolean;
    lowercase: boolean;
    uppercase: boolean;
    special: boolean;
}

// Browser timeout type (alternative to NodeJS.Timeout)
type BrowserTimeout = number;

export type { BootstrapModal, Bootstrap, FormField, PasswordRequirements, BrowserTimeout };
