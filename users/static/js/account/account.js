document.addEventListener('DOMContentLoaded', function () {
    initializeSmoothScrolling();
    initializeCardAnimations();
    initializeSessionTimeout();
});
function initializeSmoothScrolling() {
    document.querySelectorAll('.list-group-item').forEach(item => {
        item.addEventListener('click', function (e) {
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
function initializeCardAnimations() {
    const cards = document.querySelectorAll('.card');
    cards.forEach(card => {
        card.addEventListener('mouseenter', function () {
            this.style.transform = 'translateY(-5px)';
        });
        card.addEventListener('mouseleave', function () {
            this.style.transform = 'translateY(0)';
        });
    });
}
function initializeSessionTimeout() {
    const sessionTimeoutModal = document.getElementById('sessionTimeoutModal');
    if (!sessionTimeoutModal)
        return;
    const sessionData = {
        sessionTimeout: document.body.getAttribute('data-session-timeout'),
        logoutUrl: document.body.getAttribute('data-logout-url'),
        keepaliveUrl: document.body.getAttribute('data-keepalive-url'),
        csrfToken: document.body.getAttribute('data-csrf-token')
    };
    if (!sessionData.sessionTimeout || !sessionData.logoutUrl)
        return;
    const SESSION_TIMEOUT = parseInt(sessionData.sessionTimeout);
    const WARNING_TIME = 120;
    let timeoutWarning;
    let logoutTimer;
    let sessionTimer;
    let timeLeft = WARNING_TIME;
    function startTimers() {
        timeoutWarning = setTimeout(showTimeoutWarning, (SESSION_TIMEOUT - WARNING_TIME) * 1000);
        logoutTimer = setTimeout(logoutUser, SESSION_TIMEOUT * 1000);
        sessionTimer = setInterval(updateSessionTimer, 1000);
    }
    function showTimeoutWarning() {
        const modalElement = document.getElementById('sessionTimeoutModal');
        if (!modalElement)
            return;
        const modal = new window.bootstrap.Modal(modalElement);
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
            extendSessionBtn.addEventListener('click', function () {
                clearInterval(countdown);
                modal.hide();
                extendSession();
            });
        }
        const logoutNowBtn = document.getElementById('logoutNowBtn');
        if (logoutNowBtn) {
            logoutNowBtn.addEventListener('click', function () {
                clearInterval(countdown);
                logoutUser();
            });
        }
    }
    function updateSessionTimer() {
    }
    function logoutUser() {
        if (!sessionData.logoutUrl || !sessionData.csrfToken)
            return;
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
    function extendSession() {
        clearTimeout(timeoutWarning);
        clearTimeout(logoutTimer);
        clearInterval(sessionTimer);
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
        }
        else {
            timeLeft = WARNING_TIME;
            startTimers();
        }
    }
    startTimers();
    document.addEventListener('mousemove', resetTimers);
    document.addEventListener('keypress', resetTimers);
    function resetTimers() {
        clearTimeout(timeoutWarning);
        clearTimeout(logoutTimer);
        clearInterval(sessionTimer);
        startTimers();
    }
}
document.addEventListener('DOMContentLoaded', function () {
    const profileImage = document.getElementById('profile-image');
    if (profileImage) {
        profileImage.addEventListener('error', function () {
            this.src = '/static/images/default-profile.png';
        });
    }
});
export {};
//# sourceMappingURL=account.js.map