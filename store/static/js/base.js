// Enhanced Responsive JavaScript for Base Template

// ===== VIEWPORT AND DEVICE DETECTION =====
const DeviceDetector = {
  isMobile: () => window.innerWidth <= 768,
  isTablet: () => window.innerWidth > 768 && window.innerWidth <= 1024,
  isDesktop: () => window.innerWidth > 1024,
  isTouchDevice: () => 'ontouchstart' in window || navigator.maxTouchPoints > 0,

  getBreakpoint: () => {
    const width = window.innerWidth;
    if (width <= 480) return 'xs';
    if (width <= 640) return 'sm';
    if (width <= 768) return 'md';
    if (width <= 1024) return 'lg';
    return 'xl';
  }
};

// ===== RESPONSIVE NAVIGATION =====
class ResponsiveNav {
  constructor() {
    this.nav = document.querySelector('.amazon-nav');
    this.mobileMenu = document.getElementById('mobile-menu');
    this.menuToggle = document.getElementById('mobile-menu-toggle');
    this.lastScrollTop = 0;
    this.scrollThreshold = 100;

    this.init();
  }

  init() {
    this.bindEvents();
    this.handleResize();
  }

  bindEvents() {
    // Mobile menu toggle
    if (this.menuToggle) {
      this.menuToggle.addEventListener('click', (e) => {
        e.stopPropagation();
        this.toggleMobileMenu();
      });
    }

    // Close menu on outside click
    document.addEventListener('click', (e) => {
      if (this.mobileMenu &&
          this.mobileMenu.classList.contains('active') &&
          !this.mobileMenu.contains(e.target) &&
          !this.menuToggle?.contains(e.target)) {
        this.closeMobileMenu();
      }
    });

    // Close menu on escape key
    document.addEventListener('keydown', (e) => {
      if (e.key === 'Escape' && this.mobileMenu?.classList.contains('active')) {
        this.closeMobileMenu();
        this.menuToggle?.focus();
      }
    });

    // Responsive scroll behavior
    let ticking = false;
    window.addEventListener('scroll', () => {
      if (!ticking) {
        window.requestAnimationFrame(() => {
          this.handleScroll();
          ticking = false;
        });
        ticking = true;
      }
    });

    // Handle window resize
    let resizeTimer;
    window.addEventListener('resize', () => {
      clearTimeout(resizeTimer);
      resizeTimer = setTimeout(() => this.handleResize(), 250);
    });
  }

  toggleMobileMenu() {
    if (!this.mobileMenu) return;

    const isActive = this.mobileMenu.classList.toggle('active');
    this.menuToggle?.setAttribute('aria-expanded', isActive.toString());
    this.mobileMenu.setAttribute('aria-hidden', (!isActive).toString());

    // Prevent body scroll when menu is open
    document.body.style.overflow = isActive ? 'hidden' : '';

    // Focus management
    if (isActive) {
      const firstLink = this.mobileMenu.querySelector('a');
      firstLink?.focus();
    }
  }

  closeMobileMenu() {
    if (!this.mobileMenu) return;

    this.mobileMenu.classList.remove('active');
    this.menuToggle?.setAttribute('aria-expanded', 'false');
    this.mobileMenu.setAttribute('aria-hidden', 'true');
    document.body.style.overflow = '';
  }

  handleScroll() {
    const scrollTop = window.pageYOffset || document.documentElement.scrollTop;

    // Add scrolled class for styling
    if (scrollTop > 50) {
      this.nav?.classList.add('scrolled');
    } else {
      this.nav?.classList.remove('scrolled');
    }

    // Hide/show nav on mobile when scrolling
    if (DeviceDetector.isMobile()) {
      if (scrollTop > this.lastScrollTop && scrollTop > this.scrollThreshold) {
        // Scrolling down
        this.nav?.classList.add('nav-hidden');
      } else {
        // Scrolling up
        this.nav?.classList.remove('nav-hidden');
      }
    }

    this.lastScrollTop = scrollTop <= 0 ? 0 : scrollTop;
  }

  handleResize() {
    // Close mobile menu on resize to desktop
    if (DeviceDetector.isDesktop() && this.mobileMenu?.classList.contains('active')) {
      this.closeMobileMenu();
    }

    // Update body class for CSS targeting
    document.body.className = document.body.className.replace(/breakpoint-\w+/, '');
    document.body.classList.add(`breakpoint-${DeviceDetector.getBreakpoint()}`);
  }
}

// ===== ENHANCED CART FUNCTIONALITY =====
document.addEventListener('DOMContentLoaded', function() {
  function updateCartCount(count) {
    const cartCountElements = document.querySelectorAll('.cart-count, #cart-count, #mobile-cart-count');

    cartCountElements.forEach(element => {
      if (element) {
        element.textContent = count;

        // Add pulse animation
        element.classList.add('pulse-animation');
        setTimeout(() => {
          element.classList.remove('pulse-animation');
        }, 600);
      }
    });

    // Store in localStorage for cross-tab sync
    try {
      localStorage.setItem('lastCartUpdate', Date.now().toString());
      localStorage.setItem('cartCount', count.toString());
    } catch (e) {
      console.warn('localStorage not available:', e);
    }
  }

  // Listen for cart update events
  document.body.addEventListener('cartUpdated', function(event) {
    if (event.detail?.cart_total_items !== undefined) {
      updateCartCount(event.detail.cart_total_items);
      showNotification('Item added to cart!', 'success');
    }
  });

  // Cross-tab synchronization
  window.addEventListener('storage', function(event) {
    if (event.key === 'cartCount' && event.newValue) {
      const count = parseInt(event.newValue, 10);
      if (!isNaN(count)) {
        updateCartCount(count);
      }
    }
  });
});

// ===== ENHANCED SEARCH FUNCTIONALITY =====
class SearchEnhancer {
  constructor() {
    this.searchBar = document.getElementById('search-bar');
    this.searchInput = this.searchBar?.querySelector('input[name="q"]');
    this.searchSuggestions = document.getElementById('search-suggestions');
    this.selectedIndex = -1;

    if (this.searchInput) {
      this.init();
    }
  }

  init() {
    this.bindEvents();
  }

  bindEvents() {
    // Show/hide suggestions
    this.searchInput.addEventListener('focus', () => {
      if (this.searchSuggestions?.children.length > 0) {
        this.searchSuggestions.style.display = 'block';
      }
    });

    // Close suggestions on click outside
    document.addEventListener('click', (e) => {
      if (!this.searchBar?.contains(e.target)) {
        this.hideSuggestions();
      }
    });

    // Keyboard navigation
    this.searchInput.addEventListener('keydown', (e) => {
      this.handleKeyboard(e);
    });

    // HTMX events
    document.body.addEventListener('htmx:afterSwap', (e) => {
      if (e.detail.target === this.searchSuggestions) {
        const items = this.searchSuggestions.querySelectorAll('.suggestion-item');
        if (items.length > 0) {
          this.searchSuggestions.style.display = 'block';
          this.selectedIndex = -1;
        } else {
          this.hideSuggestions();
        }
      }
    });
  }

  handleKeyboard(e) {
    const items = this.searchSuggestions?.querySelectorAll('.suggestion-item');
    if (!items || items.length === 0) return;

    switch(e.key) {
      case 'ArrowDown':
        e.preventDefault();
        this.selectedIndex = Math.min(this.selectedIndex + 1, items.length - 1);
        this.updateSelection(items);
        break;

      case 'ArrowUp':
        e.preventDefault();
        this.selectedIndex = Math.max(this.selectedIndex - 1, -1);
        this.updateSelection(items);
        break;

      case 'Enter':
        if (this.selectedIndex >= 0) {
          e.preventDefault();
          items[this.selectedIndex].click();
        }
        break;

      case 'Escape':
        this.hideSuggestions();
        break;
    }
  }

  updateSelection(items) {
    items.forEach((item, index) => {
      if (index === this.selectedIndex) {
        item.classList.add('highlighted');
        item.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
      } else {
        item.classList.remove('highlighted');
      }
    });

    // Update input value for preview
    if (this.selectedIndex >= 0) {
      const selectedText = items[this.selectedIndex].textContent.trim();
      this.searchInput.value = selectedText;
    }
  }

  hideSuggestions() {
    if (this.searchSuggestions) {
      this.searchSuggestions.style.display = 'none';
      this.selectedIndex = -1;
    }
  }
}

// ===== BACK TO TOP BUTTON =====
class BackToTop {
  constructor() {
    this.button = document.getElementById('back-to-top');
    this.threshold = 300;

    if (this.button) {
      this.init();
    }
  }

  init() {
    let ticking = false;
    window.addEventListener('scroll', () => {
      if (!ticking) {
        window.requestAnimationFrame(() => {
          this.handleScroll();
          ticking = false;
        });
        ticking = true;
      }
    });

    this.button.addEventListener('click', () => {
      this.scrollToTop();
    });
  }

  handleScroll() {
    const scrollTop = window.pageYOffset || document.documentElement.scrollTop;

    if (scrollTop > this.threshold) {
      this.button.classList.add('visible');
    } else {
      this.button.classList.remove('visible');
    }
  }

  scrollToTop() {
    window.scrollTo({
      top: 0,
      behavior: 'smooth'
    });
  }
}

// ===== NOTIFICATION SYSTEM =====
function showNotification(message, type = 'info', duration = 3000) {
  // Remove existing notifications
  document.querySelectorAll('.toast-notification').forEach(n => n.remove());

  const notification = document.createElement('div');
  notification.className = `toast-notification toast-${type}`;
  notification.setAttribute('role', 'alert');
  notification.setAttribute('aria-live', 'assertive');

  // Icon based on type
  const icons = {
    success: 'fa-check-circle',
    error: 'fa-exclamation-circle',
    warning: 'fa-exclamation-triangle',
    info: 'fa-info-circle'
  };

  notification.innerHTML = `
    <i class="fas ${icons[type] || icons.info}"></i>
    <span>${message}</span>
    <button class="toast-close" aria-label="Close notification">
      <i class="fas fa-times"></i>
    </button>
  `;

  document.body.appendChild(notification);

  // Position based on device
  if (DeviceDetector.isMobile()) {
    notification.style.bottom = '80px'; // Above mobile cart button
  }

  // Animate in
  requestAnimationFrame(() => {
    notification.classList.add('show');
  });

  // Close button
  const closeBtn = notification.querySelector('.toast-close');
  closeBtn.addEventListener('click', () => removeNotification(notification));

  // Auto-remove
  setTimeout(() => removeNotification(notification), duration);
}

function removeNotification(notification) {
  notification.classList.remove('show');
  notification.classList.add('hide');

  setTimeout(() => {
    notification.remove();
  }, 300);
}

// ===== NEWSLETTER FORM =====
document.addEventListener('DOMContentLoaded', function() {
  const newsletterForm = document.getElementById('newsletter-form');
  const feedbackDiv = document.getElementById('newsletter-feedback');

  if (newsletterForm && feedbackDiv) {
    newsletterForm.addEventListener('submit', function(e) {
      e.preventDefault();

      const formData = new FormData(this);
      const submitButton = this.querySelector('.newsletter-button');
      const originalText = submitButton.textContent;

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

// ===== LAZY LOADING PROTECTION FOR CRITICAL IMAGES =====
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

(function protectCriticalImages() {
  const protect = () => {
    document.querySelectorAll(EAGER_SELECTORS.join(', ')).forEach(img => {
      img.classList.remove('lazy');
      img.loading = 'eager';

      if (img.dataset.src && !img.src) {
        img.src = img.dataset.src;
        delete img.dataset.src;
      }

      img.style.opacity = '1';
      img.style.visibility = 'visible';
      img.classList.add('eager-loaded');
      img.setAttribute('data-no-lazy', 'true');
    });
  };

  protect();
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', protect);
  }
  setTimeout(protect, 100);
})();

// ===== PERFORMANCE MONITORING =====
class PerformanceMonitor {
  static logPageLoad() {
    if ('performance' in window) {
      window.addEventListener('load', () => {
        setTimeout(() => {
          const perfData = performance.getEntriesByType('navigation')[0];
          console.log('Performance Metrics:', {
            domContentLoaded: Math.round(perfData.domContentLoadedEventEnd - perfData.domContentLoadedEventStart),
            loadComplete: Math.round(perfData.loadEventEnd - perfData.loadEventStart),
            totalTime: Math.round(perfData.loadEventEnd - perfData.fetchStart)
          });
        }, 0);
      });
    }
  }

  static observeResourceTiming() {
    if ('PerformanceObserver' in window) {
      const observer = new PerformanceObserver((list) => {
        list.getEntries().forEach((entry) => {
          if (entry.duration > 1000) {
            console.warn('Slow resource:', entry.name, Math.round(entry.duration) + 'ms');
          }
        });
      });

      observer.observe({ entryTypes: ['resource'] });
    }
  }
}

// ===== ACCESSIBILITY ENHANCEMENTS =====
class AccessibilityEnhancer {
  static init() {
    this.setupFocusVisibility();
    this.setupSkipLinks();
    this.announceRouteChanges();
  }

  static setupFocusVisibility() {
    let isUsingKeyboard = false;

    document.addEventListener('keydown', (e) => {
      if (e.key === 'Tab') {
        isUsingKeyboard = true;
        document.body.classList.add('using-keyboard');
      }
    });

    document.addEventListener('mousedown', () => {
      isUsingKeyboard = false;
      document.body.classList.remove('using-keyboard');
    });
  }

  static setupSkipLinks() {
    const skipLink = document.createElement('a');
    skipLink.href = '#main-content';
    skipLink.className = 'skip-link';
    skipLink.textContent = 'Skip to main content';
    skipLink.style.cssText = `
      position: absolute;
      top: -40px;
      left: 0;
      background: var(--color-primary);
      color: white;
      padding: 8px 16px;
      text-decoration: none;
      z-index: 1000;
      transition: top 0.3s;
    `;

    skipLink.addEventListener('focus', () => {
      skipLink.style.top = '0';
    });

    skipLink.addEventListener('blur', () => {
      skipLink.style.top = '-40px';
    });

    document.body.insertBefore(skipLink, document.body.firstChild);
  }

  static announceRouteChanges() {
    const announcer = document.createElement('div');
    announcer.setAttribute('role', 'status');
    announcer.setAttribute('aria-live', 'polite');
    announcer.setAttribute('aria-atomic', 'true');
    announcer.className = 'sr-only';
    announcer.style.cssText = `
      position: absolute;
      width: 1px;
      height: 1px;
      padding: 0;
      margin: -1px;
      overflow: hidden;
      clip: rect(0, 0, 0, 0);
      white-space: nowrap;
      border: 0;
    `;
    document.body.appendChild(announcer);

    // Announce HTMX swaps
    document.body.addEventListener('htmx:afterSwap', (e) => {
      announcer.textContent = 'Content updated';
      setTimeout(() => {
        announcer.textContent = '';
      }, 1000);
    });
  }
}

// ===== INITIALIZATION =====
document.addEventListener('DOMContentLoaded', () => {
  // Initialize all components
  new ResponsiveNav();
  new SearchEnhancer();
  new BackToTop();
  AccessibilityEnhancer.init();

  // Enable performance monitoring in development
  if (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1') {
    PerformanceMonitor.logPageLoad();
    PerformanceMonitor.observeResourceTiming();
  }

  // Add device class to body
  document.body.classList.add(`device-${DeviceDetector.getBreakpoint()}`);
  document.body.classList.add(DeviceDetector.isTouchDevice() ? 'touch-device' : 'no-touch');

  console.log('🚀 Responsive base scripts initialized');
});

// ===== GLOBAL UTILITIES =====
window.toggleMobileMenu = function() {
  const event = new CustomEvent('toggleMobileMenu');
  document.dispatchEvent(event);
};

window.showNotification = showNotification;

// Export for module usage
if (typeof module !== 'undefined' && module.exports) {
  module.exports = {
    DeviceDetector,
    ResponsiveNav,
    SearchEnhancer,
    BackToTop,
    showNotification
  };
}