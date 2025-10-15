import { StoreUtils, cartManager } from './base';
import { Category, Product } from './types';

export function initCategories(): void {
  console.log('Initializing categories...');

  const priceRange = document.getElementById('priceRange') as HTMLInputElement;
  const priceDisplay = document.getElementById('priceDisplay');
  const inStockCheckbox = document.getElementById('inStock') as HTMLInputElement;

  // Price range filter with debounce
  if (priceRange && priceDisplay) {
    const updatePriceFilter = StoreUtils.debounce((value: string) => {
      const url = StoreUtils.updateQueryStringParameter(window.location.href, 'max_price', value);
      window.location.href = url;
    }, 800);

    priceRange.addEventListener('input', () => {
      const value = priceRange.value;
      priceDisplay.textContent = `${value} KES`;
      updatePriceFilter(value);
    });
  }

  // Stock filter
  if (inStockCheckbox) {
    inStockCheckbox.addEventListener('change', () => {
      const url = inStockCheckbox.checked ?
        StoreUtils.updateQueryStringParameter(window.location.href, 'in_stock', 'true') :
        StoreUtils.removeQueryStringParameter(window.location.href, 'in_stock');
      window.location.href = url;
    });
  }

  // Initialize category sorting
  initCategorySorting();
}

function initCategorySorting(): void {
  const sortSelect = document.getElementById('category-sort') as HTMLSelectElement;

  if (sortSelect) {
    sortSelect.addEventListener('change', StoreUtils.debounce(() => {
      updateCategoryFilter('sort', sortSelect.value);
    }, 300));
  }
}



// Fix the updateCategoryContent function
function updateCategoryContent(category: Category): void {
  // Update page title
  document.title = `${category.name} - ASAI`;

  // Update category title
  const titleElement = document.querySelector('.category-title');
  if (titleElement) {
    titleElement.textContent = category.name;
  }

  // Update breadcrumbs
  updateBreadcrumbs(category);

  // Update products if they exist
  if (category.products) {
    updateCategoryProducts(category.products);
  }

  // Update filters if they exist
  if (category.filters) {
    updateCategoryFilters(category.filters);
  }
}
// Fix the filter count assignment
function updateFilterCounts(doc: Document): void {
  const filterCounts = doc.querySelectorAll('[data-filter-count]');

  filterCounts.forEach(filter => {
    const filterName = filter.getAttribute('data-filter-name');
    const count = filter.getAttribute('data-filter-count');

    const currentFilter = document.querySelector(`[data-filter-name="${filterName}"]`);
    if (currentFilter) {
      currentFilter.setAttribute('data-filter-count', count!);
      const countElement = currentFilter.querySelector('.filter-count');
      if (countElement) {
        countElement.textContent = count;
      }
    }
  });
}
function updateCategoryFilter(param: string, value: string): void {
  const url = new URL(window.location.href);

  if (value) {
    url.searchParams.set(param, value);
  } else {
    url.searchParams.delete(param);
  }

  // Use AJAX for smooth filtering if enabled
  if (document.body.classList.contains('ajax-category')) {
    updateCategoryProductsViaAJAX(url);
  } else {
    // Update URL and reload
    window.history.replaceState({}, '', url.toString());
  }
}

function updateCategoryProductsViaAJAX(url: URL): void {
  const productsContainer = document.getElementById('category-products');
  const loadingIndicator = document.getElementById('category-loading');

  if (productsContainer && loadingIndicator) {
    // Show loading state
    productsContainer.classList.add('loading');
    loadingIndicator.classList.remove('hidden');

    // Set AJAX flag
    url.searchParams.set('ajax', 'true');

    fetch(url.toString())
      .then(response => response.text())
      .then(html => {
        const parser = new DOMParser();
        const doc = parser.parseFromString(html, 'text/html');
        const newProducts = doc.getElementById('category-products');

        if (newProducts) {
          productsContainer.innerHTML = newProducts.innerHTML;

          // Re-initialize product interactions
          initCategoryProducts();

          // Update filter counts
          updateFilterCounts(doc);

          // Update product count
          updateProductCount(doc);
        }
      })
      .catch(error => {
        console.error('Failed to update category products:', error);
        showCategoryError();
      })
      .finally(() => {
        productsContainer.classList.remove('loading');
        loadingIndicator.classList.add('hidden');
      });
  }
}

function initCategoryProducts(): void {
  const productCards = document.querySelectorAll('.category-product-card');

  productCards.forEach(card => {
    // Enhanced hover effects
    card.addEventListener('mouseenter', () => {
      card.classList.add('hover');
      preloadCategoryProductImages(card as HTMLElement);
    });

    card.addEventListener('mouseleave', () => {
      card.classList.remove('hover');
    });

    // Quick actions
    initCategoryProductQuickActions(card as HTMLElement);

    // Lazy loading
    initCategoryLazyLoading(card as HTMLElement);
  });

  // Category-specific product interactions
  initCategoryProductSorting();
}

function preloadCategoryProductImages(card: HTMLElement): void {
  const hoverImage = card.getAttribute('data-hover-image');

  if (hoverImage && !card.classList.contains('image-preloaded')) {
    const img = new Image();
    img.src = hoverImage;
    img.onload = () => {
      card.classList.add('image-preloaded');
    };
  }
}

function initCategoryLazyLoading(card: HTMLElement): void {
  const images = card.querySelectorAll('img[data-src]');

  const observer = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
      if (entry.isIntersecting) {
        const img = entry.target as HTMLImageElement;
        img.src = img.getAttribute('data-src')!;
        img.removeAttribute('data-src');
        observer.unobserve(img);

        img.addEventListener('load', () => {
          img.classList.add('loaded');
        });
      }
    });
  });

  images.forEach(img => observer.observe(img));
}

function initCategoryProductQuickActions(card: HTMLElement): void {
  const quickActions = card.querySelector('.product-quick-actions');

  if (quickActions) {
    // Quick add to cart
    const quickAddBtn = quickActions.querySelector('.quick-add-btn');
    quickAddBtn?.addEventListener('click', (e) => {
      e.preventDefault();
      const productId = card.getAttribute('data-product-id');
      if (productId) {
        cartManager.quickAdd(parseInt(productId), 1);

        // Visual feedback
        (quickAddBtn as HTMLElement).innerHTML = '<i class="fas fa-check"></i>';
        setTimeout(() => {
          (quickAddBtn as HTMLElement).innerHTML = '<i class="fas fa-cart-plus"></i>';
        }, 1000);
      }
    });

    // Quick view
    const quickViewBtn = quickActions.querySelector('.quick-view-btn');
    quickViewBtn?.addEventListener('click', (e) => {
      e.preventDefault();
      const productId = card.getAttribute('data-product-id');
      if (productId) {
        // Import and use quick view functionality
        import('./product-list').then(() => {
          // You would need to expose the quick view function
          console.log('Quick view for product:', productId);
        });
      }
    });
  }
}

function initCategoryProductSorting(): void {
  const sortSelect = document.getElementById('category-sort') as HTMLSelectElement;

  if (sortSelect) {
    sortSelect.addEventListener('change', StoreUtils.debounce(() => {
      updateCategoryFilter('sort', sortSelect.value);
    }, 300));
  }

  // View mode toggle
  initCategoryViewMode();
}

function initCategoryViewMode(): void {
  const viewModeButtons = document.querySelectorAll('.category-view-mode-btn');
  const productsContainer = document.querySelector('.category-products-grid');

  viewModeButtons.forEach(btn => {
    btn.addEventListener('click', () => {
      const mode = btn.getAttribute('data-mode');

      // Update active button
      viewModeButtons.forEach(b => b.classList.remove('active'));
      btn.classList.add('active');

      // Update grid layout
      if (productsContainer) {
        productsContainer.className = `category-products-grid ${mode}-view`;
      }

      // Save preference
      StoreUtils.setStorage('category-view-mode', mode);
    });
  });

  // Load saved view mode
  const savedViewMode = StoreUtils.getStorage<string>('category-view-mode') || 'grid';
  const savedBtn = document.querySelector(`[data-mode="${savedViewMode}"]`);
  if (savedBtn) {
    (savedBtn as HTMLElement).click();
  }
}
function navigateToCategory(categoryId: string): void {
  // Show loading state
  const categoryContent = document.getElementById('category-content');
  if (categoryContent) {
    categoryContent.classList.add('loading');
  }

  // Fetch category content via AJAX
  fetch(`/api/categories/${categoryId}/`)
    .then(response => response.json())
    .then(data => {
      if (data.success) {
        updateCategoryContent(data.category);

        // Update URL
        window.history.pushState({}, '', data.category.url);
      }
    })
    .catch(error => {
      console.error('Category navigation failed:', error);
      // Fallback to full page load
      window.location.href = `/categories/${categoryId}/`;
    })
    .finally(() => {
      categoryContent?.classList.remove('loading');
    });
}



function updateBreadcrumbs(category: Category): void {
  const breadcrumbContainer = document.querySelector('.category-breadcrumbs');
  if (breadcrumbContainer) {
    // Implementation would depend on your breadcrumb structure
    console.log('Update breadcrumbs for:', category.name);
  }
}

function updateCategoryProducts(products: Product[]): void {
  const productsContainer = document.getElementById('category-products');
  if (productsContainer) {
    // Render products (implementation depends on your template)
    console.log('Update products:', products.length);
  }
}

function updateCategoryFilters(filters: any): void {
  // Update filter options and counts
  console.log('Update filters:', filters);
}
function updateProductCount(doc: Document): void {
  const productCount = doc.querySelector('.product-count');
  const currentCount = document.querySelector('.product-count');

  if (productCount && currentCount) {
    currentCount.textContent = productCount.textContent;

    // Animate count change
    StoreUtils.animateElement(currentCount as HTMLElement, 'pulse', 300);
  }
}

function getCategoryProductCount(): number {
  const countElement = document.querySelector('.product-count');
  if (countElement) {
    const text = countElement.textContent || '';
    const match = text.match(/\d+/);
    return match ? parseInt(match[0]) : 0;
  }
  return 0;
}

function showCategoryError(): void {
  const errorElement = StoreUtils.createElement('div', {
    className: 'category-error-message'
  }, [
    '<i class="fas fa-exclamation-triangle"></i>',
    '<h3>Category Unavailable</h3>',
    '<p>There was a problem loading this category. Please try again.</p>',
    '<button class="btn-primary" onclick="window.location.reload()">Retry</button>'
  ]);

  const categoryContent = document.getElementById('category-content');
  if (categoryContent) {
    categoryContent.innerHTML = '';
    categoryContent.appendChild(errorElement);
  }
}
// Export for use in other modules
export {
  updateCategoryFilter,
  navigateToCategory,
  getCategoryProductCount
};