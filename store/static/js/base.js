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
            if (typeof htmx !== 'undefined') {
                htmx.ajax('GET', '/cart/total/', {
                    target: '#cart-count',
                    swap: 'innerHTML'
                });
            }
        }
    }
});

// Enhanced back to top functionality
document.addEventListener('DOMContentLoaded', function() {
    const backToTopButton = document.getElementById('back-to-top');

    if (backToTopButton) {
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
    }
});

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

// [ --- UPDATED LAZY LOADING LOGIC --- ]

// Selectors for images that should NEVER be lazy-loaded
const EAGER_SELECTORS = [
    '.product-image',
    '.cart-item img',
    '.order-item img',
    '.product-cell img',
    '.items-table img',
    '.order-detail-container img',
    'img[data-no-lazy]',
    'img.eager-loaded'
];
const EAGER_SELECTOR_STRING = EAGER_SELECTORS.join(', ');

// 1. Run protective code FIRST - IMMEDIATELY upon script load
(function() {
    const protectCriticalImages = () => {
        try {
            document.querySelectorAll(EAGER_SELECTOR_STRING).forEach(img => {
                // Remove lazy class
                if (img.classList.contains('lazy')) {
                    console.log('Protecting critical image from lazy-loader:', img);
                    img.classList.remove('lazy');
                }

                // Force eager loading
                img.loading = 'eager';

                // If data-src exists, move it to src immediately
                if (img.dataset.src && !img.src) {
                    img.src = img.dataset.src;
                    delete img.dataset.src; // Remove to prevent re-processing
                    console.log('Restored hijacked image src:', img.src);
                }

                // Ensure visibility
                img.style.opacity = '1';
                img.style.visibility = 'visible';
                img.style.display = 'block';

                // Mark as protected
                img.classList.add('eager-loaded');
                img.setAttribute('data-no-lazy', 'true');
            });
        } catch (e) {
            console.error('Error in eager-loading protective script:', e);
        }
    };

    // Run immediately
    protectCriticalImages();

    // Run on DOMContentLoaded
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', protectCriticalImages);
    }

    // Run after a short delay to catch any late-loading elements
    setTimeout(protectCriticalImages, 100);
    setTimeout(protectCriticalImages, 500);
})();

// 2. Setup IntersectionObserver for actual lazy loading (only for non-critical images)
if ('IntersectionObserver' in window) {
    const imageObserver = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                const img = entry.target;

                // Double-check this isn't a critical image
                if (img.hasAttribute('data-no-lazy') || img.classList.contains('eager-loaded')) {
                    imageObserver.unobserve(img);
                    return;
                }

                // Process only if it has data-src and hasn't been loaded
                if (img.dataset.src && !img.classList.contains('loaded')) {
                    img.src = img.dataset.src;
                    img.classList.remove('lazy');
                    img.classList.add('loaded');
                    console.log('Lazy-loaded image:', img);
                }
                imageObserver.unobserve(img);
            }
        });
    });

    // 3. Observe ONLY images that are .lazy[data-src] AND are NOT critical images
    const setupLazyLoading = () => {
        try {
            // Build a selector that excludes all critical images
            const notSelector = EAGER_SELECTORS.map(sel => `:not(${sel})`).join('');
            const lazySelector = `img.lazy[data-src]${notSelector}`;

            const imagesToObserve = document.querySelectorAll(lazySelector);
            console.log(`Found ${imagesToObserve.length} images to lazy-load (excluding critical images).`);

            imagesToObserve.forEach(img => {
                // Skip if marked as critical
                if (img.hasAttribute('data-no-lazy') || img.classList.contains('eager-loaded')) {
                    return;
                }
                imageObserver.observe(img);
            });
        } catch (e) {
            console.error('Error in lazy-loading observer setup:', e);
        }
    };

    // Setup lazy loading after DOM is ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', setupLazyLoading);
    } else {
        setupLazyLoading();
    }
}

// 4. Watch for dynamically added images
const imageProtectionObserver = new MutationObserver((mutations) => {
    mutations.forEach((mutation) => {
        mutation.addedNodes.forEach((node) => {
            if (node.nodeType === 1) { // Element node
                const element = node;

                // Check if the node itself is a critical image
                if (element.matches && element.matches(EAGER_SELECTOR_STRING)) {
                    const img = element;
                    img.classList.remove('lazy');
                    img.loading = 'eager';
                    if (img.dataset.src) {
                        img.src = img.dataset.src;
                        delete img.dataset.src;
                    }
                    img.classList.add('eager-loaded');
                    img.setAttribute('data-no-lazy', 'true');
                }

                // Check for critical images within the node
                if (element.querySelectorAll) {
                    const criticalImages = element.querySelectorAll(EAGER_SELECTOR_STRING);
                    criticalImages.forEach(img => {
                        img.classList.remove('lazy');
                        img.loading = 'eager';
                        if (img.dataset.src) {
                            img.src = img.dataset.src;
                            delete img.dataset.src;
                        }
                        img.classList.add('eager-loaded');
                        img.setAttribute('data-no-lazy', 'true');
                    });
                }
            }
        });
    });
});

// Start observing
if (document.body) {
    imageProtectionObserver.observe(document.body, {
        childList: true,
        subtree: true
    });
}
// Responsive Navigation Toggle
function toggleMobileMenu() {
    const menu = document.getElementById('mobile-menu');
    const toggle = document.getElementById('mobile-menu-toggle');

    if (!menu || !toggle) return;

    const isActive = menu.classList.toggle('active');
    toggle.setAttribute('aria-expanded', isActive);
    menu.setAttribute('aria-hidden', !isActive);
}

// Close mobile menu when clicking outside
document.addEventListener('click', (e) => {
    const menu = document.getElementById('mobile-menu');
    const toggle = document.getElementById('mobile-menu-toggle');

    if (menu && toggle && !menu.contains(e.target) && !toggle.contains(e.target)) {
        menu.classList.remove('active');
        toggle.setAttribute('aria-expanded', 'false');
    }
});