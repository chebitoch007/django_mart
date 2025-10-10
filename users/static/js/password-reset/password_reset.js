"use strict";
document.addEventListener('DOMContentLoaded', function () {
    const elements = {
        form: document.getElementById('password-reset-form'),
        emailInput: document.getElementById('email'),
        emailError: document.getElementById('email-error'),
        emailErrorText: document.getElementById('email-error-text'),
        emailHelp: document.getElementById('email-help'),
        messageContainer: document.getElementById('message-container'),
        loginLink: document.getElementById('login-link')
    };
    if (!elements.form)
        return;
    function showMessage(type, text) {
        const messageTypes = {
            success: {
                icon: 'fa-check-circle',
                title: 'Success!',
                bgClass: 'success-alert'
            },
            error: {
                icon: 'fa-exclamation-circle',
                title: 'Action Required',
                bgClass: 'error-alert'
            },
            info: {
                icon: 'fa-info-circle',
                title: 'Notice',
                bgClass: 'info-alert'
            }
        };
        const messageType = messageTypes[type] || messageTypes.info;
        const messageHTML = `
                <div class="rounded-xl p-4 ${messageType.bgClass}">
                    <div class="flex">
                        <div class="flex-shrink-0">
                            <i class="fas ${messageType.icon} text-lg ${type === 'success' ? 'text-green-500' : type === 'error' ? 'text-red-500' : 'text-blue-500'}"></i>
                        </div>
                        <div class="ml-3">
                            <h4 class="font-semibold ${type === 'success' ? 'text-green-800' : type === 'error' ? 'text-red-800' : 'text-blue-800'}">
                                ${messageType.title}
                            </h4>
                            <p class="mt-1 text-sm ${type === 'success' ? 'text-green-700' : type === 'error' ? 'text-red-700' : 'text-blue-700'}">
                                ${text}
                            </p>
                        </div>
                    </div>
                </div>
            `;
        if (elements.messageContainer) {
            elements.messageContainer.innerHTML = messageHTML;
        }
    }
    function validateEmail(email) {
        const re = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
        return re.test(email);
    }
    if (elements.emailInput) {
        elements.emailInput.addEventListener('blur', function () {
            const email = elements.emailInput.value.trim();
            if (email === '') {
                if (elements.emailError)
                    elements.emailError.classList.remove('hidden');
                if (elements.emailErrorText)
                    elements.emailErrorText.classList.remove('hidden');
                const errorMessage = document.getElementById('error-message');
                if (errorMessage) {
                    errorMessage.textContent = 'Email is required';
                }
                if (elements.emailHelp)
                    elements.emailHelp.classList.add('hidden');
                if (elements.emailInput) {
                    elements.emailInput.classList.add('border-red-500', 'ring-1', 'ring-red-500');
                }
            }
            else if (!validateEmail(email)) {
                if (elements.emailError)
                    elements.emailError.classList.remove('hidden');
                if (elements.emailErrorText)
                    elements.emailErrorText.classList.remove('hidden');
                const errorMessage = document.getElementById('error-message');
                if (errorMessage) {
                    errorMessage.textContent = 'Please enter a valid email address';
                }
                if (elements.emailHelp)
                    elements.emailHelp.classList.add('hidden');
                if (elements.emailInput) {
                    elements.emailInput.classList.add('border-red-500', 'ring-1', 'ring-red-500');
                }
            }
            else {
                if (elements.emailError)
                    elements.emailError.classList.add('hidden');
                if (elements.emailErrorText)
                    elements.emailErrorText.classList.add('hidden');
                if (elements.emailHelp)
                    elements.emailHelp.classList.remove('hidden');
                if (elements.emailInput) {
                    elements.emailInput.classList.remove('border-red-500', 'ring-1', 'ring-red-500');
                }
            }
        });
    }
    elements.form.addEventListener('submit', function (e) {
        e.preventDefault();
        if (!elements.emailInput)
            return;
        const email = elements.emailInput.value.trim();
        if (email === '') {
            showMessage('error', 'Please enter your email address');
            elements.emailInput.focus();
            return;
        }
        if (!validateEmail(email)) {
            showMessage('error', 'Please enter a valid email address');
            elements.emailInput.focus();
            return;
        }
        const submitButton = elements.form.querySelector('button[type="submit"]');
        const originalText = submitButton.innerHTML;
        submitButton.innerHTML = '<i class="fas fa-spinner fa-spin mr-2"></i>Sending...';
        submitButton.disabled = true;
        const hiddenForm = document.createElement('form');
        hiddenForm.method = 'POST';
        hiddenForm.action = elements.form.action || window.location.href;
        hiddenForm.style.display = 'none';
        const csrfToken = document.querySelector('[name=csrfmiddlewaretoken]');
        if (csrfToken) {
            const csrfInput = document.createElement('input');
            csrfInput.type = 'hidden';
            csrfInput.name = 'csrfmiddlewaretoken';
            csrfInput.value = csrfToken.value;
            hiddenForm.appendChild(csrfInput);
        }
        const emailInput = document.createElement('input');
        emailInput.type = 'email';
        emailInput.name = 'email';
        emailInput.value = email;
        hiddenForm.appendChild(emailInput);
        document.body.appendChild(hiddenForm);
        hiddenForm.submit();
        showMessage('success', 'Password reset link has been sent to your email! Check your console for the reset link.');
        submitButton.innerHTML = originalText;
        submitButton.disabled = false;
        elements.form.reset();
        if (elements.emailError)
            elements.emailError.classList.add('hidden');
        if (elements.emailErrorText)
            elements.emailErrorText.classList.add('hidden');
        if (elements.emailHelp)
            elements.emailHelp.classList.remove('hidden');
        if (elements.emailInput) {
            elements.emailInput.classList.remove('border-red-500', 'ring-1', 'ring-red-500');
        }
    });
    if (elements.loginLink) {
        elements.loginLink.addEventListener('click', function (e) {
            e.preventDefault();
            const loginUrl = this.getAttribute('href');
            if (loginUrl && loginUrl !== '#') {
                window.location.href = loginUrl;
            }
            else {
                window.location.href = '/accounts/login/';
            }
        });
    }
});
//# sourceMappingURL=password_reset.js.map