//users_src/password-reset/password_reset_confirm.ts

class PasswordResetConfirmForm {
    private elements: {
        form: HTMLFormElement | null;
        newPassword1: HTMLInputElement | null;
        newPassword2: HTMLInputElement | null;
        strengthBars: {
            lengthBar: HTMLElement | null;
            numberBar: HTMLElement | null;
            caseBar: HTMLElement | null;
            specialBar: HTMLElement | null;
            strengthText: HTMLElement | null;
        };
    };

    constructor() {
        this.elements = {
            form: document.querySelector('form') as HTMLFormElement,
            newPassword1: document.querySelector('[name="new_password1"]') as HTMLInputElement,
            newPassword2: document.querySelector('[name="new_password2"]') as HTMLInputElement,
            strengthBars: {
                lengthBar: document.getElementById('length-strength'),
                numberBar: document.getElementById('number-strength'),
                caseBar: document.getElementById('case-strength'),
                specialBar: document.getElementById('special-strength'),
                strengthText: document.getElementById('password-strength-text')
            }
        };

        this.initialize();
    }

    private initialize(): void {
        PasswordToggle.initialize();
        this.initializePasswordStrengthMeter();
        this.enhanceFormValidation();
    }

    private initializePasswordStrengthMeter(): void {
        if (this.elements.newPassword1) {
            this.elements.newPassword1.addEventListener('input', () => {
                if (this.elements.newPassword1) {
                    this.updatePasswordStrength(this.elements.newPassword1.value);
                }
            });

            // Initialize with current value if any
            if (this.elements.newPassword1.value) {
                this.updatePasswordStrength(this.elements.newPassword1.value);
            }
        }
    }

    private updatePasswordStrength(password: string): void {
        const requirements = PasswordValidator.validatePassword(password);
        PasswordValidator.updateStrengthBars(password, this.elements.strengthBars);
        PasswordValidator.updateRequirementsList(requirements);
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
                    if (!PasswordValidator.isPasswordStrong(this.elements.newPassword1.value)) {
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