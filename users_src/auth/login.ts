class LoginForm {
    private form: HTMLFormElement | null;

    constructor() {
        this.form = document.querySelector('form') as HTMLFormElement;
        this.initialize();
    }

    private initialize(): void {
        PasswordToggle.initialize();
        this.enhanceFormValidation();
    }

    private enhanceFormValidation(): void {
        if (this.form) {
            this.form.addEventListener('submit', (e: Event) => {
                let isValid = true;

                // Email validation
                const emailField = document.getElementById('username') as HTMLInputElement;
                const emailError = document.getElementById('username-error');
                if (!emailField.value.trim()) {
                    if (emailError) emailError.classList.remove('hidden');
                    emailField.classList.add('border-red-500', 'ring-1', 'ring-red-500');
                    isValid = false;
                } else {
                    if (emailError) emailError.classList.add('hidden');
                    emailField.classList.remove('border-red-500', 'ring-1', 'ring-red-500');
                }

                // Password validation
                const passwordField = document.getElementById('password') as HTMLInputElement;
                const passwordError = document.getElementById('password-error');
                if (!passwordField.value.trim()) {
                    if (passwordError) passwordError.classList.remove('hidden');
                    passwordField.classList.add('border-red-500', 'ring-1', 'ring-red-500');
                    isValid = false;
                } else {
                    if (passwordError) passwordError.classList.add('hidden');
                    passwordField.classList.remove('border-red-500', 'ring-1', 'ring-red-500');
                }

                if (!isValid) {
                    e.preventDefault();
                }
            });
        }
    }
}

// Initialize when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    new LoginForm();
});