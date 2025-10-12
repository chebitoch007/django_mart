// password_change.ts
interface PasswordStrengthBars {
    lengthBar: HTMLElement | null;
    numberBar: HTMLElement | null;
    caseBar: HTMLElement | null;
    specialBar: HTMLElement | null;
    strengthText: HTMLElement | null;
}

class PasswordChangeForm {
    private strengthBars: PasswordStrengthBars;

    constructor() {
        this.strengthBars = {
            lengthBar: document.getElementById('length-strength'),
            numberBar: document.getElementById('number-strength'),
            caseBar: document.getElementById('case-strength'),
            specialBar: document.getElementById('special-strength'),
            strengthText: document.getElementById('password-strength-text')
        };

        this.initialize();
    }

    private initialize(): void {
        this.initializePasswordToggle();
        this.initializePasswordStrengthMeter();
        this.enhanceFormValidation();
    }

    private initializePasswordToggle(): void {
        const toggleButtons = document.querySelectorAll('.password-toggle');
        toggleButtons.forEach(button => {
            button.addEventListener('click', (e: Event) => {
                const target = e.currentTarget as HTMLElement;
                const parent = target.parentElement;
                if (!parent) return;

                const input = parent.querySelector('input') as HTMLInputElement;
                if (!input) return;

                const type = input.getAttribute('type') === 'password' ? 'text' : 'password';
                input.setAttribute('type', type);

                const icon = target.querySelector('i');
                if (icon) {
                    icon.className = type === 'password' ? 'far fa-eye' : 'far fa-eye-slash';
                }
            });
        });
    }

    private initializePasswordStrengthMeter(): void {
        const newPassword = document.querySelector('[name="new_password1"]') as HTMLInputElement;
        if (newPassword) {
            newPassword.addEventListener('input', () => {
                this.updatePasswordStrength(newPassword.value);
            });

            // Initialize with current value if any
            if (newPassword.value) {
                this.updatePasswordStrength(newPassword.value);
            }
        }
    }

    private updatePasswordStrength(password: string): void {
        if (!this.strengthBars.lengthBar || !this.strengthBars.numberBar ||
            !this.strengthBars.caseBar || !this.strengthBars.specialBar ||
            !this.strengthBars.strengthText) return;

        const allBars = [this.strengthBars.lengthBar, this.strengthBars.numberBar,
                        this.strengthBars.caseBar, this.strengthBars.specialBar];

        // Reset all bars
        allBars.forEach(bar => {
            bar.className = 'h-1 rounded bg-gray-200 flex-1';
        });

        let strength = 0;
        const requirements = {
            length: password.length >= 8,
            number: /\d/.test(password),
            lowercase: /[a-z]/.test(password),
            uppercase: /[A-Z]/.test(password),
            special: /[!@#$%^&*(),.?":{}|<>]/.test(password)
        };

        // Update bars based on requirements
        if (requirements.length) {
            this.strengthBars.lengthBar.classList.add('bg-green-500');
            strength++;
        } else if (password.length > 0) {
            this.strengthBars.lengthBar.classList.add('bg-red-500');
        }

        if (requirements.number) {
            this.strengthBars.numberBar.classList.add('bg-green-500');
            strength++;
        } else if (password.length > 0) {
            this.strengthBars.numberBar.classList.add('bg-red-500');
        }

        if (requirements.lowercase && requirements.uppercase) {
            this.strengthBars.caseBar.classList.add('bg-green-500');
            strength++;
        } else if (password.length > 0) {
            this.strengthBars.caseBar.classList.add('bg-red-500');
        }

        if (requirements.special) {
            this.strengthBars.specialBar.classList.add('bg-green-500');
            strength++;
        } else if (password.length > 0) {
            this.strengthBars.specialBar.classList.add('bg-red-500');
        }

        // Update requirements list
        this.updateRequirementsList(requirements);

        // Update strength text
        const strengthTexts: string[] = [
            'Very weak - Add more characters and complexity',
            'Weak - Try adding numbers or symbols',
            'Medium - Add uppercase letters or symbols',
            'Strong - Good job!',
            'Very strong - Excellent password!'
        ];

        this.strengthBars.strengthText.textContent = strengthTexts[strength] || 'Password must be at least 8 characters long';

        // Update text color based on strength
        this.strengthBars.strengthText.className = 'mt-2 text-xs ' + (
            strength < 2 ? 'text-red-600' :
            strength < 3 ? 'text-amber-600' :
            strength < 4 ? 'text-yellow-600' : 'text-green-600'
        );
    }

    private updateRequirementsList(requirements: any): void {
        const requirementElements = document.querySelectorAll('.requirement');

        requirementElements.forEach(element => {
            const requirementType = element.getAttribute('data-requirement');
            const icon = element.querySelector('i');

            if (icon && requirementType && requirements[requirementType]) {
                icon.className = 'fas fa-check text-green-500 mr-2 text-xs';
                element.classList.add('text-green-600');
                element.classList.remove('text-gray-600');
            } else if (icon) {
                icon.className = 'fas fa-circle text-gray-300 mr-2 text-xs';
                element.classList.remove('text-green-600');
                element.classList.add('text-gray-600');
            }
        });
    }

    private enhanceFormValidation(): void {
        const form = document.querySelector('form');
        if (form) {
            form.addEventListener('submit', (e: Event) => {
                const newPassword1 = document.querySelector('[name="new_password1"]') as HTMLInputElement;
                const newPassword2 = document.querySelector('[name="new_password2"]') as HTMLInputElement;

                if (newPassword1 && newPassword2 && newPassword1.value !== newPassword2.value) {
                    e.preventDefault();
                    this.showError('New passwords do not match. Please confirm your new password.');
                    newPassword2.focus();
                    return;
                }

                // Check password strength before submission
                if (newPassword1 && !this.isPasswordStrong(newPassword1.value)) {
                    e.preventDefault();
                    this.showError('Please ensure your password meets all the strength requirements.');
                    newPassword1.focus();
                }
            });
        }
    }

    private isPasswordStrong(password: string): boolean {
        const requirements = {
            length: password.length >= 8,
            number: /\d/.test(password),
            lowercase: /[a-z]/.test(password),
            uppercase: /[A-Z]/.test(password),
            special: /[!@#$%^&*(),.?":{}|<>]/.test(password)
        };

    // Fix Object.values issue
        return requirements.length &&
            requirements.number &&
            requirements.lowercase &&
            requirements.uppercase &&
            requirements.special;
    }

    private showError(message: string): void {
        // You can implement a more sophisticated error display here
        alert(message);
    }
}

// Initialize when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    new PasswordChangeForm();
});