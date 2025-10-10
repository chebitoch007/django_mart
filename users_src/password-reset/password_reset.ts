interface MessageTypes {
    [key: string]: {
        icon: string;
        title: string;
        bgClass: string;
    };
}

interface FormElements {
    form: HTMLFormElement | null;
    emailInput: HTMLInputElement | null;
    emailError: HTMLElement | null;
    emailErrorText: HTMLElement | null;
    emailHelp: HTMLElement | null;
    messageContainer: HTMLElement | null;
    loginLink: HTMLElement | null;
}

document.addEventListener('DOMContentLoaded', function (): void {
    const elements: FormElements = {
        form: document.getElementById('password-reset-form') as HTMLFormElement,
        emailInput: document.getElementById('email') as HTMLInputElement,
        emailError: document.getElementById('email-error'),
        emailErrorText: document.getElementById('email-error-text'),
        emailHelp: document.getElementById('email-help'),
        messageContainer: document.getElementById('message-container'),
        loginLink: document.getElementById('login-link')
    };

    if (!elements.form) return;

    function showMessage(type: string, text: string): void {
        const messageTypes: MessageTypes = {
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

    function validateEmail(email: string): boolean {
        const re = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
        return re.test(email);
    }

    if (elements.emailInput) {
        elements.emailInput.addEventListener('blur', function (): void {
            const email = elements.emailInput!.value.trim();

            if (email === '') {
                if (elements.emailError) elements.emailError.classList.remove('hidden');
                if (elements.emailErrorText) elements.emailErrorText.classList.remove('hidden');
                const errorMessage = document.getElementById('error-message');
                if (errorMessage) {
                    errorMessage.textContent = 'Email is required';
                }
                if (elements.emailHelp) elements.emailHelp.classList.add('hidden');
                if (elements.emailInput) {
                    elements.emailInput.classList.add('border-red-500', 'ring-1', 'ring-red-500');
                }
            } else if (!validateEmail(email)) {
                if (elements.emailError) elements.emailError.classList.remove('hidden');
                if (elements.emailErrorText) elements.emailErrorText.classList.remove('hidden');
                const errorMessage = document.getElementById('error-message');
                if (errorMessage) {
                    errorMessage.textContent = 'Please enter a valid email address';
                }
                if (elements.emailHelp) elements.emailHelp.classList.add('hidden');
                if (elements.emailInput) {
                    elements.emailInput.classList.add('border-red-500', 'ring-1', 'ring-red-500');
                }
            } else {
                if (elements.emailError) elements.emailError.classList.add('hidden');
                if (elements.emailErrorText) elements.emailErrorText.classList.add('hidden');
                if (elements.emailHelp) elements.emailHelp.classList.remove('hidden');
                if (elements.emailInput) {
                    elements.emailInput.classList.remove('border-red-500', 'ring-1', 'ring-red-500');
                }
            }
        });
    }

    elements.form.addEventListener('submit', function (e: Event): void {
        e.preventDefault();

        if (!elements.emailInput) return;

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

        const submitButton = elements.form!.querySelector('button[type="submit"]') as HTMLButtonElement;
        const originalText = submitButton.innerHTML;
        submitButton.innerHTML = '<i class="fas fa-spinner fa-spin mr-2"></i>Sending...';
        submitButton.disabled = true;

        // ACTUALLY SUBMIT THE FORM TO DJANGO
        // Create a hidden form and submit it
        const hiddenForm = document.createElement('form');
        hiddenForm.method = 'POST';
        hiddenForm.action = elements.form!.action || window.location.href; // Fixed: added ! to elements.form
        hiddenForm.style.display = 'none';

        // Add CSRF token
        const csrfToken = document.querySelector('[name=csrfmiddlewaretoken]') as HTMLInputElement;
        if (csrfToken) {
            const csrfInput = document.createElement('input');
            csrfInput.type = 'hidden';
            csrfInput.name = 'csrfmiddlewaretoken';
            csrfInput.value = csrfToken.value;
            hiddenForm.appendChild(csrfInput);
        }

        // Add email field
        const emailInput = document.createElement('input');
        emailInput.type = 'email';
        emailInput.name = 'email';
        emailInput.value = email;
        hiddenForm.appendChild(emailInput);

        document.body.appendChild(hiddenForm);
        hiddenForm.submit();

        // Show success message immediately while form submits
        showMessage('success', 'Password reset link has been sent to your email! Check your console for the reset link.');

        // Reset UI state
        submitButton.innerHTML = originalText;
        submitButton.disabled = false;
        elements.form!.reset();

        if (elements.emailError) elements.emailError.classList.add('hidden');
        if (elements.emailErrorText) elements.emailErrorText.classList.add('hidden');
        if (elements.emailHelp) elements.emailHelp.classList.remove('hidden');
        if (elements.emailInput) {
            elements.emailInput.classList.remove('border-red-500', 'ring-1', 'ring-red-500');
        }
    });

    if (elements.loginLink) {
        elements.loginLink.addEventListener('click', function (e: Event): void {
            e.preventDefault();
            // Actually redirect to login page
            const loginUrl = this.getAttribute('href');
            if (loginUrl && loginUrl !== '#') {
                window.location.href = loginUrl;
            } else {
                // Fallback to default login URL
                window.location.href = '/accounts/login/';
            }
        });
    }
});