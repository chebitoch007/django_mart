//frontend/src/store/main.ts

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
  const body = document.body;

  console.log('🛒 Store main script loaded');

  // Check for product list page
  if (body.classList.contains('product-list-page') ||
      window.location.pathname.includes('/products/') ||
      document.querySelector('.product-list-container')) {
    console.log('📦 Detected product list page');
    initProductList();
  }

  // Check for product detail page
  if (body.classList.contains('product-detail-page') ||
      document.querySelector('.product-detail-container')) {
    console.log('🔍 Detected product detail page');
    initProductDetail();
  }

  // Check for search page
  if (body.classList.contains('search-page') ||
      window.location.pathname.includes('/search/') ||
      document.querySelector('.search-results-container')) {
    console.log('🔎 Detected search page');
    initSearch();
  }

  // Check for categories page
  if (body.classList.contains('categories-page') ||
      document.querySelector('.categories-container')) {
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