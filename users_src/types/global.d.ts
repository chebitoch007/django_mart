// users_src/types/global.d.ts
// Global type declarations for the users module

// Make PasswordValidator available globally
declare namespace PasswordValidator {
    function validatePassword(password: string): PasswordRequirements;
    function isPasswordStrong(password: string): boolean;
    function getStrengthText(strength: number): string;
    function updateStrengthBars(password: string, bars: StrengthBars): void;
    function updateRequirementsList(requirements: PasswordRequirements): void;
}

// Make PasswordToggle available globally
declare namespace PasswordToggle {
    function initialize(): void;
}

// Password requirements interface
interface PasswordRequirements {
    length: boolean;
    number: boolean;
    lowercase: boolean;
    uppercase: boolean;
    special: boolean;
}

// Strength bars interface
interface StrengthBars {
    lengthBar: HTMLElement | null;
    numberBar: HTMLElement | null;
    caseBar: HTMLElement | null;
    specialBar: HTMLElement | null;
    strengthText: HTMLElement | null;
}

// Bootstrap Modal types
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

// Extend Window interface
declare global {
    interface Window {
        bootstrap: Bootstrap;
    }
}

export {};