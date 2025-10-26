import { StoreUtils, cartManager } from './base';

export function initProductList(): void {
  const filterToggle = document.getElementById('filterToggle');
  const filterContent = document.getElementById('filterContent');
  const priceRange = document.getElementById('priceRange') as HTMLInputElement;
  const priceDisplay = document.getElementById('priceDisplay');

  // Mobile sidebar toggle (doesn't conflict with HTMX)
  function setupFilterSidebar() {
  const filterToggle = document.getElementById('filterToggle');
  const filterContent = document.getElementById('filterContent');

  if (!filterToggle || !filterContent) return;

  const MOBILE_BREAKPOINT = 1024;

  function updateSidebarVisibility() {
    if (window.innerWidth >= MOBILE_BREAKPOINT) {
      // Desktop view: show sidebar and hide toggle
      filterContent.removeAttribute('hidden');
      filterContent.classList.remove('slide-in');
      filterToggle.style.display = 'none';
    } else {
      // Mobile view: hide sidebar and show toggle
      if (!filterToggle.hasAttribute('aria-expanded') || filterToggle.getAttribute('aria-expanded') === 'false') {
        filterContent.setAttribute('hidden', '');
      }
      filterToggle.style.display = 'flex';
    }
  }

  // Initial setup
  updateSidebarVisibility();

  // Update on resize
  window.addEventListener('resize', StoreUtils.debounce(updateSidebarVisibility, 150));

  // Toggle behavior for mobile
  filterToggle.addEventListener('click', () => {
    const isHidden = filterContent.hasAttribute('hidden');

    if (isHidden) {
      filterContent.removeAttribute('hidden');
      filterContent.classList.add('slide-in');
      filterToggle.setAttribute('aria-expanded', 'true');
      document.body.classList.add('no-scroll'); // prevent background scroll
    } else {
      filterContent.classList.remove('slide-in');
      setTimeout(() => filterContent.setAttribute('hidden', ''), 250); // after animation
      filterToggle.setAttribute('aria-expanded', 'false');
      document.body.classList.remove('no-scroll');
    }

    const span = filterToggle.querySelector('span');
    if (span) span.textContent = isHidden ? 'Hide Filters' : 'Show Filters';
  });
}

// Call it inside initProductList()
setupFilterSidebar();
  // Live update price display (visual feedback only, HTMX handles submission)
  if (priceRange && priceDisplay) {
    priceRange.addEventListener('input', () => {
      priceDisplay.textContent = `${priceRange.value} KES`;
    });
  }

  // Initialize product grid enhancements (non-conflicting)
  initProductGrid();

  // Initialize analytics tracking
  initAnalytics();
}

function initProductGrid(): void {
  const productCards = document.querySelectorAll('.product-card');

  productCards.forEach((card) => {
    // Add hover effects for better UX
    card.addEventListener('mouseenter', () => {
      card.classList.add('hover');
      preloadProductImages(card as HTMLElement);
    });

    card.addEventListener('mouseleave', () => {
      card.classList.remove('hover');
    });

    // Lazy loading for images
    initLazyLoading(card as HTMLElement);
  });

  // Animate product count on page load
  animateProductCount();
}

function preloadProductImages(card: HTMLElement): void {
  const hoverImage = card.getAttribute('data-hover-image');

  if (hoverImage && !card.classList.contains('image-preloaded')) {
    const img = new Image();
    img.src = hoverImage;
    img.onload = () => {
      card.classList.add('image-preloaded');
    };
  }
}

function initLazyLoading(card: HTMLElement): void {
  const images = card.querySelectorAll('img[data-src]');

  const observer = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
      if (entry.isIntersecting) {
        const img = entry.target as HTMLImageElement;
        const dataSrc = img.getAttribute('data-src');
        if (dataSrc) {
          img.src = dataSrc;
          img.removeAttribute('data-src');
          observer.unobserve(img);

          // Add loaded class for fade-in effect
          img.addEventListener('load', () => {
            img.classList.add('loaded');
          });
        }
      }
    });
  }, {
    rootMargin: '50px 0px',
    threshold: 0.01
  });

  images.forEach(img => observer.observe(img));
}

function initQuickView(): void {
  // Quick view modal functionality
  document.addEventListener('click', (e) => {
    const quickViewBtn = (e.target as Element).closest('.quick-view-btn');
    if (quickViewBtn) {
      e.preventDefault();
      const productId = quickViewBtn.getAttribute('data-product-id');
      if (productId) {
        openQuickView(productId);
      }
    }
  });

  // Close quick view
  document.addEventListener('click', (e) => {
    const quickView = document.getElementById('quick-view-modal');
    if (quickView && (e.target === quickView || (e.target as Element).closest('.close-quick-view'))) {
      closeQuickView();
    }
  });

  // Keyboard navigation
  document.addEventListener('keydown', (e: KeyboardEvent) => {
    const quickView = document.getElementById('quick-view-modal');
    if (quickView && !quickView.classList.contains('hidden')) {
      if (e.key === 'Escape') {
        closeQuickView();
      } else if (e.key === 'ArrowLeft') {
        navigateQuickView('prev');
      } else if (e.key === 'ArrowRight') {
        navigateQuickView('next');
      }
    }
  });
}

function openQuickView(productId: string): void {
  const modal = document.getElementById('quick-view-modal');
  if (modal) {
    modal.classList.remove('hidden');
    modal.innerHTML = `
      <div class="quick-view-loading">
        <i class="fas fa-spinner fa-spin fa-2x"></i>
        <p>Loading product details...</p>
      </div>
    `;

    // Fetch product data
    fetch(`/api/products/${productId}/quick-view/`)
      .then(response => response.json())
      .then(data => {
        if (data.success) {
          renderQuickView(data.product);
        } else {
          showQuickViewError();
        }
      })
      .catch(error => {
        console.error('Quick view failed:', error);
        showQuickViewError();
      });
  }

  // Prevent body scroll
  document.body.style.overflow = 'hidden';
}

function renderQuickView(product: any): void {
  const modal = document.getElementById('quick-view-modal');
  if (!modal) return;

  modal.innerHTML = `
    <div class="quick-view-content">
      <button class="close-quick-view" aria-label="Close quick view">
        <i class="fas fa-times"></i>
      </button>
      
      <div class="quick-view-nav">
        <button class="nav-btn prev-btn" aria-label="Previous product">
          <i class="fas fa-chevron-left"></i>
        </button>
        <button class="nav-btn next-btn" aria-label="Next product">
          <i class="fas fa-chevron-right"></i>
        </button>
      </div>

      <div class="quick-view-body">
        <div class="quick-view-images">
          <img src="${product.image_url}" alt="${product.name}" class="main-image">
          <div class="image-thumbnails">
            ${product.images?.map((img: string, index: number) => `
              <img src="${img}" alt="Thumbnail ${index + 1}" class="thumbnail ${index === 0 ? 'active' : ''}">
            `).join('') || ''}
          </div>
        </div>

        <div class="quick-view-details">
          <h2 class="product-title">${product.name}</h2>
          <div class="price">${StoreUtils.formatPrice(product.price)}</div>
          <div class="rating">${generateStarRating(product.rating)}</div>
          <div class="stock-status">${product.stock > 0 ? 'In Stock' : 'Out of Stock'}</div>
          <p class="description">${product.short_description}</p>

          <div class="quick-actions">
            <button class="btn-primary add-to-cart-quick" 
                    ${product.stock <= 0 ? 'disabled' : ''}
                    data-product-id="${product.id}">
              <i class="fas fa-shopping-cart"></i>
              Add to Cart
            </button>
            <button class="btn-secondary wishlist-btn" data-product-id="${product.id}">
              <i class="far fa-heart"></i>
            </button>
            <button class="btn-secondary compare-btn" data-product-id="${product.id}">
              <i class="fas fa-balance-scale"></i>
            </button>
          </div>

          <div class="product-meta">
            <div class="meta-item">
              <i class="fas fa-shipping-fast"></i>
              Free shipping
            </div>
            <div class="meta-item">
              <i class="fas fa-undo"></i>
              30-day returns
            </div>
            <div class="meta-item">
              <i class="fas fa-shield-alt"></i>
              2-year warranty
            </div>
          </div>
        </div>
      </div>
    </div>
  `;

  // Add event listeners for quick view actions
  initQuickViewActions();
}

function initQuickViewActions(): void {
  // Add to cart from quick view
  document.querySelector('.add-to-cart-quick')?.addEventListener('click', (e) => {
    const button = e.target as HTMLButtonElement;
    const productId = button.getAttribute('data-product-id');

    if (productId) {
      cartManager.quickAdd(parseInt(productId), 1);
      button.innerHTML = '<i class="fas fa-check"></i> Added to Cart';
      button.disabled = true;

      setTimeout(() => {
        button.innerHTML = '<i class="fas fa-shopping-cart"></i> Add to Cart';
        button.disabled = false;
      }, 2000);
    }
  });

  // Wishlist from quick view
  document.querySelector('.wishlist-btn')?.addEventListener('click', (e) => {
    const button = e.target as HTMLButtonElement;
    const productId = button.getAttribute('data-product-id');

    if (productId) {
      const isActive = button.classList.contains('active');
      button.classList.toggle('active');
      button.innerHTML = isActive ?
        '<i class="far fa-heart"></i>' :
        '<i class="fas fa-heart" style="color: #ef4444;"></i>';

      // Dispatch wishlist event
      document.dispatchEvent(new CustomEvent('wishlist:toggle', {
        detail: {
          product: { id: parseInt(productId) },
          action: isActive ? 'remove' : 'add'
        }
      }));
    }
  });

  // Image navigation in quick view
  document.querySelectorAll('.thumbnail').forEach(thumb => {
    thumb.addEventListener('click', () => {
      const mainImage = document.querySelector('.quick-view-images .main-image') as HTMLImageElement;
      if (mainImage && thumb instanceof HTMLImageElement) {
        mainImage.src = thumb.src;

        // Update active thumbnail
        document.querySelectorAll('.thumbnail').forEach(t => t.classList.remove('active'));
        thumb.classList.add('active');
      }
    });
  });

  // Quick view navigation
  document.querySelector('.prev-btn')?.addEventListener('click', () => navigateQuickView('prev'));
  document.querySelector('.next-btn')?.addEventListener('click', () => navigateQuickView('next'));
}

function navigateQuickView(direction: 'prev' | 'next'): void {
  const currentProductId = document.querySelector('.add-to-cart-quick')?.getAttribute('data-product-id');
  const productCards = Array.from(document.querySelectorAll('.product-card'));
  const currentIndex = productCards.findIndex(card =>
    card.getAttribute('data-product-id') === currentProductId
  );

  let newIndex;
  if (direction === 'prev') {
    newIndex = currentIndex > 0 ? currentIndex - 1 : productCards.length - 1;
  } else {
    newIndex = currentIndex < productCards.length - 1 ? currentIndex + 1 : 0;
  }

  const newProductId = productCards[newIndex]?.getAttribute('data-product-id');
  if (newProductId) {
    openQuickView(newProductId);
  }
}

function closeQuickView(): void {
  const modal = document.getElementById('quick-view-modal');
  if (modal) {
    modal.classList.add('hidden');
  }
  document.body.style.overflow = '';
}

function showQuickViewError(): void {
  const modal = document.getElementById('quick-view-modal');
  if (modal) {
    modal.innerHTML = `
      <div class="quick-view-error">
        <i class="fas fa-exclamation-triangle fa-2x"></i>
        <h3>Unable to load product</h3>
        <p>Please try again later.</p>
        <button class="btn-primary close-quick-view">Close</button>
      </div>
    `;
  }
}

function initComparison(): void {
  const compareCheckboxes = document.querySelectorAll('.compare-checkbox');
  const compareBar = document.getElementById('compare-bar');
  let comparedProducts: number[] = [];

  compareCheckboxes.forEach(checkbox => {
    checkbox.addEventListener('change', () => {
      const productId = parseInt((checkbox as HTMLInputElement).value);

      if ((checkbox as HTMLInputElement).checked) {
        comparedProducts.push(productId);
      } else {
        comparedProducts = comparedProducts.filter(id => id !== productId);
      }

      updateCompareBar(comparedProducts);
    });
  });

  function updateCompareBar(products: number[]): void {
    if (!compareBar) return;

    if (products.length > 0) {
      compareBar.classList.remove('hidden');

      const countElement = compareBar.querySelector('.compare-count');
      if (countElement) {
        countElement.textContent = products.length.toString();
      }

      const compareBtn = compareBar.querySelector('.compare-btn');
      if (compareBtn) {
        (compareBtn as HTMLButtonElement).disabled = products.length < 2;
      }
    } else {
      compareBar.classList.add('hidden');
    }
  }

  // Compare action
  document.querySelector('.compare-btn')?.addEventListener('click', () => {
    const products = comparedProducts.join(',');
    window.open(`/compare/?products=${products}`, '_blank');
  });
}

function initInfiniteScroll(): void {
  if (!document.body.classList.contains('infinite-scroll')) return;

  const observer = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
      if (entry.isIntersecting) {
        loadMoreProducts();
      }
    });
  }, {
    rootMargin: '100px 0px',
    threshold: 0.1
  });

  const sentinel = document.getElementById('load-more-sentinel');
  if (sentinel) {
    observer.observe(sentinel);
  }
}

function loadMoreProducts(): void {
  const loadMoreBtn = document.getElementById('load-more-btn');
  const currentPage = parseInt(loadMoreBtn?.getAttribute('data-page') || '1');
  const totalPages = parseInt(loadMoreBtn?.getAttribute('data-total-pages') || '1');

  if (currentPage >= totalPages) return;

  if (loadMoreBtn instanceof HTMLButtonElement) {
    loadMoreBtn.disabled = true;
  }

  const nextPage = currentPage + 1;
  const url = new URL(window.location.href);
  url.searchParams.set('page', nextPage.toString());

  fetch(url.toString())
    .then(response => response.text())
    .then(html => {
      const parser = new DOMParser();
      const doc = parser.parseFromString(html, 'text/html');
      const newProducts = doc.querySelector('.product-grid')?.innerHTML;

      if (newProducts) {
        const productGrid = document.querySelector('.product-grid');
        if (productGrid) {
          productGrid.innerHTML += newProducts;
        }

        if (loadMoreBtn instanceof HTMLButtonElement) {
          loadMoreBtn.setAttribute('data-page', nextPage.toString());

          if (nextPage >= totalPages) {
            loadMoreBtn.style.display = 'none';
          } else {
            loadMoreBtn.innerHTML = 'Load More Products';
            loadMoreBtn.disabled = false;
          }
        }

        // Re-initialize product grid for new products
        initProductGrid();
      }
    })
    .catch(error => {
      console.error('Failed to load more products:', error);
      if (loadMoreBtn instanceof HTMLButtonElement) {
        loadMoreBtn.innerHTML = 'Error loading products';
        setTimeout(() => {
          loadMoreBtn.innerHTML = 'Load More Products';
          loadMoreBtn.disabled = false;
        }, 3000);
      }
    });
}

function initAnalytics(): void {
  // Track product views
  const productCards = document.querySelectorAll('.product-card');

  const observer = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
      if (entry.isIntersecting) {
        const card = entry.target as HTMLElement;
        const productId = card.getAttribute('data-product-id');

        if (productId && !card.classList.contains('view-tracked')) {
          card.classList.add('view-tracked');

          // Dispatch analytics event
          document.dispatchEvent(new CustomEvent('analytics:productView', {
            detail: {
              productId: parseInt(productId),
              list: getProductListType(),
              position: Array.from(productCards).indexOf(card) + 1
            }
          }));
        }
      }
    });
  }, {
    threshold: 0.5
  });

  productCards.forEach(card => observer.observe(card));
}

function getProductListType(): string {
  if (document.body.classList.contains('search-page')) return 'search';
  if (document.body.classList.contains('category-page')) return 'category';
  if (window.location.pathname.includes('/deals/')) return 'deals';
  return 'general';
}

function animateProductCount(): void {
  const countElement = document.querySelector('.product-count');
  if (countElement) {
    StoreUtils.animateElement(countElement as HTMLElement, 'bounceIn', 500);
  }
}

function generateStarRating(rating: number): string {
  const fullStars = Math.floor(rating);
  const hasHalfStar = rating % 1 >= 0.5;
  const emptyStars = 5 - fullStars - (hasHalfStar ? 1 : 0);

  return `
    ${'<i class="fas fa-star"></i>'.repeat(fullStars)}
    ${hasHalfStar ? '<i class="fas fa-star-half-alt"></i>' : ''}
    ${'<i class="far fa-star"></i>'.repeat(emptyStars)}
  `;
}

// Export additional functions
export {
  initQuickView,
  initComparison,
  initInfiniteScroll,
  loadMoreProducts
};