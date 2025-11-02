// frontend/src/store/main.ts - UPDATED with filters import

console.log('🟢 STORE main.ts loaded');

import './styles/product-list.css';
import './styles/product-detail.css';
import './styles/search.css';
import './styles/categories.css';
import './styles/filters.css';

// Import functionality
import { initProductList } from './product-list';
import { initProductDetail } from './product-detail';
import { initSearch } from './search';
import { initCategories } from './categories';

// ✅ CRITICAL: Import but DON'T call getInstance() here
// The base.ts module already initializes CartManager when imported
import './base';

// ✅ Track if we've already initialized to prevent duplicates
let isStoreInitialized = false;

// Initialize based on current page
function initializeStorePage() {
  if (isStoreInitialized) {
    console.warn('⚠️ Store already initialized, skipping...');
    return;
  }

  // Get the unique page name from the body's data-page attribute
  const pageName = document.body.dataset.page;

  console.log(`🛒 Store main script loaded. Page: ${pageName}`);

  if (pageName === 'product-detail') {
    console.log('📝 Detected product detail page');
    initProductDetail();
  }
  else if (pageName === 'product-list') {
    console.log('📦 Detected product list page');
    initProductList();
  }
  else if (pageName === 'search') {
    console.log('🔍 Detected search page');
    initSearch();
  }
  else if (pageName === 'categories') {
    console.log('📂 Detected categories page');
    initCategories();
  }

  isStoreInitialized = true;

  // Additional: handle HTMX swaps so page-specific initialisation fires after swap
  document.body.addEventListener('htmx:afterSwap', (evt: any) => {
    const target = evt.detail?.target as HTMLElement | null;
    if (!target) return;

    // If the results container was swapped in (for product list), re-initialise
    if (pageName === 'product-list' && target.id === 'resultsRoot') {
      console.log('↻ HTMX afterSwap on resultsRoot – re-init product list logic');
      initProductList();
    }

    // If other page types need re-init after swap, add here as needed
  });
}

// ✅ Use standard DOMContentLoaded (don't initialize multiple times)
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', initializeStorePage);
} else {
  // DOM already loaded
  initializeStorePage();
}

// Export for global access if needed
declare global {
  interface Window {
    storeUtils: any;
  }
}

export { initProductList, initProductDetail, initSearch, initCategories };