// src/store/product-list.ts - Cleaned Version

export function initProductList(): void {
  const priceRange = document.getElementById('priceRange') as HTMLInputElement;
  const priceDisplay = document.getElementById('priceDisplay');

  if (priceRange && priceDisplay) {
    const updateDisplay = () => {
      const formattedPrice = parseInt(priceRange.value, 10).toLocaleString();
      priceDisplay.textContent = `${formattedPrice} KES`;
    };

    updateDisplay();

    if (!(priceRange as any)._priceDisplayAdded) {
      priceRange.addEventListener('input', updateDisplay);
      (priceRange as any)._priceDisplayAdded = true;
      console.log('Price range listener added.');
    }
  }

  initProductGrid();
  initAnalytics();
}

function initProductGrid(): void {
  const productCards = document.querySelectorAll('#resultsRoot .product-card');

  productCards.forEach((card) => {
    card.addEventListener('mouseenter', () => {
      card.classList.add('hover');
      preloadProductImages(card as HTMLElement);
    });

    card.addEventListener('mouseleave', () => {
      card.classList.remove('hover');
    });

    initLazyLoading(card as HTMLElement);
  });
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

function initAnalytics(): void {
  const productCards = document.querySelectorAll('#resultsRoot .product-card');

  const observer = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
      if (entry.isIntersecting) {
        const card = entry.target as HTMLElement;
        const productId = card.getAttribute('data-product-id');

        if (productId && !card.classList.contains('view-tracked')) {
          card.classList.add('view-tracked');

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