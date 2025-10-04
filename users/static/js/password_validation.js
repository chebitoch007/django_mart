document.addEventListener('DOMContentLoaded', function () {
    const passwordInput = document.getElementById('id_new_password1');
    const requirements = {
        length: document.querySelector('[data-requirement="length"]'),
        common: document.querySelector('[data-requirement="common"]'),
        numeric: document.querySelector('[data-requirement="numeric"]'),
        similar: document.querySelector('[data-requirement="similar"]')
    };

    const strengthBar = document.querySelector('.strength-bar');
    const strengthText = document.querySelector('.strength-text');
    const submitBtn = document.getElementById('submit-btn');

    const commonPasswords = ['password', '12345678', 'qwerty'];

    function isCommonPassword(password) {
        return commonPasswords.includes(password.toLowerCase());
    }

    function calculateStrength(password) {
        let score = 0;
        if (password.length >= 8) score += 1;
        if (password.length >= 12) score += 1;
        if (/[A-Z]/.test(password)) score += 1;
        if (/[0-9]/.test(password)) score += 1;
        if (/[^A-Za-z0-9]/.test(password)) score += 1;
        if (isCommonPassword(password)) score = Math.max(0, score - 2);
        return Math.min(2, Math.floor(score / 2));
    }

    function updateStrengthMeter(strength) {
        strengthBar.className = `strength-bar strength-${strength}`;
        const labels = ['Weak', 'Medium', 'Strong'];
        strengthText.textContent = labels[strength];
    }

    if (passwordInput) {
        passwordInput.addEventListener('input', function () {
            const password = this.value;

            // Validation checks
            requirements.length?.classList.toggle('valid', password.length >= 8);
            requirements.common?.classList.toggle('valid', !isCommonPassword(password));
            requirements.numeric?.classList.toggle('valid', !/^\d+$/.test(password));
            requirements.similar?.classList.toggle('valid', !password.toLowerCase().includes('admin') && !password.toLowerCase().includes('user'));

            // Strength meter
            const strength = calculateStrength(password);
            updateStrengthMeter(strength);
        });
    }

    // Password visibility toggle
    document.querySelectorAll('.toggle-password').forEach(button => {
        button.addEventListener('click', function () {
            const target = document.getElementById(this.dataset.target);
            const icon = this.querySelector('i');
            if (target && icon) {
                const isPassword = target.type === 'password';
                target.type = isPassword ? 'text' : 'password';
                icon.classList.replace(isPassword ? 'bi-eye-slash' : 'bi-eye', isPassword ? 'bi-eye' : 'bi-eye-slash');
            }
        });
    });

    // Submit loading state
    const form = document.getElementById('password-change-form');
    if (form && submitBtn) {
        form.addEventListener('submit', function () {
            submitBtn.disabled = true;
            submitBtn.querySelector('.btn-text').textContent = 'Updating...';
            submitBtn.querySelector('.spinner-border')?.classList.remove('d-none');
        });
    }

    // Handle server-side error feedback
    document.querySelectorAll('.errorlist').forEach(error => {
        error.closest('.form-group')?.classList.add('has-error');
    });
});