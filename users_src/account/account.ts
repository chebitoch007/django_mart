import { BrowserTimeout } from '../types/dom';

interface SessionData {
    sessionTimeout: string | null;
    logoutUrl: string | null;
    keepaliveUrl: string | null;
    csrfToken: string | null;
}

document.addEventListener('DOMContentLoaded', function(): void {
    initializeSmoothScrolling();
    initializeCardAnimations();
    initializeSessionTimeout();
});

function initializeSmoothScrolling(): void {
    document.querySelectorAll('.list-group-item').forEach(item => {
        item.addEventListener('click', function(this: HTMLElement, e: Event): void {
            const href = this.getAttribute('href');
            if (href && href.startsWith('#')) {
                e.preventDefault();
                const targetElement = document.querySelector(href);

                if (targetElement) {
                    targetElement.scrollIntoView({
                        behavior: 'smooth',
                        block: 'start'
                    });

                    document.querySelectorAll('.list-group-item').forEach(el => {
                        el.classList.remove('active');
                    });
                    this.classList.add('active');
                }
            }
        });
    });
}

function initializeCardAnimations(): void {
    const cards = document.querySelectorAll('.card');
    cards.forEach(card => {
        card.addEventListener('mouseenter', function(this: HTMLElement): void {
            this.style.transform = 'translateY(-5px)';
        });

        card.addEventListener('mouseleave', function(this: HTMLElement): void {
            this.style.transform = 'translateY(0)';
        });
    });
}

function initializeSessionTimeout(): void {
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

    let timeoutWarning: BrowserTimeout;
    let logoutTimer: BrowserTimeout;
    let sessionTimer: BrowserTimeout;
    let timeLeft = WARNING_TIME;

    function startTimers(): void {
        timeoutWarning = setTimeout(showTimeoutWarning, (SESSION_TIMEOUT - WARNING_TIME) * 1000);
        logoutTimer = setTimeout(logoutUser, SESSION_TIMEOUT * 1000);
        sessionTimer = setInterval(updateSessionTimer, 1000) as unknown as BrowserTimeout;
    }

    function showTimeoutWarning(): void {
        const modalElement = document.getElementById('sessionTimeoutModal');
        if (!modalElement) return;

        const modal = new (window as any).bootstrap.Modal(modalElement);
        modal.show();

        const countdown = setInterval(() => {
            timeLeft--;
            const timeLeftElement = document.getElementById('timeLeft');
            if (timeLeftElement) {
                const minutes = Math.floor(timeLeft / 60).toString().padStart(2, '0');
                const seconds = (timeLeft % 60).toString().padStart(2, '0');
                timeLeftElement.textContent = `${minutes}:${seconds}`;
            }

            const progress = (timeLeft / WARNING_TIME) * 100;
            const sessionProgress = document.getElementById('sessionProgress');
            if (sessionProgress) {
                sessionProgress.style.width = `${progress}%`;
            }

            if (timeLeft <= 0) {
                clearInterval(countdown);
                logoutUser();
            }
        }, 1000);

        const extendSessionBtn = document.getElementById('extendSessionBtn');
        if (extendSessionBtn) {
            extendSessionBtn.addEventListener('click', function(): void {
                clearInterval(countdown);
                modal.hide();
                extendSession();
            });
        }

        const logoutNowBtn = document.getElementById('logoutNowBtn');
        if (logoutNowBtn) {
            logoutNowBtn.addEventListener('click', function(): void {
                clearInterval(countdown);
                logoutUser();
            });
        }
    }

    function updateSessionTimer(): void {
        // Could implement a visible timer on page if needed
    }

    function logoutUser(): void {
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

    function extendSession(): void {
        clearTimeout(timeoutWarning);
        clearTimeout(logoutTimer);
        clearInterval(sessionTimer as unknown as number);

        if (sessionData.keepaliveUrl) {
            fetch(sessionData.keepaliveUrl, { method: 'HEAD' })
                .then(() => {
                    timeLeft = WARNING_TIME;
                    startTimers();
                })
                .catch(() => {
                    timeLeft = WARNING_TIME;
                    startTimers();
                });
        } else {
            timeLeft = WARNING_TIME;
            startTimers();
        }
    }

    startTimers();

    document.addEventListener('mousemove', resetTimers);
    document.addEventListener('keypress', resetTimers);

    function resetTimers(): void {
        clearTimeout(timeoutWarning);
        clearTimeout(logoutTimer);
        clearInterval(sessionTimer as unknown as number);
        startTimers();
    }
}

document.addEventListener('DOMContentLoaded', function(): void {
    const profileImage = document.getElementById('profile-image') as HTMLImageElement;
    if (profileImage) {
        profileImage.addEventListener('error', function(): void {
            this.src = '/static/images/default-profile.png';
        });
    }
});