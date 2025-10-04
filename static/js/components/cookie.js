// Cookie Consent
const cookieConsent = {
    init() {
        if (!this.getConsent()) this.showBanner()
    },

    getConsent() {
        return localStorage.getItem('cookiesAccepted') === 'true'
    },

    showBanner() {
        const banner = document.getElementById('cookie-consent')
        banner.classList.remove('hidden')
    },

    accept() {
        localStorage.setItem('cookiesAccepted', 'true')
        document.getElementById('cookie-consent').classList.add('hidden')
    }
}

document.addEventListener('DOMContentLoaded', () => cookieConsent.init())