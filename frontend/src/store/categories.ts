/**
 * categories.ts
 * * Initializes UI enhancements for the categories page that HTMX doesn't handle,
 * such as the price range slider's text display.
 */

export function initCategories(): void {
  console.log('Initializing categories page enhancements...');

  // This function wires up the mobile filter toggle and the price range slider's text display.
  // It's safe to call multiple times (e.g., after HTMX swaps) as it
  // checks for element existence.
  initFilterSidebarEnhancements();
}

/**
 * Wires up client-side-only enhancements for the filter sidebar.
 * - Price Slider: Updates the price text display as the slider moves.
 *
 * 🛑 REMOVED: The old logic for filterToggleBtn, filterSidebar, and
 * filterCloseBtn. This is now 100% handled by the global `filters.js`
 * and `filters.css`, which were being conflicted with.
 */
function initFilterSidebarEnhancements(): void {

  // --- Price Range Slider Display Logic ---
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
      console.log('Categories page price range listener added.');
    }
  }
}