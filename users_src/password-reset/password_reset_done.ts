interface CountdownElements {
    countdownElement: HTMLElement | null;
    resendButton: HTMLElement | null;
}

function initializePasswordResetDone(): void {
    initializeCountdownTimer();
    initializeProgressIndicator();
    initializeInteractiveElements();
    initializeEmailAnimation();
    initializeSuccessAnimation();
}

function initializeCountdownTimer(): void {
    const elements: CountdownElements = {
        countdownElement: document.getElementById('countdown-timer'),
        resendButton: document.getElementById('resend-button')
    };

    if (!elements.countdownElement) return;

    let timeLeft = 600;
    const timerInterval = setInterval(() => {
        timeLeft--;

        if (timeLeft <= 0) {
            clearInterval(timerInterval);
            if (elements.countdownElement) {
                elements.countdownElement.innerHTML = `
                    <div class="countdown-text">
                        <i class="fas fa-exclamation-triangle mr-2"></i>
                        Link expired - request a new one
                    </div>
                `;
            }
            return;
        }

        const minutes = Math.floor(timeLeft / 60);
        const seconds = timeLeft % 60;

        if (elements.countdownElement) {
            elements.countdownElement.innerHTML = `
                <div class="countdown-text">
                    <i class="fas fa-clock mr-2"></i>
                    Reset link expires in
                </div>
                <div class="countdown-time">
                    ${minutes.toString().padStart(2, '0')}:${seconds.toString().padStart(2, '0')}
                </div>
            `;
        }
    }, 1000);
}

function initializeProgressIndicator(): void {
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
                setTimeout(initializeProgressIndicator, 1000);
            }, 2000);
        }
    }, 800);
}

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
    const resendButton = document.getElementById('resend-button') as HTMLButtonElement;
    if (!resendButton) return;

    let canResend = false;
    let resendTimer = 60;

    const updateResendButton = (): void => {
        if (canResend) {
            resendButton.innerHTML = '<i class="fas fa-redo mr-2"></i>Resend Email';
            resendButton.classList.remove('opacity-50', 'cursor-not-allowed');
            resendButton.classList.add('cursor-pointer');
        } else {
            resendButton.innerHTML = `<i class="fas fa-clock mr-2"></i>Resend available in ${resendTimer}s`;
            resendButton.classList.add('opacity-50', 'cursor-not-allowed');
            resendButton.classList.remove('cursor-pointer');
        }
    };

    const countdown = setInterval(() => {
        resendTimer--;
        updateResendButton();

        if (resendTimer <= 0) {
            clearInterval(countdown);
            canResend = true;
            updateResendButton();
        }
    }, 1000);

    resendButton.addEventListener('click', function(e: Event): void {
        if (!canResend) {
            e.preventDefault();
            return;
        }

        console.log('Resending password reset email...');

        canResend = false;
        resendTimer = 60;
        updateResendButton();

        const newCountdown = setInterval(() => {
            resendTimer--;
            updateResendButton();

            if (resendTimer <= 0) {
                clearInterval(newCountdown);
                canResend = true;
                updateResendButton();
            }
        }, 1000);
    });
}

addEmailParticleAnimation();

document.addEventListener('DOMContentLoaded', function(): void {
    initializePasswordResetDone();
});

export {
    initializePasswordResetDone,
    initializeCountdownTimer,
    initializeProgressIndicator
};