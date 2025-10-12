// account.ts
interface BrowserTimeout {
    (callback: (...args: any[]) => void, ms: number): number;
}

interface SessionData {
    sessionTimeout: string | null;
    logoutUrl: string | null;
    keepaliveUrl: string | null;
    csrfToken: string | null;
}

class AccountPage {
    private timeoutWarning: number | null = null;
    private logoutTimer: number | null = null;
    private sessionTimer: number | null = null;
    private timeLeft: number = 120;

    constructor() {
        this.initialize();
    }

    private initialize(): void {
        this.initializeSmoothScrolling();
        this.initializeCardAnimations();
        this.initializeProfileImageErrorHandling();
        this.initializeSessionTimeout();
    }

    private initializeSmoothScrolling(): void {
        const navItems = document.querySelectorAll('.account-nav-item');

        navItems.forEach(item => {
            item.addEventListener('click', (e: Event) => {
                e.preventDefault();
                const targetId = (e.currentTarget as HTMLElement).getAttribute('href');

                if (targetId && targetId.startsWith('#')) {
                    const targetElement = document.querySelector(targetId);

                    if (targetElement) {
                        targetElement.scrollIntoView({
                            behavior: 'smooth',
                            block: 'start'
                        });
                    }
                }
            });
        });
    }

    private initializeCardAnimations(): void {
        const cards = document.querySelectorAll('.card-hover');

        cards.forEach(card => {
            card.addEventListener('mouseenter', () => {
                (card as HTMLElement).style.transform = 'translateY(-5px)';
            });

            card.addEventListener('mouseleave', () => {
                (card as HTMLElement).style.transform = 'translateY(0)';
            });
        });
    }

    private initializeProfileImageErrorHandling(): void {
        const profileImage = document.getElementById('profile-image') as HTMLImageElement;

        if (profileImage) {
            profileImage.addEventListener('error', () => {
                const defaultImage = profileImage.getAttribute('data-default-src');
                if (defaultImage) {
                    profileImage.src = defaultImage;
                }
            });
        }
    }

    private initializeSessionTimeout(): void {
        const sessionTimeoutModal = document.getElementById('sessionTimeoutModal');
        if (!sessionTimeoutModal) return;

        const sessionData: SessionData = {
            sessionTimeout: document.body.getAttribute('data-session-timeout'),
            logoutUrl: document.body.getAttribute('data-logout-url'),
            keepaliveUrl: document.body.getAttribute('data-keepalive-url'),
            csrfToken: document.body.getAttribute('data-csrf-token')
        };

        if (!sessionData.sessionTimeout || !sessionData.logoutUrl) return;

        const SESSION_TIMEOUT = parseInt(sessionData.sessionTimeout);
        const WARNING_TIME = 120;

        this.startTimers(SESSION_TIMEOUT, WARNING_TIME, sessionData);

        // Reset timers on user activity
        document.addEventListener('mousemove', () => this.resetTimers(SESSION_TIMEOUT, WARNING_TIME, sessionData));
        document.addEventListener('keypress', () => this.resetTimers(SESSION_TIMEOUT, WARNING_TIME, sessionData));
    }

    private startTimers(sessionTimeout: number, warningTime: number, sessionData: SessionData): void {
        this.timeoutWarning = window.setTimeout(() => {
            this.showTimeoutWarning(warningTime, sessionData);
        }, (sessionTimeout - warningTime) * 1000);

        this.logoutTimer = window.setTimeout(() => {
            this.logoutUser(sessionData);
        }, sessionTimeout * 1000);
    }

    private showTimeoutWarning(warningTime: number, sessionData: SessionData): void {
        const modalElement = document.getElementById('sessionTimeoutModal');
        if (!modalElement) return;

        // Using Bootstrap modal - you might need to adjust this based on your modal implementation
        const modal = new (window as any).bootstrap.Modal(modalElement);
        modal.show();

        this.timeLeft = warningTime;

        const countdown = setInterval(() => {
            this.timeLeft--;
            const timeLeftElement = document.getElementById('timeLeft');

            if (timeLeftElement) {
                const minutes = Math.floor(this.timeLeft / 60).toString().padStart(2, '0');
                const seconds = (this.timeLeft % 60).toString().padStart(2, '0');

                timeLeftElement.textContent = `${minutes}:${seconds}`;
            }

            const progress = (this.timeLeft / warningTime) * 100;
            const sessionProgress = document.getElementById('sessionProgress');

            if (sessionProgress) {
                sessionProgress.style.width = `${progress}%`;
            }

            if (this.timeLeft <= 0) {
                clearInterval(countdown);
                this.logoutUser(sessionData);
            }
        }, 1000);

        const extendSessionBtn = document.getElementById('extendSessionBtn');
        if (extendSessionBtn) {
            extendSessionBtn.addEventListener('click', () => {
                clearInterval(countdown);
                modal.hide();
                this.extendSession(sessionData);
            });
        }

        const logoutNowBtn = document.getElementById('logoutNowBtn');
        if (logoutNowBtn) {
            logoutNowBtn.addEventListener('click', () => {
                clearInterval(countdown);
                this.logoutUser(sessionData);
            });
        }
    }

    private logoutUser(sessionData: SessionData): void {
        if (!sessionData.logoutUrl || !sessionData.csrfToken) return;

        const form = document.createElement('form');
        form.method = 'post';
        form.action = sessionData.logoutUrl;

        const csrf = document.createElement('input');
        csrf.type = 'hidden';
        csrf.name = 'csrfmiddlewaretoken';
        csrf.value = sessionData.csrfToken;
        form.appendChild(csrf);

        document.body.appendChild(form);
        form.submit();
    }

    private extendSession(sessionData: SessionData): void {
        if (this.timeoutWarning) clearTimeout(this.timeoutWarning);
        if (this.logoutTimer) clearTimeout(this.logoutTimer);
        if (this.sessionTimer) clearInterval(this.sessionTimer);

        if (sessionData.keepaliveUrl) {
            fetch(sessionData.keepaliveUrl, { method: 'HEAD' })
                .then(() => {
                    this.timeLeft = 120;
                    // Restart timers - you might want to get fresh timeout values
                    const SESSION_TIMEOUT = parseInt(sessionData.sessionTimeout || '1800');
                    this.startTimers(SESSION_TIMEOUT, 120, sessionData);
                })
                .catch(() => {
                    this.timeLeft = 120;
                    const SESSION_TIMEOUT = parseInt(sessionData.sessionTimeout || '1800');
                    this.startTimers(SESSION_TIMEOUT, 120, sessionData);
                });
        } else {
            this.timeLeft = 120;
            const SESSION_TIMEOUT = parseInt(sessionData.sessionTimeout || '1800');
            this.startTimers(SESSION_TIMEOUT, 120, sessionData);
        }
    }

    private resetTimers(sessionTimeout: number, warningTime: number, sessionData: SessionData): void {
        if (this.timeoutWarning) clearTimeout(this.timeoutWarning);
        if (this.logoutTimer) clearTimeout(this.logoutTimer);
        if (this.sessionTimer) clearInterval(this.sessionTimer);
        this.startTimers(sessionTimeout, warningTime, sessionData);
    }
}

// Initialize the account page when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    new AccountPage();
});