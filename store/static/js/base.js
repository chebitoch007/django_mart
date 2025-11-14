// Enhanced Responsive JavaScript for Base Template - FIXED MOBILE CURRENCY

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
    this.menuClose = document.getElementById('mobile-menu-close-btn');
    this.lastScrollTop = 0;
    this.scrollThreshold = 100;
    this.isMenuOpen = false;

    this.init();
  }

  init() {
    this.bindEvents();
    this.handleResize();
    this.setupFocusTrap();
  }

  bindEvents() {
    // Mobile menu toggle
    if (this.menuToggle) {
      this.menuToggle.addEventListener('click', (e) => {
        e.preventDefault();
        e.stopPropagation();
        this.toggleMobileMenu();
      });
    }

    // Mobile menu close button
    if (this.menuClose) {
      this.menuClose.addEventListener('click', (e) => {
        e.preventDefault();
        e.stopPropagation();
        this.closeMobileMenu();
      });
    }

    // Close menu on outside click
    document.addEventListener('click', (e) => {
      if (this.isMenuOpen &&
          this.mobileMenu &&
          !this.mobileMenu.contains(e.target) &&
          !this.menuToggle?.contains(e.target)) {
        this.closeMobileMenu();
      }
    });

    // Close menu on escape key
    document.addEventListener('keydown', (e) => {
      if (e.key === 'Escape' && this.isMenuOpen) {
        this.closeMobileMenu();
        this.menuToggle?.focus();
      }
    });

    // Responsive scroll behavior with RAF
    let ticking = false;
    window.addEventListener('scroll', () => {
      if (!ticking) {
        window.requestAnimationFrame(() => {
          this.handleScroll();
          ticking = false;
        });
        ticking = true;
      }
    }, { passive: true });

    // Handle window resize with debounce
    let resizeTimer;
    window.addEventListener('resize', () => {
      clearTimeout(resizeTimer);
      resizeTimer = setTimeout(() => this.handleResize(), 250);
    }, { passive: true });

    // Handle orientation change
    window.addEventListener('orientationchange', () => {
      setTimeout(() => this.handleResize(), 300);
    });
  }

  toggleMobileMenu() {
    if (!this.mobileMenu) return;

    if (this.isMenuOpen) {
      this.closeMobileMenu();
    } else {
      this.openMobileMenu();
    }
  }

  openMobileMenu() {
    if (!this.mobileMenu) return;

    // Calculate and set the top position
    const navHeight = this.nav.offsetHeight;
    this.mobileMenu.style.top = `${navHeight}px`;

    // Open menu
    this.mobileMenu.classList.add('active');
    this.isMenuOpen = true;

    // Update ARIA attributes
    this.menuToggle?.setAttribute('aria-expanded', 'true');
    this.mobileMenu.setAttribute('aria-hidden', 'false');

    // Prevent body scroll
    document.body.classList.add('mobile-menu-open');
    document.body.style.overflow = 'hidden';

    // Focus management
    const firstFocusable = this.mobileMenu.querySelector('a, button');
    if (firstFocusable) {
      setTimeout(() => firstFocusable.focus(), 100);
    }

    // Announce to screen readers
    this.announceToScreenReader('Menu opened');
  }

  closeMobileMenu() {
    if (!this.mobileMenu) return;

    this.mobileMenu.classList.remove('active');
    this.isMenuOpen = false;

    // Update ARIA attributes
    this.menuToggle?.setAttribute('aria-expanded', 'false');
    this.mobileMenu.setAttribute('aria-hidden', 'true');

    // Restore body scroll
    document.body.classList.remove('mobile-menu-open');
    document.body.style.overflow = '';

    // Announce to screen readers
    this.announceToScreenReader('Menu closed');
  }

  handleScroll() {
    const scrollTop = window.pageYOffset || document.documentElement.scrollTop;

    // Add scrolled class for styling
    if (scrollTop > 50) {
      this.nav?.classList.add('scrolled');
    } else {
      this.nav?.classList.remove('scrolled');
    }

    // Hide/show nav on mobile when scrolling (only if menu is closed)
    if (DeviceDetector.isMobile() && !this.isMenuOpen) {
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
    if (DeviceDetector.isDesktop() && this.isMenuOpen) {
      this.closeMobileMenu();
    }

    // Recalculate menu top if it's open and window resizes
    if (this.isMenuOpen && this.mobileMenu) {
      const navHeight = this.nav.offsetHeight;
      this.mobileMenu.style.top = `${navHeight}px`;
    }

    // Update body class for CSS targeting
    document.body.className = document.body.className.replace(/breakpoint-\w+/g, '');
    document.body.classList.add(`breakpoint-${DeviceDetector.getBreakpoint()}`);
  }

  setupFocusTrap() {
    if (!this.mobileMenu) return;

    // Get all focusable elements
    const focusableElements = 'a[href], button:not([disabled]), [tabindex]:not([tabindex="-1"])';

    this.mobileMenu.addEventListener('keydown', (e) => {
      if (!this.isMenuOpen || e.key !== 'Tab') return;

      const focusableContent = this.mobileMenu.querySelectorAll(focusableElements);
      const firstFocusable = focusableContent[0];
      const lastFocusable = focusableContent[focusableContent.length - 1];

      if (e.shiftKey) {
        // Shift + Tab
        if (document.activeElement === firstFocusable) {
          e.preventDefault();
          lastFocusable.focus();
        }
      } else {
        // Tab
        if (document.activeElement === lastFocusable) {
          e.preventDefault();
          firstFocusable.focus();
        }
      }
    });
  }

  announceToScreenReader(message) {
    const announcement = document.createElement('div');
    announcement.setAttribute('role', 'status');
    announcement.setAttribute('aria-live', 'polite');
    announcement.className = 'sr-only';
    announcement.textContent = message;
    document.body.appendChild(announcement);

    setTimeout(() => {
      document.body.removeChild(announcement);
    }, 1000);
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

  // Cart update notifications are handled by base.ts CartManager
  // Cross-tab synchronization only
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
    this.originalQuery = '';

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

    // Store original query on input
    this.searchInput.addEventListener('input', () => {
      this.originalQuery = this.searchInput.value;
      this.selectedIndex = -1;
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
        this.searchInput.value = this.originalQuery;
        this.hideSuggestions();
        break;
    }
  }

  updateSelection(items) {
    items.forEach((item, index) => {
      if (index === this.selectedIndex) {
        item.classList.add('highlighted');
        item.scrollIntoView({ block: 'nearest', behavior: 'smooth' });

        // Update input with selected suggestion
        const selectedText = item.textContent.trim();
        this.searchInput.value = selectedText;
      } else {
        item.classList.remove('highlighted');
      }
    });

    // Restore original query if no selection
    if (this.selectedIndex === -1) {
      this.searchInput.value = this.originalQuery;
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
    }, { passive: true });

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
    notification.style.bottom = '80px';
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
          if (perfData) {
            console.log('Performance Metrics:', {
              domContentLoaded: Math.round(perfData.domContentLoadedEventEnd - perfData.domContentLoadedEventStart),
              loadComplete: Math.round(perfData.loadEventEnd - perfData.loadEventStart),
              totalTime: Math.round(perfData.loadEventEnd - perfData.fetchStart)
            });
          }
        }, 0);
      });
    }
  }

  static observeResourceTiming() {
    if ('PerformanceObserver' in window) {
      try {
        const observer = new PerformanceObserver((list) => {
          list.getEntries().forEach((entry) => {
            if (entry.duration > 1000) {
              console.warn('Slow resource:', entry.name, Math.round(entry.duration) + 'ms');
            }
          });
        });

        observer.observe({ entryTypes: ['resource'] });
      } catch (e) {
        console.warn('PerformanceObserver not supported:', e);
      }
    }
  }
}

// ===== ACCESSIBILITY ENHANCEMENTS =====
class AccessibilityEnhancer {
  static init() {
    this.setupFocusVisibility();
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

  static announceRouteChanges() {
    const announcer = document.createElement('div');
    announcer.setAttribute('role', 'status');
    announcer.setAttribute('aria-live', 'polite');
    announcer.setAttribute('aria-atomic', 'true');
    announcer.className = 'sr-only';
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

// ===== MOBILE CURRENCY SELECTOR - FIXED =====
function initMobileCurrencySelector() {
  const mobileCurrencyOptions = document.querySelectorAll('.mobile-currency-option');

  if (mobileCurrencyOptions.length === 0) return;

  console.log('✅ Initializing mobile currency selector...');

  // Get current currency from desktop selector or localStorage
  const currentCurrency = getCurrentCurrency();

  // Set active currency on page load
  mobileCurrencyOptions.forEach(option => {
    const currency = option.dataset.currency;
    if (currency === currentCurrency) {
      option.classList.add('active');
    } else {
      option.classList.remove('active');
    }
  });

  // Handle currency change
  mobileCurrencyOptions.forEach(option => {
    option.addEventListener('click', function() {
      const newCurrency = this.dataset.currency;
      console.log('💰 Mobile currency changed to:', newCurrency);

      // --- START: MODIFIED CODE ---

      // Get CSRF token from any form on the page (e.g., newsletter or review form)
      const csrfTokenInput = document.querySelector('form input[name="csrfmiddlewaretoken"]');

      if (!csrfTokenInput) {
          console.error('CSRF token not found. Cannot change currency.');
          // Use alert as showNotification might not be available
          alert('An error occurred. Could not find security token.');
          return;
      }

      const csrfToken = csrfTokenInput.value;

      // Update active state
      mobileCurrencyOptions.forEach(opt => opt.classList.remove('active'));
      this.classList.add('active');

      // Call the global, WORKING function from currency_selector.html
      // This function handles the POST request and the page reload.
      if (typeof handleCurrencyChange === 'function') {
        handleCurrencyChange(newCurrency, csrfToken);
      } else {
        console.error('handleCurrencyChange function not found.');
        alert('A critical error occurred. Please refresh the page.');
      }

      // --- END: MODIFIED CODE ---

      // REMOVED old broken logic:
      // changeCurrency(newCurrency);
      // showNotification(`Currency changed to ${newCurrency}`, 'success', 2000);
      // setTimeout(() => { window.location.reload(); }, 500);
    });
  });
}

function getCurrentCurrency() {
  // Try to get from desktop currency selector
  const desktopSelector = document.querySelector('.currency-selector select, #currencyToggle');
  if (desktopSelector) {
    // If it's a button (new currency selector), get from data attribute or text
    if (desktopSelector.tagName === 'BUTTON') {
      const currencyText = desktopSelector.querySelector('.currency-code')?.textContent;
      if (currencyText) return currencyText.trim();
    }
    // If it's a select element
    else if (desktopSelector.tagName === 'SELECT') {
      return desktopSelector.value;
    }
  }

  // Try localStorage
  try {
    return localStorage.getItem('selectedCurrency') || 'KES';
  } catch (e) {
    return 'KES';
  }
}

function changeCurrency(currency) {
  console.log('🔄 Changing currency to:', currency);

  // Update desktop currency selector if it exists
  const desktopSelector = document.querySelector('.currency-selector select');
  if (desktopSelector && desktopSelector.tagName === 'SELECT') {
    desktopSelector.value = currency;
    // Trigger change event to update prices
    const event = new Event('change', { bubbles: true });
    desktopSelector.dispatchEvent(event);
  }

  // Store in localStorage
  try {
    localStorage.setItem('selectedCurrency', currency);
    console.log('💾 Currency saved to localStorage:', currency);
  } catch (e) {
    console.warn('Could not save currency to localStorage:', e);
  }

  // Dispatch custom event for other components
  document.dispatchEvent(new CustomEvent('currency:changed', {
    detail: { currency }
  }));

  // ✅ Update the form that submits currency change to server
  const currencyForm = document.querySelector('form[action*="currency"]');
  if (currencyForm) {
    const currencyInput = currencyForm.querySelector('input[name="currency"]');
    if (currencyInput) {
      currencyInput.value = currency;
      // Submit the form to update session currency
      currencyForm.submit();
    }
  }
}

// ===== INITIALIZATION =====
document.addEventListener('DOMContentLoaded', () => {
  // Initialize all components
  new ResponsiveNav();
  new SearchEnhancer();
  new BackToTop();
  AccessibilityEnhancer.init();
  initMobileCurrencySelector();

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