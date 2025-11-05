// users_src/password-reset/password_reset_confirm.ts
import '../utils/password-toggle';
import '../utils/password-validation';

class PasswordResetConfirmForm {
    private elements: {
        form: HTMLFormElement | null;
        newPassword1: HTMLInputElement | null;
        newPassword2: HTMLInputElement | null;
    };

    constructor() {
        this.elements = {
            form: document.querySelector('form') as HTMLFormElement,
            newPassword1: document.querySelector('[name="new_password1"]') as HTMLInputElement,
            newPassword2: document.querySelector('[name="new_password2"]') as HTMLInputElement,
        };

        this.initialize();
    }

    private initialize(): void {
        // Password utilities are auto-initialized from their modules
        this.enhanceFormValidation();
    }

    private enhanceFormValidation(): void {
        if (this.elements.form) {
            this.elements.form.addEventListener('submit', (e: Event) => {
                if (this.elements.newPassword1 && this.elements.newPassword2) {
                    // Check if passwords match
                    if (this.elements.newPassword1.value !== this.elements.newPassword2.value) {
                        e.preventDefault();
                        this.showError('New passwords do not match. Please confirm your new password.');
                        this.elements.newPassword2.focus();
                        return;
                    }

                    // Check password strength
                    if (window.PasswordValidator && !window.PasswordValidator.isPasswordStrong(this.elements.newPassword1.value)) {
                        e.preventDefault();
                        this.showError('Please ensure your password meets all the strength requirements.');
                        this.elements.newPassword1.focus();
                    }
                }
            });
        }
    }

    private showError(message: string): void {
        alert(message);
    }
}

// Initialize when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    new PasswordResetConfirmForm();
});