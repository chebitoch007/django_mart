// static/js/footer.js - Newsletter Form Handler ONLY
// This file should ONLY contain footer-related code

(function() {
    'use strict';

    console.log('🎨 Footer.js loading...');

    // ===== NEWSLETTER FORM HANDLER =====
    const NewsletterForm = {
        init() {
            const form = document.getElementById('newsletter-form');
            const feedbackDiv = document.getElementById('newsletter-feedback');

            if (!form) {
                console.warn('❌ Newsletter form not found');
                return;
            }

            if (!feedbackDiv) {
                console.warn('❌ Newsletter feedback div not found');
                return;
            }

            this.form = form;
            this.feedbackDiv = feedbackDiv;
            this.emailInput = form.querySelector('input[name="email"]');
            this.submitButton = form.querySelector('button[type="submit"]');

            if (!this.emailInput) {
                console.error('❌ Email input not found');
                return;
            }

            if (!this.submitButton) {
                console.error('❌ Submit button not found');
                return;
            }

            this.originalButtonText = this.submitButton.textContent;

            this.bindEvents();
            console.log('✅ Newsletter form initialized successfully');
            console.log('Form action:', this.form.action);
        },

        bindEvents() {
            this.form.addEventListener('submit', (e) => {
                console.log('📧 Form submitted');
                this.handleSubmit(e);
            });

            // Clear feedback on input
            this.emailInput.addEventListener('input', () => {
                this.clearFeedback();
            });

            // Email validation on blur
            this.emailInput.addEventListener('blur', () => {
                this.validateEmail();
            });
        },

        validateEmail() {
            const email = this.emailInput.value.trim();
            if (email && !this.isValidEmail(email)) {
                this.showFeedback('Please enter a valid email address', 'error');
                return false;
            }
            return true;
        },

        isValidEmail(email) {
            const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
            return emailRegex.test(email);
        },

        async handleSubmit(e) {
            e.preventDefault();

            const email = this.emailInput.value.trim();
            console.log('Processing email:', email);

            // Validation
            if (!email) {
                this.showFeedback('Please enter your email address', 'error');
                this.emailInput.focus();
                return;
            }

            if (!this.isValidEmail(email)) {
                this.showFeedback('Please enter a valid email address', 'error');
                this.emailInput.focus();
                return;
            }

            // Disable submit button and show loading state
            this.submitButton.disabled = true;
            this.submitButton.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Subscribing...';

            try {
                const formData = new FormData(this.form);

                console.log('Sending request to:', this.form.action);

                const response = await fetch(this.form.action, {
                    method: 'POST',
                    body: formData,
                    headers: {
                        'X-Requested-With': 'XMLHttpRequest',
                    }
                });

                console.log('Response status:', response.status);

                const data = await response.json();
                console.log('Response data:', data);

                if (data.success) {
                    this.showFeedback(data.message || 'Success! Please check your email to confirm.', 'success');
                    this.form.reset();
                    this.celebrateSubscription();
                } else {
                    this.showFeedback(data.message || 'Subscription failed. Please try again.', 'error');
                }

            } catch (error) {
                console.error('Newsletter subscription error:', error);
                this.showFeedback('An error occurred. Please try again later.', 'error');
            } finally {
                // Re-enable submit button
                this.submitButton.disabled = false;
                this.submitButton.textContent = this.originalButtonText;
            }
        },

        showFeedback(message, type) {
            console.log('Showing feedback:', type, message);
            this.feedbackDiv.textContent = message;
            this.feedbackDiv.className = `footer-newsletter-feedback ${type} show`;

            // Auto-hide success messages after 5 seconds
            if (type === 'success') {
                setTimeout(() => {
                    this.clearFeedback();
                }, 5000);
            }
        },

        clearFeedback() {
            this.feedbackDiv.classList.remove('show');
            setTimeout(() => {
                this.feedbackDiv.textContent = '';
                this.feedbackDiv.className = 'footer-newsletter-feedback';
            }, 300);
        },

        celebrateSubscription() {
            // Add celebration animation
            const container = this.form.parentElement;
            if (!container) return;

            container.style.transform = 'scale(1.02)';
            setTimeout(() => {
                container.style.transform = 'scale(1)';
            }, 200);

            this.createSparkles();
        },

        createSparkles() {
            const container = this.form.parentElement;
            if (!container) return;

            const sparkles = ['✨', '⭐', '🌟', '💫'];

            for (let i = 0; i < 5; i++) {
                const sparkle = document.createElement('div');
                sparkle.textContent = sparkles[Math.floor(Math.random() * sparkles.length)];
                sparkle.style.cssText = `
                    position: absolute;
                    font-size: 20px;
                    animation: sparkle-float 1s ease-out forwards;
                    pointer-events: none;
                    left: ${Math.random() * 100}%;
                    top: 50%;
                    z-index: 1000;
                `;
                container.style.position = 'relative';
                container.appendChild(sparkle);

                setTimeout(() => sparkle.remove(), 1000);
            }
        }
    };

    // ===== BACK TO TOP BUTTON (REMOVED) =====
    // This is now handled by base.js, which has the more robust class-based implementation.
    // const BackToTopButton = { ... };

    // Add CSS animations
    const addStyles = () => {
        if (document.getElementById('footer-styles')) return;

        const style = document.createElement('style');
        style.id = 'footer-styles';
        style.textContent = `
            @keyframes sparkle-float {
                0% {
                    transform: translateY(0) scale(0);
                    opacity: 1;
                }
                100% {
                    transform: translateY(-100px) scale(1);
                    opacity: 0;
                }
            }

            .footer-newsletter-feedback {
                margin-top: 15px;
                padding: 12px 20px;
                border-radius: 8px;
                font-size: 14px;
                transition: all 0.3s ease;
                transform: translateY(-10px);
                opacity: 0;
                display: block;
            }

            .footer-newsletter-feedback.show {
                transform: translateY(0);
                opacity: 1;
            }

            .footer-newsletter-feedback.success {
                background: #d1fae5;
                color: #065f46;
                border-left: 4px solid #10b981;
            }

            .footer-newsletter-feedback.error {
                background: #fee2e2;
                color: #991b1b;
                border-left: 4px solid #ef4444;
            }
        `;
        // Removed .back-to-top-btn styles as they are in footer.css and handled by base.js
        document.head.appendChild(style);
    };

    // ===== INITIALIZATION =====
    function initFooter() {
        console.log('🎨 Initializing footer...');
        addStyles();
        NewsletterForm.init();
        // BackToTopButton.init(); // Removed call
        console.log('✅ Footer enhancements loaded');
    }

    // Wait for DOM to be ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initFooter);
    } else {
        initFooter();
    }

})();