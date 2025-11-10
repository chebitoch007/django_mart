// =======================================
// UNIFIED FILTER SIDEBAR FUNCTIONALITY
// Works across all pages: product-list, search, categories
// =======================================

class FilterSidebar {
  constructor() {
    this.filterToggle = document.getElementById('filterToggle');
    this.filterContent = document.getElementById('filterContent');
    this.filterSidebar = document.querySelector('.filter-sidebar');
    this.filterCloseBtn = document.querySelector('.filter-close-btn');
    this.MOBILE_BREAKPOINT = 992;
    this.isInitialized = false;

    if (this.filterToggle && this.filterContent) {
      this.init();
    } else {
      console.warn('⚠️ Filter toggle or content not found');
    }
  }

  init() {
    if (this.isInitialized) return;
    this.isInitialized = true;

    console.log('🎯 Filter sidebar initialized');

    // Set initial state based on screen size
    this.updateSidebarVisibility();

    // Bind events
    this.bindEvents();
  }

  bindEvents() {
    // Toggle button click
    this.filterToggle.addEventListener('click', (e) => {
      e.preventDefault();
      this.toggleFilters();
    });

    // Close button click (if exists)
    if (this.filterCloseBtn) {
      this.filterCloseBtn.addEventListener('click', (e) => {
        e.preventDefault();
        this.closeFilters();
      });
    }

    // Close filters when clicking outside on mobile
    document.addEventListener('click', (e) => {
      if (this.isMobile() && this.isFiltersOpen()) {
        const isClickInsideFilters = this.filterContent.contains(e.target);
        const isClickOnToggle = this.filterToggle.contains(e.target);

        if (!isClickInsideFilters && !isClickOnToggle) {
          this.closeFilters();
        }
      }
    });

    // Close filters with Escape key
    document.addEventListener('keydown', (e) => {
      if (e.key === 'Escape' && this.isFiltersOpen() && this.isMobile()) {
        this.closeFilters();
        this.filterToggle.focus();
      }
    });

    // Handle window resize
    let resizeTimer;
    window.addEventListener('resize', () => {
      clearTimeout(resizeTimer);
      resizeTimer = setTimeout(() => {
        this.updateSidebarVisibility();
      }, 150);
    });
  }

  isMobile() {
    return window.innerWidth < this.MOBILE_BREAKPOINT;
  }

  isFiltersOpen() {
    return !this.filterContent.hasAttribute('hidden');
  }

  toggleFilters() {
    if (this.isFiltersOpen()) {
      this.closeFilters();
    } else {
      this.openFilters();
    }
  }

  openFilters() {
    // Remove hidden attribute
    this.filterContent.removeAttribute('hidden');

    // Add slide-in animation class
    this.filterContent.classList.add('slide-in');

    // Update aria-expanded
    this.filterToggle.setAttribute('aria-expanded', 'true');

    // Update button text
    const buttonText = this.filterToggle.querySelector('span');
    if (buttonText) {
      buttonText.textContent = 'Hide Filters';
    }

    // Prevent body scroll on mobile
    if (this.isMobile()) {
      document.body.classList.add('no-scroll');
    }

    console.log('✅ Filters opened');
  }

  closeFilters() {
    // Remove slide-in class
    this.filterContent.classList.remove('slide-in');

    // Add hidden attribute after animation
    setTimeout(() => {
      this.filterContent.setAttribute('hidden', '');
    }, 300);

    // Update aria-expanded
    this.filterToggle.setAttribute('aria-expanded', 'false');

    // Update button text
    const buttonText = this.filterToggle.querySelector('span');
    if (buttonText) {
      buttonText.textContent = 'Show Filters';
    }

    // Allow body scroll
    document.body.classList.remove('no-scroll');

    console.log('❌ Filters closed');
  }

  updateSidebarVisibility() {
    if (this.isMobile()) {
      // Mobile: Hide filters by default, show toggle
      if (!this.filterContent.hasAttribute('hidden') &&
          this.filterToggle.getAttribute('aria-expanded') !== 'true') {
        this.filterContent.setAttribute('hidden', '');
      }
      this.filterToggle.style.display = 'flex';

      console.log('📱 Mobile view: Toggle visible, filters collapsed');
    } else {
      // Desktop: Always show filters, hide toggle
      this.filterContent.removeAttribute('hidden');
      this.filterContent.classList.remove('slide-in');
      this.filterToggle.style.display = 'none';
      document.body.classList.remove('no-scroll');

      console.log('💻 Desktop view: Filters always visible');
    }
  }
}

// =======================================
// PRICE FILTER ENHANCEMENT
// =======================================
class PriceFilter {
  constructor() {
    this.priceRange = document.getElementById('priceRange');
    this.priceDisplay = document.getElementById('priceDisplay');
    this.maxPriceInput = document.getElementById('maxPriceInput');
    this.minPriceInput = document.getElementById('minPriceInput');

    if (this.priceRange && this.priceDisplay) {
      this.init();
    }
  }

  init() {
    // Real-time display update
    this.priceRange.addEventListener('input', () => {
      this.updateDisplay();
    });

    // Sync input fields if they exist
    if (this.maxPriceInput) {
      this.maxPriceInput.addEventListener('input', () => {
        const value = parseInt(this.maxPriceInput.value) || 0;
        this.priceRange.value = value.toString();
        this.updateDisplay();
      });
    }

    if (this.minPriceInput) {
      this.minPriceInput.addEventListener('input', () => {
        console.log('Min price:', this.minPriceInput.value);
      });
    }

    // Initialize display
    this.updateDisplay();
  }

  updateDisplay() {
    const value = parseInt(this.priceRange.value);
    this.priceDisplay.textContent = `${value.toLocaleString()} KES`;

    // Update input if it exists
    if (this.maxPriceInput) {
      this.maxPriceInput.value = value.toString();
    }
  }
}

// =======================================
// FILTER ANIMATIONS
// =======================================
class FilterAnimations {
  static animateFilterChange(element) {
    if (!element) return;

    element.style.transform = 'scale(0.95)';
    setTimeout(() => {
      element.style.transform = 'scale(1)';
    }, 150);
  }

  static highlightActiveFilter(filterElement) {
    filterElement.classList.add('active');

    // Add pulse animation
    filterElement.style.animation = 'pulse 0.6s ease';
    setTimeout(() => {
      filterElement.style.animation = '';
    }, 600);
  }
}

// =======================================
// INITIALIZE ON PAGE LOAD
// =======================================
function initFilterSidebar() {
  // Initialize filter sidebar
  new FilterSidebar();

  // Initialize price filter
  new PriceFilter();

  // Add smooth scroll for filter clicks
  document.querySelectorAll('.sort-option, .brand-item, .supplier-item, .rating-option').forEach(link => {
    link.addEventListener('click', function() {
      FilterAnimations.animateFilterChange(this);
    });
  });

  console.log('✅ All filter components initialized');

  // Removed redundant initFilterCloseButton() function.
  // The FilterSidebar class already handles all close functionality.
}

// =======================================
// ADD PULSE ANIMATION FOR ACTIVE FILTERS
// =======================================
const style = document.createElement('style');
style.textContent = `
  @keyframes pulse {
    0% { transform: scale(1); }
    50% { transform: scale(1.05); }
    100% { transform: scale(1); }
  }

  /* Smooth transitions for all filter elements */
  .sort-option,
  .brand-item,
  .supplier-item,
  .rating-option {
    transition: all 0.3s cubic-bezier(0.25, 0.8, 0.25, 1);
  }
`;
document.head.appendChild(style);

// Auto-initialize when DOM is ready
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', initFilterSidebar);
} else {
  initFilterSidebar();
}

// Re-initialize after HTMX swaps (REMOVED)
// This is now handled by the main.ts (Vite) entrypoint, which correctly
// calls page-specific initializers (like initProductList) after a swap.
// The filter sidebar itself is persistent and does not need re-initialization.

// Export for use in other modules if needed
if (typeof module !== 'undefined' && module.exports) {
  module.exports = { FilterSidebar, PriceFilter, FilterAnimations };
}

// Add to window for global access
window.FilterSidebar = FilterSidebar;
window.PriceFilter = PriceFilter;
window.initFilterSidebar = initFilterSidebar;