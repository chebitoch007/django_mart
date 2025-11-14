// ========================================
// Product Detail Page - Cleaned TypeScript
// ========================================

interface ProductVariant {
  id: number;
  color: string | null;
  size: string | null;
  price: number;
  quantity: number;
}

// ========================================
// Helper Functions
// ========================================

function getCsrfToken(): string {
  const tokenEl = document.querySelector('[name=csrfmiddlewaretoken]') as HTMLInputElement;
  return tokenEl ? tokenEl.value : '';
}

function showNotification(message: string, type: 'success' | 'error'): void {
  if (typeof (window as any).showNotification === 'function') {
    (window as any).showNotification(message, type);
    return;
  }

  const toast = document.createElement('div');
  toast.className = `toast ${type}`;
  const icon = document.createElement('i');
  icon.className = type === 'success' ? 'fas fa-check-circle' : 'fas fa-exclamation-circle';
  toast.appendChild(icon);
  toast.appendChild(document.createTextNode(message));
  document.body.appendChild(toast);

  setTimeout(() => {
    toast.style.animation = 'slideOutDown 0.3s ease forwards';
    toast.addEventListener('animationend', () => toast.remove());
  }, 2700);
}

// ========================================
// Image Gallery with Zoom & Swipe
// ========================================

function initImageGallery(): void {
  const mainImage = document.getElementById('main-product-image') as HTMLImageElement;
  const thumbnailItems = document.querySelectorAll('.thumbnail-item');
  const zoomContainer = document.getElementById('image-zoom-container');
  const fullscreenBtn = document.getElementById('fullscreen-btn');

  if (!mainImage || !zoomContainer) return;

  thumbnailItems.forEach(item => {
    const img = item.querySelector('.thumbnail-image') as HTMLImageElement;
    if (img) {
      item.addEventListener('click', (e) => {
        e.preventDefault();
        const newSrc = img.dataset.src || img.src;
        const newLargeSrc = img.dataset.largeSrc || newSrc;

        mainImage.style.opacity = '0';
        setTimeout(() => {
          mainImage.src = newSrc;
          mainImage.dataset.largeSrc = newLargeSrc;
          (zoomContainer as HTMLElement).style.backgroundImage = `url(${newLargeSrc})`;
          mainImage.style.opacity = '1';
        }, 200);

        thumbnailItems.forEach(thumb => thumb.classList.remove('active'));
        item.classList.add('active');
      });
    }
  });

  const zoomParent = mainImage.parentElement;
  if (zoomParent) {
    zoomParent.addEventListener('mousemove', (e: MouseEvent) => {
      const { left, top, width, height } = zoomParent.getBoundingClientRect();
      const x = ((e.clientX - left) / width) * 100;
      const y = ((e.clientY - top) / height) * 100;
      (zoomContainer as HTMLElement).style.backgroundPosition = `${x}% ${y}%`;
    });

    zoomParent.addEventListener('mouseenter', () => {
      (zoomContainer as HTMLElement).classList.add('active');
    });

    zoomParent.addEventListener('mouseleave', () => {
      (zoomContainer as HTMLElement).classList.remove('active');
    });
  }

  fullscreenBtn?.addEventListener('click', () => {
    const lightbox = createLightbox(mainImage.dataset.largeSrc || mainImage.src);
    document.body.appendChild(lightbox);
  });

  let touchStartX = 0;
  let touchEndX = 0;

  mainImage.addEventListener('touchstart', (e) => {
    touchStartX = e.changedTouches[0].screenX;
  });

  mainImage.addEventListener('touchend', (e) => {
    touchEndX = e.changedTouches[0].screenX;
    handleSwipe();
  });

  function handleSwipe(): void {
    const swipeThreshold = 50;
    if (touchEndX < touchStartX - swipeThreshold) {
      navigateImages(1);
    } else if (touchEndX > touchStartX + swipeThreshold) {
      navigateImages(-1);
    }
  }

  function navigateImages(direction: number): void {
    const activeIndex = Array.from(thumbnailItems).findIndex(thumb =>
      thumb.classList.contains('active')
    );
    const newIndex = (activeIndex + direction + thumbnailItems.length) % thumbnailItems.length;
    (thumbnailItems[newIndex] as HTMLElement).click();
  }

  mainImage.style.transition = 'opacity 0.3s ease';
}

function createLightbox(imageSrc: string): HTMLElement {
  const lightbox = document.createElement('div');
  lightbox.className = 'image-lightbox';
  lightbox.style.cssText = `
    position: fixed; top: 0; left: 0; width: 100%; height: 100%;
    background: rgba(0, 0, 0, 0.95); display: flex; align-items: center;
    justify-content: center; z-index: 9999; cursor: zoom-out;
    animation: fadeIn 0.3s ease;
  `;

  const img = document.createElement('img');
  img.src = imageSrc;
  img.style.cssText = `
    max-width: 90%; max-height: 90%; object-fit: contain;
    animation: zoomIn 0.3s ease;
  `;

  const closeBtn = document.createElement('button');
  closeBtn.innerHTML = '<i class="fas fa-times"></i>';
  closeBtn.style.cssText = `
    position: absolute; top: 20px; right: 20px; background: rgba(255, 255, 255, 0.9);
    border: none; border-radius: 50%; width: 50px; height: 50px; font-size: 1.5rem;
    cursor: pointer; color: #1e293b; transition: all 0.3s ease;
  `;

  closeBtn.addEventListener('mouseover', () => {
    closeBtn.style.background = '#ffffff';
    closeBtn.style.transform = 'rotate(90deg) scale(1.1)';
  });

  closeBtn.addEventListener('mouseout', () => {
    closeBtn.style.transform = 'rotate(0) scale(1)';
  });

  const closeLightbox = () => {
    lightbox.style.animation = 'fadeOut 0.3s ease';
    setTimeout(() => lightbox.remove(), 300);
  };

  closeBtn.addEventListener('click', closeLightbox);
  lightbox.addEventListener('click', (e) => {
    if (e.target === lightbox) closeLightbox();
  });

  const escHandler = (e: KeyboardEvent) => {
    if (e.key === 'Escape') {
      closeLightbox();
      document.removeEventListener('keydown', escHandler);
    }
  };

  document.addEventListener('keydown', escHandler);

  lightbox.appendChild(img);
  lightbox.appendChild(closeBtn);

  const style = document.createElement('style');
  style.textContent = `
    @keyframes fadeIn { from { opacity: 0; } to { opacity: 1; } }
    @keyframes fadeOut { from { opacity: 1; } to { opacity: 0; } }
    @keyframes zoomIn { from { transform: scale(0.8); opacity: 0; } to { transform: scale(1); opacity: 1; } }
  `;
  document.head.appendChild(style);

  return lightbox;
}

// ========================================
// Rating System for Review Form
// ========================================

function initRatingSystem(): void {
  const ratingInput = document.querySelector('.rating-input');
  if (!ratingInput) return;

  const stars = ratingInput.querySelectorAll('label');
  const inputs = ratingInput.querySelectorAll('input[type="radio"]');

  stars.forEach((label, index) => {
    label.addEventListener('click', () => {
      (inputs[index] as HTMLInputElement).checked = true;
    });

    label.addEventListener('mouseenter', () => {
      const hoverRating = 5 - index;
      stars.forEach((star, starIndex) => {
        (star as HTMLElement).style.color = (5 - starIndex <= hoverRating) ? '#fbbf24' : '#cbd5e1';
      });
    });

    label.addEventListener('mouseleave', () => {
      stars.forEach((star, starIndex) => {
        const isChecked = (inputs[starIndex] as HTMLInputElement).checked;
        (star as HTMLElement).style.color = isChecked ? '#f59e0b' : '#cbd5e1';
      });
    });
  });
}

// ========================================
// Quantity Controls with Validation
// ========================================

function initQuantityControls(): void {
  const quantityInput = document.querySelector('.quantity-input') as HTMLInputElement;
  const quantityMinus = document.querySelector('.quantity-minus');
  const quantityPlus = document.querySelector('.quantity-plus');

  if (!quantityInput) return;

  let maxStock = parseInt(quantityInput.dataset.maxStock || '99');

  const observer = new MutationObserver((mutations) => {
    mutations.forEach((mutation) => {
      if (mutation.type === 'attributes' && mutation.attributeName === 'data-max-stock') {
        maxStock = parseInt(quantityInput.dataset.maxStock || '99');
        quantityInput.max = maxStock.toString();
      }
    });
  });
  observer.observe(quantityInput, { attributes: true });

  quantityMinus?.addEventListener('click', (e) => {
    e.stopPropagation();
    const currentValue = parseInt(quantityInput.value) || 1;
    if (currentValue > 1) {
      quantityInput.value = (currentValue - 1).toString();
      animateButton(quantityMinus as HTMLElement);
    }
  });

  quantityPlus?.addEventListener('click', (e) => {
    e.stopPropagation();
    const currentValue = parseInt(quantityInput.value) || 1;
    if (currentValue < maxStock) {
      quantityInput.value = (currentValue + 1).toString();
      animateButton(quantityPlus as HTMLElement);
    }
  });

  quantityInput.addEventListener('input', () => {
    let value = parseInt(quantityInput.value) || 1;
    if (value < 1) value = 1;
    if (value > maxStock) value = maxStock;
    quantityInput.value = value.toString();
  });

  quantityInput.addEventListener('keydown', (e) => {
    if (e.key === 'ArrowUp') {
      e.preventDefault();
      (quantityPlus as HTMLButtonElement | null)?.click();
    } else if (e.key === 'ArrowDown') {
      e.preventDefault();
      (quantityMinus as HTMLButtonElement | null)?.click();
    }
  });
}

function animateButton(button: HTMLElement): void {
  button.style.transform = 'scale(0.9)';
  setTimeout(() => {
    button.style.transform = 'scale(1)';
  }, 150);
}

// ========================================
// Variant Selection with Pills
// ========================================

function initVariantSelection(): void {
  const container = document.querySelector('[data-product-variants]') as HTMLElement | null;
  if (!container) return;

  const variants: ProductVariant[] = JSON.parse(container.dataset.productVariants || '[]');
  if (variants.length === 0) return;

  const colorPills = document.querySelectorAll('.color-pill');
  const sizePills = document.querySelectorAll('.size-pill');
  const priceEl = document.getElementById('product-price');
  const originalPriceEl = document.getElementById('product-original-price');
  const stockEl = document.getElementById('product-stock-status');
  const variantInput = document.querySelector('input[name="variant_id"]') as HTMLInputElement;
  const colorInput = document.getElementById('selected-color') as HTMLInputElement;
  const sizeInput = document.getElementById('selected-size') as HTMLInputElement;
  const addToCartBtn = document.getElementById('add-to-cart-button') as HTMLButtonElement;
  const quantityInput = document.querySelector('.quantity-input') as HTMLInputElement;

  colorPills.forEach(pill => {
    pill.addEventListener('click', function(this: HTMLElement) {
      colorPills.forEach(p => p.classList.remove('active'));
      this.classList.add('active');
      if (colorInput) colorInput.value = this.dataset.color || '';
      updateVariant();
    });
  });

  sizePills.forEach(pill => {
    pill.addEventListener('click', function(this: HTMLElement) {
      sizePills.forEach(p => p.classList.remove('active'));
      this.classList.add('active');
      if (sizeInput) sizeInput.value = this.dataset.size || '';
      updateVariant();
    });
  });

  function updateVariant(): void {
    const selectedColor = colorInput?.value || null;
    const selectedSize = sizeInput?.value || null;

    const matchedVariant = variants.find(v => {
      const colorMatch = !v.color || v.color === selectedColor || !selectedColor;
      const sizeMatch = !v.size || v.size === selectedSize || !selectedSize;
      return colorMatch && sizeMatch;
    });

    if (matchedVariant && priceEl && stockEl && variantInput && addToCartBtn && quantityInput) {
      priceEl.style.opacity = '0.5';
      setTimeout(() => {
        priceEl.textContent = `KES ${matchedVariant.price.toLocaleString()}`;
        priceEl.style.opacity = '1';
      }, 150);

      if (originalPriceEl) {
        (originalPriceEl as HTMLElement).style.display = 'none';
      }

      if (matchedVariant.quantity > 10) {
        stockEl.innerHTML = '<span class="stock-in"><i class="fas fa-check-circle"></i> In Stock</span>';
      } else if (matchedVariant.quantity > 0) {
        stockEl.innerHTML = `<span class="stock-low"><i class="fas fa-exclamation-circle"></i> Only ${matchedVariant.quantity} left!</span>`;
      } else {
        stockEl.innerHTML = '<span class="stock-out"><i class="fas fa-times-circle"></i> Out of Stock</span>';
      }

      variantInput.value = matchedVariant.id.toString();
      addToCartBtn.disabled = matchedVariant.quantity <= 0;

      quantityInput.max = matchedVariant.quantity.toString();
      quantityInput.dataset.maxStock = matchedVariant.quantity.toString();

      if (parseInt(quantityInput.value) > matchedVariant.quantity) {
        quantityInput.value = matchedVariant.quantity > 0 ? matchedVariant.quantity.toString() : '1';
      }
    }
  }
}

// ========================================
// Review Form Toggle
// ========================================

function initReviewFormToggle(): void {
  const toggleBtn = document.getElementById('toggle-review-form');
  const reviewForm = document.getElementById('review-form');

  if (!toggleBtn || !reviewForm) return;

  toggleBtn.addEventListener('click', (e) => {
    e.preventDefault();
    const isActive = reviewForm.classList.toggle('active');

    toggleBtn.innerHTML = isActive
      ? '<i class="fas fa-times"></i> Cancel'
      : '<i class="fas fa-edit"></i> Write a Review';

    if (isActive) {
      setTimeout(() => {
        reviewForm.scrollIntoView({ behavior: 'smooth', block: 'start' });
      }, 400);
    }
  });
}

// ========================================
// Review Filtering and Sorting
// ========================================

function initReviews(): void {
  const filter = document.getElementById('review-filter') as HTMLSelectElement | null;
  const sort = document.getElementById('review-sort') as HTMLSelectElement | null;
  const list = document.querySelector('.reviews-list') as HTMLElement | null;

  if (!list) return;

  function filterAndSort(): void {
    const filterValue = filter?.value ?? 'all';
    const sortValue = sort?.value ?? 'newest';
    const reviews = Array.from(list.querySelectorAll<HTMLElement>('.review-item'));

    reviews.forEach(review => {
      const rating = review.dataset.rating ?? '';
      const shouldShow = filterValue === 'all' || rating === filterValue;
      review.style.display = shouldShow ? 'block' : 'none';
      if (shouldShow) {
        review.style.animation = 'fadeIn 0.3s ease';
      } else {
        review.style.animation = '';
      }
    });

    const visibleReviews = reviews.filter(r => r.style.display !== 'none');

    visibleReviews.sort((a, b) => {
      const aDate = new Date(a.dataset.date ?? '').getTime();
      const bDate = new Date(b.dataset.date ?? '').getTime();
      const aRating = parseInt(a.dataset.rating ?? '0', 10);
      const bRating = parseInt(b.dataset.rating ?? '0', 10);
      const aHelpful = parseInt(a.dataset.helpful ?? '0', 10);
      const bHelpful = parseInt(b.dataset.helpful ?? '0', 10);

      switch (sortValue) {
        case 'newest': return bDate - aDate;
        case 'oldest': return aDate - bDate;
        case 'highest': return bRating - aRating;
        case 'lowest': return aRating - bRating;
        case 'most_helpful': return bHelpful - aHelpful;
        default: return 0;
      }
    });

    visibleReviews.forEach(review => list.appendChild(review));
  }

  filter?.addEventListener('change', filterAndSort);
  sort?.addEventListener('change', filterAndSort);

  filterAndSort();

  initHelpfulButtons();
  initDeleteReviewButtons();
}

function initHelpfulButtons(): void {
  const buttons = document.querySelectorAll<HTMLButtonElement>('.helpful-btn');

  buttons.forEach(btn => {
    const reviewId = btn.dataset.reviewId;
    const url = btn.dataset.url;
    if (!reviewId || !url) return;

    const initiallyVoted = btn.dataset.voted === 'true';
    if (initiallyVoted) btn.classList.add('voted');

    btn.addEventListener('click', async (e) => {
      e.preventDefault();

      if (btn.dataset.busy === 'true') return;
      btn.dataset.busy = 'true';
      btn.disabled = true;

      const countEl = btn.querySelector<HTMLElement>('.helpful-count');
      const reviewItem = btn.closest<HTMLElement>('.review-item');

      try {
        const response = await fetch(url, {
          method: 'POST',
          headers: {
            'X-CSRFToken': getCsrfToken(),
            'X-Requested-With': 'XMLHttpRequest',
            'Accept': 'application/json',
          },
          credentials: 'same-origin',
        });

        if (response.status === 401 || response.status === 403) {
          showNotification('You need to log in to vote helpful reviews.', 'error');
          return;
        }

        if (!response.ok) {
          showNotification('Could not register vote. Please try again.', 'error');
          return;
        }

        const data = await response.json();

        if (data.success) {
          const newCount = typeof data.new_count !== 'undefined' ? parseInt(data.new_count, 10) : null;

          if (newCount !== null && countEl) {
            countEl.textContent = `(${newCount})`;
          }

          if (reviewItem && newCount !== null) {
            reviewItem.dataset.helpful = String(newCount);
          }

          if (data.voted) {
            btn.classList.add('voted');
            btn.dataset.voted = 'true';
            showNotification('Marked as helpful', 'success');
          } else if (data.unvoted) {
            btn.classList.remove('voted');
            btn.dataset.voted = 'false';
            showNotification('Removed helpful vote', 'success');
          }

          (btn as HTMLElement).style.transform = 'scale(1.05)';
          setTimeout(() => (btn as HTMLElement).style.transform = 'scale(1)', 180);
        } else {
          showNotification(data.message || 'Unable to vote', 'error');
        }
      } catch (err) {
        console.error('Helpful vote error', err);
        showNotification('An error occurred. Please try again.', 'error');
      } finally {
        btn.disabled = false;
        btn.dataset.busy = 'false';
      }
    });
  });
}

function initDeleteReviewButtons(): void {
  document.querySelectorAll<HTMLButtonElement>('.delete-review-btn').forEach(btn => {
    const reviewId = btn.dataset.reviewId;
    if (!reviewId) return;

    btn.addEventListener('click', async (e) => {
      e.preventDefault();
      const ok = confirm('Delete your review? This cannot be undone.');
      if (!ok) return;

      btn.disabled = true;

      try {
        const response = await fetch(`/reviews/${reviewId}/delete/`, {
          method: 'POST',
          headers: {
            'X-CSRFToken': getCsrfToken(),
            'X-Requested-With': 'XMLHttpRequest',
            'Accept': 'application/json',
          },
          credentials: 'same-origin',
        });

        if (!response.ok) {
          showNotification('Could not delete review. Please try again.', 'error');
          return;
        }

        const data = await response.json();
        if (data.success) {
          const reviewItem = btn.closest<HTMLElement>('.review-item');
          if (reviewItem) reviewItem.remove();
          showNotification('Review deleted', 'success');
        } else {
          showNotification(data.message || 'Unable to delete review', 'error');
        }
      } catch (err) {
        console.error('Delete review error', err);
        showNotification('Network error. Try again later.', 'error');
      } finally {
        btn.disabled = false;
      }
    });
  });
}

// ========================================
// Mobile Sticky CTA Visibility
// ========================================

function initMobileStickyCTA(): void {
  const stickyCTA = document.querySelector('.mobile-sticky-cta') as HTMLElement;
  const addToCartForm = document.querySelector('.add-to-cart-form');

  if (!stickyCTA || !addToCartForm) return;

  const observer = new IntersectionObserver(
    (entries) => {
      entries.forEach(entry => {
        stickyCTA.style.transform = entry.isIntersecting ? 'translateY(100%)' : 'translateY(0)';
      });
    },
    { threshold: 0.1 }
  );

  observer.observe(addToCartForm);
  stickyCTA.style.transition = 'transform 0.3s ease';
}

// ========================================
// Main Initialization Function
// ========================================

let productDetailInitialized = false;

export function initProductDetail(): void {
  if (productDetailInitialized) {
    console.warn('[Init] Product detail already initialized – skipping duplicate');
    return;
  }
  productDetailInitialized = true;

  initImageGallery();
  initQuantityControls();
  initVariantSelection();
  initRatingSystem();
  initReviews();
  initReviewFormToggle();
  initMobileStickyCTA();

  console.log('✅ Product detail page initialized');
}