// users_src/password-reset/password_reset_done.ts - Fixed version
interface CountdownElements {
    countdownElement: HTMLElement | null;
    resendButton: HTMLElement | null;
}

interface ResendResponse {
    success: boolean;
    message: string;
}

function initializePasswordResetDone(): void {
    console.log('Initializing password reset done page...');
    initializeCountdownTimer();
    initializeDoneProgressIndicator(); // ← Renamed this function
    initializeInteractiveElements();
    initializeEmailAnimation();
    initializeSuccessAnimation();
    initializeAutoResend();
}

function initializeCountdownTimer(): void {
    const elements: CountdownElements = {
        countdownElement: document.getElementById('countdown-timer'),
        resendButton: document.getElementById('resend-button')
    };

    if (!elements.countdownElement) {
        console.log('Countdown timer element not found');
        return;
    }

    let timeLeft = 600; // 10 minutes
    const timerInterval = setInterval(() => {
        timeLeft--;

        if (timeLeft <= 0) {
            clearInterval(timerInterval);
            elements.countdownElement!.innerHTML = `
                <div class="countdown-text">
                    <i class="fas fa-exclamation-triangle mr-2"></i>
                    Link expired - request a new one
                </div>
            `;
            return;
        }

        const hours = Math.floor(timeLeft / 3600);
        const minutes = Math.floor((timeLeft % 3600) / 60);
        const seconds = timeLeft % 60;

        // ✅ Format as HH:MM:SS
        const hoursStr = hours.toString().padStart(2, '0');
        const minutesStr = minutes.toString().padStart(2, '0');
        const secondsStr = seconds.toString().padStart(2, '0');

        elements.countdownElement!.innerHTML = `
            <div class="countdown-text">
                <i class="fas fa-clock mr-2"></i>
                Reset link expires in
            </div>
            <div class="countdown-time">
                ${hoursStr}:${minutesStr}:${secondsStr}
            </div>
        `;
    }, 1000);
}

// Renamed this function to avoid conflict
function initializeDoneProgressIndicator(): void {
    const progressSteps = document.querySelectorAll('.progress-step');
    if (!progressSteps.length) return;

    let currentStep = 0;
    const totalSteps = progressSteps.length;

    const progressInterval = setInterval(() => {
        progressSteps.forEach(step => {
            step.classList.remove('active', 'completed');
        });

        for (let i = 0; i < currentStep; i++) {
            if (progressSteps[i]) {
                progressSteps[i].classList.add('completed');
            }
        }

        if (progressSteps[currentStep]) {
            progressSteps[currentStep].classList.add('active');
        }

        currentStep++;

        if (currentStep > totalSteps) {
            clearInterval(progressInterval);
            setTimeout(() => {
                currentStep = 0;
                progressSteps.forEach(step => {
                    step.classList.remove('active', 'completed');
                });
                setTimeout(initializeDoneProgressIndicator, 1000);
            }, 2000);
        }
    }, 800);
}

// ... rest of your password_reset_done.ts code remains the same ...
function initializeInteractiveElements(): void {
    const cards = document.querySelectorAll('.password-reset-done-card');
    cards.forEach(card => {
        card.addEventListener('mouseenter', function(this: HTMLElement): void {
            this.style.transform = 'translateY(-5px)';
        });

        card.addEventListener('mouseleave', function(this: HTMLElement): void {
            this.style.transform = 'translateY(0)';
        });
    });

    const buttons = document.querySelectorAll('.password-reset-done-btn');
    buttons.forEach(button => {
        button.addEventListener('mouseenter', function(this: HTMLElement): void {
            this.style.transform = 'translateY(-2px)';
        });

        button.addEventListener('mouseleave', function(this: HTMLElement): void {
            this.style.transform = 'translateY(0)';
        });

        button.addEventListener('mousedown', function(this: HTMLElement): void {
            this.style.transform = 'scale(0.98)';
        });

        button.addEventListener('mouseup', function(this: HTMLElement): void {
            this.style.transform = 'translateY(-2px)';
        });
    });

    const tips = document.querySelectorAll('.password-reset-done-tips li');
    tips.forEach((tip, index) => {
        const tipElement = tip as HTMLElement;
        tipElement.style.animationDelay = `${index * 0.1}s`;
        tipElement.classList.add('password-reset-done-animation');

        tipElement.addEventListener('click', function(this: HTMLElement): void {
            const link = this.querySelector('a') as HTMLAnchorElement;
            if (link) {
                this.style.backgroundColor = '#f3f4f6';
                setTimeout(() => {
                    window.location.href = link.href;
                }, 200);
            }
        });
    });
}

function initializeEmailAnimation(): void {
    const emailIcon = document.querySelector('.email-sent-animation');
    if (!emailIcon) return;

    setTimeout(() => {
        createEmailParticles();
    }, 1000);

    setInterval(createEmailParticles, 5000);
}

function createEmailParticles(): void {
    const container = document.querySelector('.password-reset-done-container');
    if (!container) return;

    const particles = 3;
    const particleContainer = document.createElement('div');
    particleContainer.style.cssText = `
        position: absolute;
        top: 0;
        left: 0;
        width: 100%;
        height: 100%;
        pointer-events: none;
        z-index: 10;
    `;

    for (let i = 0; i < particles; i++) {
        const particle = document.createElement('div');
        particle.innerHTML = '✉️';
        particle.style.cssText = `
            position: absolute;
            font-size: 1.5rem;
            opacity: 0;
            animation: emailParticle 3s ease-in-out forwards;
            top: ${50 + Math.random() * 20}%;
            left: ${Math.random() * 100}%;
        `;

        particleContainer.appendChild(particle);
    }

    (container as HTMLElement).style.position = 'relative';
    container.appendChild(particleContainer);

    setTimeout(() => {
        if (particleContainer.parentNode) {
            particleContainer.remove();
        }
    }, 3000);
}

function initializeSuccessAnimation(): void {
    const successIcon = document.querySelector('.success-checkmark');
    if (!successIcon) return;

    successIcon.addEventListener('click', function(this: HTMLElement): void {
        this.style.transform = 'scale(1.1)';
        setTimeout(() => {
            this.style.transform = 'scale(1)';
        }, 200);
    });
}

function addEmailParticleAnimation(): void {
    if (!document.querySelector('#email-particle-styles')) {
        const style = document.createElement('style');
        style.id = 'email-particle-styles';
        style.textContent = `
            @keyframes emailParticle {
                0% {
                    transform: translateY(0) translateX(0) rotate(0deg);
                    opacity: 0;
                }
                10% {
                    opacity: 1;
                }
                90% {
                    opacity: 1;
                }
                100% {
                    transform: translateY(-100px) translateX(${Math.random() > 0.5 ? 50 : -50}px) rotate(${Math.random() > 0.5 ? 180 : -180}deg);
                    opacity: 0;
                }
            }
        `;
        document.head.appendChild(style);
    }
}

function initializeAutoResend(): void {
    console.log('Initializing auto resend...');

    const resendButton = document.getElementById('resend-button') as HTMLButtonElement;
    const resendText = document.getElementById('resend-text');
    const countdownElement = document.getElementById('countdown');
    const messageElement = document.getElementById('resend-message');

    if (!resendButton || !resendText || !countdownElement) {
        console.error('Required elements for resend not found');
        return;
    }

    // Check if resend URL is available
    const resendUrl = resendButton.dataset.resendUrl;
    if (!resendUrl) {
        console.error('Resend URL not found in data-resend-url attribute');
        resendButton.disabled = true;
        resendText.innerHTML = '<i class="fas fa-exclamation-triangle mr-2"></i>Resend unavailable';
        return;
    }

    console.log('All resend elements found, URL:', resendUrl);

    // Create message element if it doesn't exist
    let messageContainer = messageElement;
    if (!messageContainer) {
        messageContainer = document.createElement('div');
        messageContainer.id = 'resend-message';
        messageContainer.className = 'mt-2 text-center hidden';
        resendButton.parentNode?.insertBefore(messageContainer, resendButton.nextSibling);
    }

    let canResend = false;
    let resendTimer = 60;

    const updateResendButton = (): void => {
        if (canResend) {
            resendText.innerHTML = '<i class="fas fa-redo mr-2"></i>Resend Email';
            resendButton.classList.remove('opacity-50', 'cursor-not-allowed');
            resendButton.classList.add('cursor-pointer', 'hover:bg-gray-100');
            resendButton.disabled = false;
        } else {
            resendText.innerHTML = `<i class="fas fa-clock mr-2"></i>Resend available in <span id="countdown">${resendTimer}</span>s`;
            resendButton.classList.add('opacity-50', 'cursor-not-allowed');
            resendButton.classList.remove('cursor-pointer', 'hover:bg-gray-100');
            resendButton.disabled = true;
        }
    };

    // Initial countdown
    const countdown = setInterval(() => {
        resendTimer--;
        updateResendButton();

        if (resendTimer <= 0) {
            clearInterval(countdown);
            canResend = true;
            updateResendButton();
        }
    }, 1000);

    resendButton.addEventListener('click', async function(e: Event): Promise<void> {
        e.preventDefault();

        if (!canResend) {
            console.log('Resend not available yet');
            return;
        }

        console.log('Resend button clicked, URL:', resendUrl);

        // Disable button and show loading state
        canResend = false;
        resendButton.disabled = true;
        resendButton.classList.add('opacity-50', 'cursor-not-allowed');
        resendText.innerHTML = '<i class="fas fa-spinner fa-spin mr-2"></i>Sending...';

        try {
            const csrfToken = getCsrfToken();
            console.log('CSRF Token:', csrfToken ? 'Found' : 'Not found');

            const response = await fetch(resendUrl, {  // Use the resendUrl variable
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': csrfToken,
                    'X-Requested-With': 'XMLHttpRequest'
                },
                body: JSON.stringify({}),
            });

            // Check if response is OK before parsing JSON
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }

            const data: ResendResponse = await response.json();
            console.log('Resend response:', data);

            if (data.success) {
                showMessage(messageContainer!, data.message, 'success');

                // Reset countdown
                resendTimer = 60;
                updateResendButton();

                // Restart countdown
                const newCountdown = setInterval(() => {
                    resendTimer--;
                    updateResendButton();

                    if (resendTimer <= 0) {
                        clearInterval(newCountdown);
                        canResend = true;
                        resendButton.disabled = false;
                        updateResendButton();
                    }
                }, 1000);

            } else {
                showMessage(messageContainer!, data.message, 'error');
                canResend = true;
                resendButton.disabled = false;
                updateResendButton();
            }

        } catch (error) {
            console.error('Resend error:', error);
            showMessage(messageContainer!, 'Network error. Please try again.', 'error');
            canResend = true;
            resendButton.disabled = false;
            updateResendButton();
        }
    });

    // Initial update
    updateResendButton();
}

function showMessage(element: HTMLElement, message: string, type: 'success' | 'error'): void {
    element.textContent = message;
    element.className = 'mt-2 text-center p-2 rounded';

    if (type === 'success') {
        element.classList.add('bg-green-100', 'text-green-800', 'border', 'border-green-200');
    } else {
        element.classList.add('bg-red-100', 'text-red-800', 'border', 'border-red-200');
    }

    element.classList.remove('hidden');

    // Auto-hide message after 5 seconds
    setTimeout(() => {
        element.classList.add('hidden');
    }, 5000);
}

function getCsrfToken(): string {
    const name = 'csrftoken';
    let cookieValue = '';
    if (document.cookie && document.cookie !== '') {
        const cookies = document.cookie.split(';');
        for (let i = 0; i < cookies.length; i++) {
            const cookie = cookies[i].trim();
            if (cookie.substring(0, name.length + 1) === (name + '=')) {
                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                break;
            }
        }
    }
    return cookieValue;
}

// Initialize when DOM is loaded
addEmailParticleAnimation();

document.addEventListener('DOMContentLoaded', function(): void {
    console.log('DOM loaded, initializing password reset done...');
    initializePasswordResetDone();
});