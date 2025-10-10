interface ConfettiConfig {
    colors: string[];
    count: number;
}

function initializePasswordSuccessPage(): void {
    createConfetti();
    initializeSecurityTips();
    initializeButtonInteractions();
    initializeProgressIndicator();
}

function createConfetti(): void {
    const config: ConfettiConfig = {
        colors: ['#10b981', '#2563eb', '#8b5cf6', '#f97316', '#f59e0b', '#ef4444'],
        count: 50
    };

    const container = document.createElement('div');
    container.className = 'confetti-container';
    container.style.cssText = 'position: fixed; top: 0; left: 0; width: 100%; height: 100%; pointer-events: none; z-index: 1000;';

    for (let i = 0; i < config.count; i++) {
        const confetti = document.createElement('div');
        confetti.className = 'confetti';
        confetti.style.cssText = `
            position: absolute;
            width: ${Math.random() * 10 + 5}px;
            height: ${Math.random() * 10 + 5}px;
            background: ${config.colors[Math.floor(Math.random() * config.colors.length)]};
            top: -20px;
            left: ${Math.random() * 100}vw;
            opacity: ${Math.random() * 0.5 + 0.5};
            border-radius: ${Math.random() > 0.5 ? '50%' : '2px'};
            animation: confettiFall ${Math.random() * 3 + 2}s linear forwards;
            transform: rotate(${Math.random() * 360}deg);
        `;

        container.appendChild(confetti);
    }

    document.body.appendChild(container);

    setTimeout(() => {
        if (container.parentNode) {
            container.remove();
        }
    }, 5000);
}

function initializeSecurityTips(): void {
    const tips = document.querySelectorAll('.security-tip');

    tips.forEach((tip, index) => {
        const tipElement = tip as HTMLElement;
        tipElement.style.animationDelay = `${index * 0.1}s`;
        tipElement.classList.add('animate-fade-in');

        tipElement.addEventListener('click', function(this: HTMLElement): void {
            const link = this.querySelector('a') as HTMLAnchorElement;
            if (link) {
                link.click();
            }
        });
    });
}

function initializeButtonInteractions(): void {
    const buttons = document.querySelectorAll('.password-success-btn');

    buttons.forEach(button => {
        button.addEventListener('mouseenter', function(this: HTMLElement): void {
            this.style.transform = 'translateY(-2px)';
        });

        button.addEventListener('mouseleave', function(this: HTMLElement): void {
            this.style.transform = 'translateY(0)';
        });

        button.addEventListener('mousedown', function(this: HTMLElement): void {
            this.style.transform = 'translateY(0)';
        });
    });
}

function initializeProgressIndicator(): void {
    const securityLevel = document.querySelector('.security-level') as HTMLElement;
    if (securityLevel) {
        let progress = 0;
        const interval = setInterval(() => {
            progress += 5;
            securityLevel.style.width = `${progress}%`;

            if (progress >= 85) {
                clearInterval(interval);
            }
        }, 50);
    }
}

document.addEventListener('visibilitychange', function(): void {
    if (!document.hidden) {
        initializeSecurityTips();
    }
});

document.addEventListener('DOMContentLoaded', function(): void {
    initializePasswordSuccessPage();
});

export {
    initializePasswordSuccessPage,
    createConfetti,
    initializeSecurityTips
};