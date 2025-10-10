function initializePasswordResetComplete() {
    createConfettiCelebration();
    initializeStaggerAnimations();
    initializeProgressIndicator();
    initializeInteractiveTips();
    initializeButtonInteractions();
}
function createConfettiCelebration() {
    const config = {
        colors: ['#10b981', '#2563eb', '#8b5cf6', '#f97316', '#f59e0b', '#ef4444'],
        count: 60
    };
    for (let i = 0; i < config.count; i++) {
        setTimeout(() => {
            createConfettiPiece(config.colors);
        }, i * 50);
    }
}
function createConfettiPiece(colors) {
    const confetti = document.createElement('div');
    confetti.className = 'confetti';
    const color = colors[Math.floor(Math.random() * colors.length)];
    const size = Math.random() * 10 + 5;
    const left = Math.random() * 100;
    const animationDuration = Math.random() * 3 + 2;
    confetti.style.cssText = `
        position: fixed;
        width: ${size}px;
        height: ${size}px;
        background: ${color};
        top: -20px;
        left: ${left}vw;
        opacity: ${Math.random() * 0.7 + 0.3};
        border-radius: ${Math.random() > 0.5 ? '50%' : '2px'};
        animation: confettiFall ${animationDuration}s linear forwards;
        transform: rotate(${Math.random() * 360}deg);
        z-index: 1000;
        pointer-events: none;
    `;
    document.body.appendChild(confetti);
    setTimeout(() => {
        if (confetti.parentNode) {
            confetti.remove();
        }
    }, animationDuration * 1000);
}
function initializeStaggerAnimations() {
    const animatedElements = document.querySelectorAll('.password-reset-stagger-animation');
    animatedElements.forEach((element, index) => {
        element.style.animationDelay = `${index * 0.2}s`;
    });
}
function initializeProgressIndicator() {
    const progressBar = document.querySelector('.password-reset-progress-bar');
    if (progressBar) {
        setTimeout(() => {
            progressBar.style.opacity = '0.7';
        }, 1600);
    }
}
function initializeInteractiveTips() {
    const tips = document.querySelectorAll('.password-reset-tips li');
    tips.forEach((tip, index) => {
        const tipElement = tip;
        tipElement.style.animationDelay = `${index * 0.1 + 0.5}s`;
        tipElement.classList.add('password-reset-stagger-animation');
        tipElement.addEventListener('click', function () {
            this.style.transform = 'scale(1.02)';
            this.style.transition = 'transform 0.2s ease';
            setTimeout(() => {
                this.style.transform = 'scale(1)';
            }, 200);
        });
    });
}
function initializeButtonInteractions() {
    const buttons = document.querySelectorAll('.password-reset-btn');
    buttons.forEach(button => {
        const buttonElement = button;
        buttonElement.addEventListener('mouseenter', function () {
            this.style.transform = 'translateY(-2px)';
        });
        buttonElement.addEventListener('mouseleave', function () {
            this.style.transform = 'translateY(0)';
        });
        buttonElement.addEventListener('mousedown', function () {
            this.style.transform = 'scale(0.98)';
        });
        buttonElement.addEventListener('mouseup', function () {
            this.style.transform = 'translateY(-2px)';
        });
        buttonElement.addEventListener('click', function (e) {
            createRippleEffect(e, this);
        });
    });
}
function createRippleEffect(event, element) {
    const ripple = document.createElement('span');
    const rect = element.getBoundingClientRect();
    const size = Math.max(rect.width, rect.height);
    const x = event.clientX - rect.left - size / 2;
    const y = event.clientY - rect.top - size / 2;
    ripple.style.cssText = `
        position: absolute;
        border-radius: 50%;
        background: rgba(255, 255, 255, 0.6);
        transform: scale(0);
        animation: ripple-animation 0.6s linear;
        pointer-events: none;
        width: ${size}px;
        height: ${size}px;
        left: ${x}px;
        top: ${y}px;
    `;
    element.style.position = 'relative';
    element.style.overflow = 'hidden';
    element.appendChild(ripple);
    setTimeout(() => {
        ripple.remove();
    }, 600);
}
function addRippleAnimation() {
    if (!document.querySelector('#ripple-styles')) {
        const style = document.createElement('style');
        style.id = 'ripple-styles';
        style.textContent = `
            @keyframes ripple-animation {
                to {
                    transform: scale(4);
                    opacity: 0;
                }
            }
        `;
        document.head.appendChild(style);
    }
}
function initializeAutoRedirect() {
    const redirectTime = 10000;
    const loginButton = document.querySelector('[href*="login"]');
    if (loginButton) {
        let timeLeft = redirectTime / 1000;
        const originalText = loginButton.innerHTML;
        const countdownInterval = setInterval(() => {
            timeLeft--;
            loginButton.innerHTML = `<i class="fas fa-sign-in-alt mr-2"></i>Sign In Now (${timeLeft}s)`;
            if (timeLeft <= 0) {
                clearInterval(countdownInterval);
                window.location.href = loginButton.href;
            }
        }, 1000);
        loginButton.addEventListener('click', () => {
            clearInterval(countdownInterval);
            loginButton.innerHTML = originalText;
        });
    }
}
addRippleAnimation();
document.addEventListener('DOMContentLoaded', function () {
    initializePasswordResetComplete();
});
export { initializePasswordResetComplete, createConfettiCelebration };
//# sourceMappingURL=password_reset_complete.js.map