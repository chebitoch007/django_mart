interface StrengthBars {
    length: string;
    number: string;
    case: string;
    special: string;
    text: string;
}

interface ValidationRule {
    selector: string;
    validator: (value: string) => boolean;
}

function setupPasswordToggle(): void {
    const toggleButtons = document.querySelectorAll('.password-toggle');
    toggleButtons.forEach(button => {
        button.addEventListener('click', function(this: HTMLElement): void {
            const parent = this.parentElement;
            if (!parent) return;

            const input = parent.querySelector('input') as HTMLInputElement;
            if (!input) return;

            const type = input.getAttribute('type') === 'password' ? 'text' : 'password';
            input.setAttribute('type', type);
            this.innerHTML = type === 'password' ? '<i class="far fa-eye"></i>' : '<i class="far fa-eye-slash"></i>';
        });
    });
}

function setupPasswordStrengthMeter(passwordFieldId: string, strengthBars: StrengthBars): void {
    const passwordField = document.querySelector(passwordFieldId) as HTMLInputElement;
    if (!passwordField) return;

    passwordField.addEventListener('input', function(): void {
        const password = this.value;
        const lengthBar = document.getElementById(strengthBars.length);
        const numberBar = document.getElementById(strengthBars.number);
        const caseBar = document.getElementById(strengthBars.case);
        const specialBar = document.getElementById(strengthBars.special);
        const strengthText = document.getElementById(strengthBars.text);

        const bars = [lengthBar, numberBar, caseBar, specialBar];
        bars.forEach(bar => {
            if (bar) bar.className = 'h-1 rounded bg-gray-200';
        });

        let strength = 0;

        if (password.length >= 8) {
            if (lengthBar) lengthBar.classList.add('bg-green-500');
            strength++;
        } else if (password.length > 0 && lengthBar) {
            lengthBar.classList.add('bg-red-500');
        }

        if (/\d/.test(password)) {
            if (numberBar) numberBar.classList.add('bg-green-500');
            strength++;
        } else if (password.length > 0 && numberBar) {
            numberBar.classList.add('bg-red-500');
        }

        if (/[a-z]/.test(password) && /[A-Z]/.test(password)) {
            if (caseBar) caseBar.classList.add('bg-green-500');
            strength++;
        } else if (password.length > 0 && caseBar) {
            caseBar.classList.add('bg-red-500');
        }

        if (/[!@#$%^&*(),.?":{}|<>]/.test(password)) {
            if (specialBar) specialBar.classList.add('bg-green-500');
            strength++;
        } else if (password.length > 0 && specialBar) {
            specialBar.classList.add('bg-red-500');
        }

        if (strengthText) {
            const strengthTexts: string[] = [
                'Very weak - Add more characters and complexity',
                'Weak - Try adding numbers or symbols',
                'Medium - Add uppercase letters or symbols',
                'Strong - Good job!',
                'Very strong - Excellent password!'
            ];
            strengthText.textContent = strengthTexts[strength];
            strengthText.className = 'mt-2 text-xs ' + (
                strength < 2 ? 'text-red-600' :
                strength < 3 ? 'text-amber-600' :
                strength < 4 ? 'text-yellow-600' : 'text-green-600'
            );
        }
    });
}

function setupFormValidation(formId: string, validationRules: ValidationRule[]): void {
    const form = document.getElementById(formId) as HTMLFormElement;
    if (!form) return;

    form.addEventListener('submit', function(e: Event): void {
        let isValid = true;

        validationRules.forEach(rule => {
            const field = document.querySelector(rule.selector) as HTMLInputElement;
            if (field && !rule.validator(field.value)) {
                isValid = false;
                field.classList.add('border-red-500');
            }
        });

        if (!isValid) {
            e.preventDefault();
        }
    });
}

function validateEmail(email: string): boolean {
    const re = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    return re.test(email);
}

document.addEventListener('DOMContentLoaded', function(): void {
    setupPasswordToggle();
});