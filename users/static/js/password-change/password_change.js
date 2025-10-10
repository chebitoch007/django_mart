"use strict";
document.addEventListener('DOMContentLoaded', function () {
    initializePasswordToggle();
    initializePasswordStrengthMeter();
});
function initializePasswordToggle() {
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
function initializePasswordStrengthMeter() {
    const newPassword = document.querySelector('[name="new_password1"]');
    if (newPassword) {
        newPassword.addEventListener('input', function () {
            updatePasswordStrength(this.value);
        });
        if (newPassword.value) {
            updatePasswordStrength(newPassword.value);
        }
    }
}
function updatePasswordStrength(password) {
    const bars = {
        lengthBar: document.getElementById('length-strength'),
        numberBar: document.getElementById('number-strength'),
        caseBar: document.getElementById('case-strength'),
        specialBar: document.getElementById('special-strength'),
        strengthText: document.getElementById('password-strength-text')
    };
    if (!bars.lengthBar || !bars.numberBar || !bars.caseBar || !bars.specialBar || !bars.strengthText)
        return;
    const allBars = [bars.lengthBar, bars.numberBar, bars.caseBar, bars.specialBar];
    allBars.forEach(bar => {
        bar.className = 'h-1 rounded bg-gray-200';
    });
    let strength = 0;
    if (password.length >= 8) {
        bars.lengthBar.classList.add('bg-green-500');
        strength++;
    }
    else if (password.length > 0) {
        bars.lengthBar.classList.add('bg-red-500');
    }
    if (/\d/.test(password)) {
        bars.numberBar.classList.add('bg-green-500');
        strength++;
    }
    else if (password.length > 0) {
        bars.numberBar.classList.add('bg-red-500');
    }
    if (/[a-z]/.test(password) && /[A-Z]/.test(password)) {
        bars.caseBar.classList.add('bg-green-500');
        strength++;
    }
    else if (password.length > 0) {
        bars.caseBar.classList.add('bg-red-500');
    }
    if (/[!@#$%^&*(),.?":{}|<>]/.test(password)) {
        bars.specialBar.classList.add('bg-green-500');
        strength++;
    }
    else if (password.length > 0) {
        bars.specialBar.classList.add('bg-red-500');
    }
    const strengthTexts = [
        'Very weak - Add more characters and complexity',
        'Weak - Try adding numbers or symbols',
        'Medium - Add uppercase letters or symbols',
        'Strong - Good job!',
        'Very strong - Excellent password!'
    ];
    bars.strengthText.textContent = strengthTexts[strength] || 'Password must be at least 8 characters long';
    bars.strengthText.className = 'mt-2 text-xs ' + (strength < 2 ? 'text-red-600' :
        strength < 3 ? 'text-amber-600' :
            strength < 4 ? 'text-yellow-600' : 'text-green-600');
}
function enhanceFormValidation() {
    const form = document.querySelector('.premium-form');
    if (form) {
        form.addEventListener('submit', function (e) {
            const newPassword1 = document.querySelector('[name="new_password1"]');
            const newPassword2 = document.querySelector('[name="new_password2"]');
            if (newPassword1 && newPassword2 && newPassword1.value !== newPassword2.value) {
                e.preventDefault();
                alert('New passwords do not match. Please confirm your new password.');
                newPassword2.focus();
            }
        });
    }
}
document.addEventListener('DOMContentLoaded', function () {
    enhanceFormValidation();
});
//# sourceMappingURL=password_change.js.map