// Enhanced cart update functionality
document.addEventListener('DOMContentLoaded', function() {
    // Function to update cart count in multiple locations
    function updateCartCount(count) {
        const cartCountElements = ['cart-count', 'mobile-cart-count'];
        cartCountElements.forEach(elementId => {
            const element = document.getElementById(elementId);
            if (element) {
                element.textContent = count;
                // Add animation effect
                element.style.transform = 'scale(1.2)';
                setTimeout(() => {
                    element.style.transform = 'scale(1)';
                }, 200);
            }
        });
        localStorage.setItem('lastCartUpdate', new Date().getTime().toString());
    }

    // Enhanced cart update events
    document.body.addEventListener('cartUpdated', function(event) {
        if (event.detail && event.detail.cart_total_items !== undefined) {
            updateCartCount(event.detail.cart_total_items);

            // Show success notification
            showNotification('Item added to cart!', 'success');

            if (typeof localStorage !== 'undefined') {
                localStorage.setItem('cartUpdated', JSON.stringify({
                    cart_total_items: event.detail.cart_total_items,
                    timestamp: new Date().getTime()
                }));
            }
        }
    });

    // Cross-tab cart synchronization
    window.addEventListener('storage', function(event) {
        if (event.key === 'cartUpdated' && event.newValue) {
            try {
                const cartData = JSON.parse(event.newValue);
                if (cartData.cart_total_items !== undefined) {
                    updateCartCount(cartData.cart_total_items);
                }
            } catch (e) {
                console.error('Error parsing cart data:', e);
            }
        }
    });

    // Refresh cart data if recently updated
    if (typeof localStorage !== 'undefined') {
        const lastCartUpdate = localStorage.getItem('lastCartUpdate');
        const now = new Date().getTime();

        if (lastCartUpdate && (now - parseInt(lastCartUpdate)) < 300000) {
            htmx.ajax('GET', '{% url "cart:cart_total" %}', {
                target: '#cart-count',
                swap: 'innerHTML'
            });
        }
    }
});

// Enhanced back to top functionality
document.addEventListener('DOMContentLoaded', function() {
    const backToTopButton = document.getElementById('back-to-top');

    window.addEventListener('scroll', function() {
        if (window.pageYOffset > 300) {
            backToTopButton.classList.add('visible');
        } else {
            backToTopButton.classList.remove('visible');
        }
    });

    backToTopButton.addEventListener('click', function() {
        window.scrollTo({ top: 0, behavior: 'smooth' });
    });
});

// Enhanced mobile menu functionality
function toggleMobileMenu() {
    const mobileMenu = document.getElementById('mobile-menu');
    const menuToggle = document.getElementById('mobile-menu-toggle');

    if (mobileMenu && menuToggle) {
        const isActive = mobileMenu.classList.contains('active');

        mobileMenu.classList.toggle('active');
        mobileMenu.setAttribute('aria-hidden', isActive ? 'true' : 'false');
        menuToggle.setAttribute('aria-expanded', isActive ? 'false' : 'true');
    }
}

// Enhanced search category dropdown
document.addEventListener('DOMContentLoaded', function() {
    const categoryToggle = document.getElementById('categoryToggle');
    const categoryDropdown = document.getElementById('categoryDropdown');
    const categoryItems = document.querySelectorAll('.category-item, .category-header');
    const selectedCategoryText = document.getElementById('selectedCategoryText');
    const selectedCategoryInput = document.getElementById('selectedCategory');

    if (categoryToggle && categoryDropdown) {
        // Toggle dropdown with proper aria attributes
        categoryToggle.addEventListener('click', function(e) {
            e.stopPropagation();
            const isOpen = categoryDropdown.classList.contains('show');

            categoryDropdown.classList.toggle('show');
            categoryToggle.setAttribute('aria-expanded', isOpen ? 'false' : 'true');
        });

        // Close dropdown when clicking outside
        document.addEventListener('click', function(e) {
            if (!categoryToggle.contains(e.target) && !categoryDropdown.contains(e.target)) {
                categoryDropdown.classList.remove('show');
                categoryToggle.setAttribute('aria-expanded', 'false');
            }
        });

        // Handle category selection
        categoryItems.forEach(item => {
            item.addEventListener('click', function(e) {
                e.stopPropagation();
                const categorySlug = this.getAttribute('data-category-slug');

                if (categorySlug !== null && !this.classList.contains('category-header')) {
                    selectedCategoryInput.value = categorySlug;
                    selectedCategoryText.textContent = this.textContent.trim();
                    categoryDropdown.classList.remove('show');
                    categoryToggle.setAttribute('aria-expanded', 'false');
                }

                // Toggle subcategories for category headers
                if (this.classList.contains('category-header')) {
                    this.classList.toggle('active');
                    const isExpanded = this.classList.contains('active');
                    this.setAttribute('aria-expanded', isExpanded ? 'true' : 'false');
                }
            });

            // Keyboard navigation support
            item.addEventListener('keydown', function(e) {
                if (e.key === 'Enter' || e.key === ' ') {
                    e.preventDefault();
                    this.click();
                }
            });
        });
    }
});

// Newsletter form enhancement
document.addEventListener('DOMContentLoaded', function() {
    const newsletterForm = document.getElementById('newsletter-form');
    const feedbackDiv = document.getElementById('newsletter-feedback');

    if (newsletterForm && feedbackDiv) {
        newsletterForm.addEventListener('submit', function(e) {
            e.preventDefault();

            const formData = new FormData(this);
            const submitButton = this.querySelector('.newsletter-button');
            const originalText = submitButton.textContent;

            // Show loading state
            submitButton.textContent = 'Subscribing...';
            submitButton.disabled = true;

            fetch(this.action, {
                method: 'POST',
                body: formData,
                headers: {
                    'X-Requested-With': 'XMLHttpRequest',
                }
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    showFeedback('Thank you for subscribing!', 'success');
                    this.reset();
                } else {
                    showFeedback(data.message || 'Subscription failed. Please try again.', 'error');
                }
            })
            .catch(error => {
                showFeedback('An error occurred. Please try again later.', 'error');
            })
            .finally(() => {
                submitButton.textContent = originalText;
                submitButton.disabled = false;
            });
        });
    }

    function showFeedback(message, type) {
        feedbackDiv.textContent = message;
        feedbackDiv.className = `newsletter-feedback ${type} show`;

        setTimeout(() => {
            feedbackDiv.classList.remove('show');
        }, 5000);
    }
});

// Enhanced notification system
function showNotification(message, type = 'info', duration = 3000) {
    const notification = document.createElement('div');
    notification.className = `fixed top-4 right-4 z-50 px-6 py-3 rounded-lg shadow-lg text-white font-medium transform translate-x-full transition-transform duration-300`;

    switch(type) {
        case 'success':
            notification.classList.add('bg-green-500');
            break;
        case 'error':
            notification.classList.add('bg-red-500');
            break;
        case 'warning':
            notification.classList.add('bg-yellow-500');
            break;
        default:
            notification.classList.add('bg-blue-500');
    }

    notification.textContent = message;
    document.body.appendChild(notification);

    // Animate in
    setTimeout(() => {
        notification.classList.remove('translate-x-full');
    }, 100);

    // Animate out and remove
    setTimeout(() => {
        notification.classList.add('translate-x-full');
        setTimeout(() => {
            document.body.removeChild(notification);
        }, 300);
    }, duration);
}

// Enhanced scroll animations
const observerOptions = {
    threshold: 0.1,
    rootMargin: '0px 0px -50px 0px'
};

const observer = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
        if (entry.isIntersecting) {
            entry.target.classList.add('fadeInUp');
            observer.unobserve(entry.target);
        }
    });
}, observerOptions);

// Observe elements for animation
document.addEventListener('DOMContentLoaded', function() {
    const animateElements = document.querySelectorAll('.hero-content, .product-card, .footer-column');
    animateElements.forEach(el => observer.observe(el));
});

// Enhanced accessibility - focus management
document.addEventListener('keydown', function(e) {
    // Escape key closes dropdowns
    if (e.key === 'Escape') {
        const openDropdowns = document.querySelectorAll('.show');
        openDropdowns.forEach(dropdown => {
            dropdown.classList.remove('show');
            const trigger = document.querySelector(`[aria-controls="${dropdown.id}"]`);
            if (trigger) {
                trigger.setAttribute('aria-expanded', 'false');
                trigger.focus();
            }
        });

        // Close mobile menu
        const mobileMenu = document.getElementById('mobile-menu');
        const menuToggle = document.getElementById('mobile-menu-toggle');
        if (mobileMenu && mobileMenu.classList.contains('active')) {
            mobileMenu.classList.remove('active');
            mobileMenu.setAttribute('aria-hidden', 'true');
            menuToggle.setAttribute('aria-expanded', 'false');
        }
    }
});

// Performance: Lazy load images
if ('IntersectionObserver' in window) {
    const imageObserver = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                const img = entry.target;
                img.src = img.dataset.src;
                img.classList.remove('lazy');
                imageObserver.unobserve(img);
            }
        });
    });

    document.querySelectorAll('img[data-src]').forEach(img => {
        imageObserver.observe(img);
    });
}