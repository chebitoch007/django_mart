"use strict";
function setupPasswordToggle() {
    const toggleButtons = document.querySelectorAll('.password-toggle');
    toggleButtons.forEach(button => {
        button.addEventListener('click', function () {
            const parent = this.parentElement;
            if (!parent)
                return;
            const input = parent.querySelector('input');
            if (!input)
                return;
            const type = input.getAttribute('type') === 'password' ? 'text' : 'password';
            input.setAttribute('type', type);
            this.innerHTML = type === 'password' ? '<i class="far fa-eye"></i>' : '<i class="far fa-eye-slash"></i>';
        });
    });
}
function setupPasswordStrengthMeter(passwordFieldId, strengthBars) {
    const passwordField = document.querySelector(passwordFieldId);
    if (!passwordField)
        return;
    passwordField.addEventListener('input', function () {
        const password = this.value;
        const lengthBar = document.getElementById(strengthBars.length);
        const numberBar = document.getElementById(strengthBars.number);
        const caseBar = document.getElementById(strengthBars.case);
        const specialBar = document.getElementById(strengthBars.special);
        const strengthText = document.getElementById(strengthBars.text);
        const bars = [lengthBar, numberBar, caseBar, specialBar];
        bars.forEach(bar => {
            if (bar)
                bar.className = 'h-1 rounded bg-gray-200';
        });
        let strength = 0;
        if (password.length >= 8) {
            if (lengthBar)
                lengthBar.classList.add('bg-green-500');
            strength++;
        }
        else if (password.length > 0 && lengthBar) {
            lengthBar.classList.add('bg-red-500');
        }
        if (/\d/.test(password)) {
            if (numberBar)
                numberBar.classList.add('bg-green-500');
            strength++;
        }
        else if (password.length > 0 && numberBar) {
            numberBar.classList.add('bg-red-500');
        }
        if (/[a-z]/.test(password) && /[A-Z]/.test(password)) {
            if (caseBar)
                caseBar.classList.add('bg-green-500');
            strength++;
        }
        else if (password.length > 0 && caseBar) {
            caseBar.classList.add('bg-red-500');
        }
        if (/[!@#$%^&*(),.?":{}|<>]/.test(password)) {
            if (specialBar)
                specialBar.classList.add('bg-green-500');
            strength++;
        }
        else if (password.length > 0 && specialBar) {
            specialBar.classList.add('bg-red-500');
        }
        if (strengthText) {
            const strengthTexts = [
                'Very weak - Add more characters and complexity',
                'Weak - Try adding numbers or symbols',
                'Medium - Add uppercase letters or symbols',
                'Strong - Good job!',
                'Very strong - Excellent password!'
            ];
            strengthText.textContent = strengthTexts[strength];
            strengthText.className = 'mt-2 text-xs ' + (strength < 2 ? 'text-red-600' :
                strength < 3 ? 'text-amber-600' :
                    strength < 4 ? 'text-yellow-600' : 'text-green-600');
        }
    });
}
function setupFormValidation(formId, validationRules) {
    const form = document.getElementById(formId);
    if (!form)
        return;
    form.addEventListener('submit', function (e) {
        let isValid = true;
        validationRules.forEach(rule => {
            const field = document.querySelector(rule.selector);
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
function validateEmail(email) {
    const re = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    return re.test(email);
}
document.addEventListener('DOMContentLoaded', function () {
    setupPasswordToggle();
});
//# sourceMappingURL=auth.js.map