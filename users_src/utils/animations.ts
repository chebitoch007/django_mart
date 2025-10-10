interface ConfettiConfig {
    colors: string[];
    count: number;
    duration?: number;
}

export function createConfetti(config: ConfettiConfig): void {
    const { colors, count, duration = 3 } = config;

    for (let i = 0; i < count; i++) {
        setTimeout(() => {
            createConfettiPiece(colors, duration);
        }, i * 50);
    }
}

function createConfettiPiece(colors: string[], duration: number): void {
    const confetti = document.createElement('div');
    confetti.className = 'confetti';

    const color = colors[Math.floor(Math.random() * colors.length)];
    const size = Math.random() * 10 + 5;
    const left = Math.random() * 100;

    confetti.style.cssText = `
        position: fixed;
        width: ${size}px;
        height: ${size}px;
        background: ${color};
        top: -20px;
        left: ${left}vw;
        opacity: ${Math.random() * 0.7 + 0.3};
        border-radius: ${Math.random() > 0.5 ? '50%' : '2px'};
        animation: confettiFall ${duration}s linear forwards;
        transform: rotate(${Math.random() * 360}deg);
        z-index: 1000;
        pointer-events: none;
    `;

    document.body.appendChild(confetti);

    setTimeout(() => {
        if (confetti.parentNode) {
            confetti.remove();
        }
    }, duration * 1000);
}

export function addRippleAnimation(): void {
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