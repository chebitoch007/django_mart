// frontend/src/store/main.ts

// Store main entry point
import './styles/product-list.css';
import './styles/product-detail.css';
import './styles/search.css';
import './styles/categories.css';


// Then import functionality
import { initProductList } from './product-list';
import { initProductDetail } from './product-detail';
import { initSearch } from './search';
import { initCategories } from './categories';

// Initialize based on current page
document.addEventListener('DOMContentLoaded', () => {
  // Get the unique page name from the body's data-page attribute
  const pageName = document.body.dataset.page;

  console.log(`🛒 Store main script loaded. Page: ${pageName}`);

  // Use a mutually exclusive if/else if block
  // This ensures ONLY the correct script runs
  if (pageName === 'product-detail') {
    console.log('🔍 Detected product detail page');
    initProductDetail();
  } else if (pageName === 'product-list') {
    console.log('📦 Detected product list page');
    initProductList();
  } else if (pageName === 'search') {
    console.log('🔎 Detected search page');
    initSearch();
  } else if (pageName === 'categories') {
    console.log('📂 Detected categories page');
    initCategories();
  }
});

// Export for global access if needed
declare global {
  interface Window {
    storeUtils: any;
  }
}

export { initProductList, initProductDetail, initSearch, initCategories };