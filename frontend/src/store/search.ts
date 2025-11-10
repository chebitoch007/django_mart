/**
 * search.ts
 * * Initializes UI enhancements for the search results page.
 * * This file is intentionally simple, as HTMX handles all filtering.
 * * This replaces the conflicting, non-HTMX version.
 */

export function initSearch(): void {
  console.log('Initializing search page enhancements...');

  // This function wires up the price slider display.
  // It's safe to call multiple times (e.g., after HTMX swaps) as it
  // checks for element existence and uses an idempotency flag.
  initSearchFilterEnhancements();

  // You can add functions to re-initialize grid-specific things here
  // (like lazy loading or analytics) if needed, as they run on
  // content inside the #resultsRoot.
}

/**
 * Wires up client-side-only enhancements for the filter sidebar.
 * - Price Slider: Updates the price text display as the slider moves.
 */
function initSearchFilterEnhancements(): void {

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
      console.log('Search page price range listener added.');
    }
  }
}