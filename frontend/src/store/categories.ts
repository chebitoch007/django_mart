/**
 * categories.ts
 * * Initializes UI enhancements for the categories page that HTMX doesn't handle,
 * such as the mobile filter toggle and the price range slider's text display.
 */

export function initCategories(): void {
  console.log('Initializing categories page enhancements...');

  // This function wires up the mobile filter toggle and price slider display.
  // It's safe to call multiple times (e.g., after HTMX swaps) as it
  // checks for element existence.
  initFilterSidebarEnhancements();
}

/**
 * Wires up client-side-only enhancements for the filter sidebar.
 * - Mobile Toggle: Opens/closes the filter sidebar on mobile.
 * - Price Slider: Updates the price text display as the slider moves.
 */
function initFilterSidebarEnhancements(): void {

  // --- 1. Mobile Filter Toggle Logic ---
  const filterToggleBtn = document.getElementById('filterToggle');
  const filterSidebar = document.getElementById('filterSidebar');
  const filterCloseBtn = filterSidebar?.querySelector('.filter-close-btn');

  if (filterToggleBtn && filterSidebar && filterCloseBtn) {
    const openFilters = () => {
      filterSidebar.classList.add('is-open');
      filterToggleBtn.setAttribute('aria-expanded', 'true');
    };

    const closeFilters = () => {
      filterSidebar.classList.remove('is-open');
      filterToggleBtn.setAttribute('aria-expanded', 'false');
    };

    // Use a simple click toggle, ensuring we don't add multiple listeners
    if (!(filterToggleBtn as any)._filterToggleAdded) {
      filterToggleBtn.addEventListener('click', openFilters);
      filterCloseBtn.addEventListener('click', closeFilters);
      (filterToggleBtn as any)._filterToggleAdded = true;
    }
  }

  // --- 2. Price Range Slider Display Logic ---
  const priceRange = document.getElementById('priceRange') as HTMLInputElement;
  const priceDisplay = document.getElementById('priceDisplay');

  if (priceRange && priceDisplay) {
    const updateDisplay = () => {
      // Format the number with a comma for thousands
      const formattedPrice = parseInt(priceRange.value, 10).toLocaleString();
      priceDisplay.textContent = `${formattedPrice} KES`;
    };

    // Set initial value just in case
    updateDisplay();

    // Add event listener, ensuring we don't add multiple
    if (!(priceRange as any)._priceDisplayAdded) {
      priceRange.addEventListener('input', updateDisplay);
      (priceRange as any)._priceDisplayAdded = true;
    }
  }
}