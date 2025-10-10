// Authentication related types
interface UserSession {
    timeout: number;
    logoutUrl: string;
    keepaliveUrl: string | null;
    csrfToken: string;
}

interface PasswordStrength {
    score: number;
    text: string;
    requirements: {
        length: boolean;
        number: boolean;
        lowercase: boolean;
        uppercase: boolean;
        special: boolean;
    };
}

interface ValidationResult {
    isValid: boolean;
    message?: string;
}

export type { UserSession, PasswordStrength, ValidationResult };