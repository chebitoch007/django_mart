// users_src/auth/register.ts
import '../utils/password-toggle';
import '../utils/password-validation';

interface RegisterFormElements {
    form: HTMLFormElement | null;
    password1: HTMLInputElement | null;
    password2: HTMLInputElement | null;
}

class RegisterForm {
    private elements: RegisterFormElements;

    constructor() {
        console.log('Initializing RegisterForm...');
        this.elements = {
            form: document.querySelector('form') as HTMLFormElement,
            password1: document.querySelector('[name="password1"]') as HTMLInputElement,
            password2: document.querySelector('[name="password2"]') as HTMLInputElement,
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
                if (this.elements.password1 && this.elements.password2) {
                    // Check if passwords match
                    if (this.elements.password1.value !== this.elements.password2.value) {
                        e.preventDefault();
                        this.showError('Passwords do not match. Please confirm your password.');
                        this.elements.password2.focus();
                        return;
                    }

                    // Check password strength using global PasswordValidator
                    if (window.PasswordValidator && !window.PasswordValidator.isPasswordStrong(this.elements.password1.value)) {
                        e.preventDefault();
                        this.showError('Please ensure your password meets all the strength requirements.');
                        this.elements.password1.focus();
                    }
                }
            });
        }
    }

    private showError(message: string): void {
        // Remove existing error message
        const existingError = document.getElementById('form-error-message');
        if (existingError) {
            existingError.remove();
        }

        // Create new error message
        const errorElement = document.createElement('div');
        errorElement.id = 'form-error-message';
        errorElement.className = 'rounded-xl p-4 error-alert mb-4';
        errorElement.innerHTML = `
            <div class="flex">
                <div class="flex-shrink-0">
                    <i class="fas fa-exclamation-circle text-red-500 text-lg"></i>
                </div>
                <div class="ml-3">
                    <h4 class="font-semibold text-red-800">Action Required</h4>
                    <p class="mt-1 text-sm text-red-700">${message}</p>
                </div>
            </div>
        `;

        if (this.elements.form) {
            this.elements.form.prepend(errorElement);
        }

        // Auto-remove after 8 seconds
        setTimeout(() => {
            if (errorElement.parentNode) {
                errorElement.remove();
            }
        }, 8000);
    }
}

// Initialize when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    new RegisterForm();
});