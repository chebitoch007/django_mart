// ========================================
// Product Detail Page - Enhanced TypeScript
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

/**
 * Gets the CSRF token from the DOM
 */
function getCsrfToken(): string {
  const tokenEl = document.querySelector('[name=csrfmiddlewaretoken]') as HTMLInputElement;
  return tokenEl ? tokenEl.value : '';
}

/**
 * Displays a toast notification with icon
 */
function showNotification(message: string, type: 'success' | 'error'): void {
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

/**
 * Updates all cart count indicators on the page
 */
function updateGlobalCartCount(count: number): void {
  document.querySelectorAll('.cart-count').forEach(el => {
    el.textContent = count.toString();
  });

  const cartIcon = document.querySelector('.cart-box');
  if (cartIcon) {
    (cartIcon as HTMLElement).style.transform = 'scale(1.2)';
    setTimeout(() => ((cartIcon as HTMLElement).style.transform = 'scale(1)'), 300);
  }
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

  // Thumbnail click handler with fade transition
  thumbnailItems.forEach(item => {
    const img = item.querySelector('.thumbnail-image') as HTMLImageElement;
    if (img) {
      item.addEventListener('click', (e) => {
        e.preventDefault();
        const newSrc = img.dataset.src || img.src;
        const newLargeSrc = img.dataset.largeSrc || newSrc;

        // Fade out
        mainImage.style.opacity = '0';
        setTimeout(() => {
          mainImage.src = newSrc;
          mainImage.dataset.largeSrc = newLargeSrc;
          (zoomContainer as HTMLElement).style.backgroundImage = `url(${newLargeSrc})`;
          // Fade in
          mainImage.style.opacity = '1';
        }, 200);

        thumbnailItems.forEach(thumb => thumb.classList.remove('active'));
        item.classList.add('active');
      });
    }
  });

  // Image zoom on hover
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

  // Fullscreen functionality
  fullscreenBtn?.addEventListener('click', () => {
    const lightbox = createLightbox(mainImage.dataset.largeSrc || mainImage.src);
    document.body.appendChild(lightbox);
  });

  // Touch swipe for mobile gallery navigation
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
      navigateImages(1); // Swipe left -> next
    } else if (touchEndX > touchStartX + swipeThreshold) {
      navigateImages(-1); // Swipe right -> previous
    }
  }

  function navigateImages(direction: number): void {
    const activeIndex = Array.from(thumbnailItems).findIndex(thumb =>
      thumb.classList.contains('active')
    );
    const newIndex = (activeIndex + direction + thumbnailItems.length) % thumbnailItems.length;
    (thumbnailItems[newIndex] as HTMLElement).click();
  }

  // Add smooth transition to main image
  mainImage.style.transition = 'opacity 0.3s ease';
}

/**
 * Creates a fullscreen lightbox for images
 */
function createLightbox(imageSrc: string): HTMLElement {
  const lightbox = document.createElement('div');
  lightbox.className = 'image-lightbox';
  lightbox.style.cssText = `
    position: fixed;
    top: 0;
    left: 0;
    width: 100%;
    height: 100%;
    background: rgba(0, 0, 0, 0.95);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 9999;
    cursor: zoom-out;
    animation: fadeIn 0.3s ease;
  `;

  const img = document.createElement('img');
  img.src = imageSrc;
  img.style.cssText = `
    max-width: 90%;
    max-height: 90%;
    object-fit: contain;
    animation: zoomIn 0.3s ease;
  `;

  const closeBtn = document.createElement('button');
  closeBtn.innerHTML = '<i class="fas fa-times"></i>';
  closeBtn.style.cssText = `
    position: absolute;
    top: 20px;
    right: 20px;
    background: rgba(255, 255, 255, 0.9);
    border: none;
    border-radius: 50%;
    width: 50px;
    height: 50px;
    font-size: 1.5rem;
    cursor: pointer;
    color: #1e293b;
    transition: all 0.3s ease;
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

  // Keyboard support — use a named handler that we can remove later
    const escHandler = (e: KeyboardEvent) => {
        if (e.key === 'Escape') {
            closeLightbox();
            document.removeEventListener('keydown', escHandler);
        }
    };

    document.addEventListener('keydown', escHandler);


  lightbox.appendChild(img);
  lightbox.appendChild(closeBtn);

  // Add animations
  const style = document.createElement('style');
  style.textContent = `
    @keyframes fadeIn {
      from { opacity: 0; }
      to { opacity: 1; }
    }
    @keyframes fadeOut {
      from { opacity: 1; }
      to { opacity: 0; }
    }
    @keyframes zoomIn {
      from { transform: scale(0.8); opacity: 0; }
      to { transform: scale(1); opacity: 1; }
    }
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
      const rating = 5 - index;
      (inputs[index] as HTMLInputElement).checked = true;
    });

    label.addEventListener('mouseenter', () => {
      const hoverRating = 5 - index;
      stars.forEach((star, starIndex) => {
        if (5 - starIndex <= hoverRating) {
          (star as HTMLElement).style.color = '#fbbf24';
        } else {
          (star as HTMLElement).style.color = '#cbd5e1';
        }
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

  // Observer for dynamic stock changes
  const observer = new MutationObserver((mutations) => {
    mutations.forEach((mutation) => {
      if (mutation.type === 'attributes' && mutation.attributeName === 'data-max-stock') {
        maxStock = parseInt(quantityInput.dataset.maxStock || '99');
        quantityInput.max = maxStock.toString();
      }
    });
  });
  observer.observe(quantityInput, { attributes: true });

  quantityMinus?.addEventListener('click', () => {
    const currentValue = parseInt(quantityInput.value) || 1;
    if (currentValue > 1) {
      quantityInput.value = (currentValue - 1).toString();
      animateButton(quantityMinus as HTMLElement);
    }
  });

  quantityPlus?.addEventListener('click', () => {
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

    // Keyboard support
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

/**
 * Animates button click feedback
 */
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

  // Color pill selection
  colorPills.forEach(pill => {
    pill.addEventListener('click', function(this: HTMLElement) {
      colorPills.forEach(p => p.classList.remove('active'));
      this.classList.add('active');
      if (colorInput) colorInput.value = this.dataset.color || '';
      updateVariant();
    });
  });

  // Size pill selection
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

    // Find matching variant
    const matchedVariant = variants.find(v => {
      const colorMatch = !v.color || v.color === selectedColor || !selectedColor;
      const sizeMatch = !v.size || v.size === selectedSize || !selectedSize;
      return colorMatch && sizeMatch;
    });

    if (matchedVariant && priceEl && stockEl && variantInput && addToCartBtn && quantityInput) {
      // Update price with animation
      priceEl.style.opacity = '0.5';
      setTimeout(() => {
        priceEl.textContent = `KES ${matchedVariant.price.toLocaleString()}`;
        priceEl.style.opacity = '1';
      }, 150);

      if (originalPriceEl) {
        (originalPriceEl as HTMLElement).style.display = 'none';
      }

      // Update stock status with appropriate styling
      if (matchedVariant.quantity > 10) {
        stockEl.innerHTML = '<span class="stock-in"><i class="fas fa-check-circle"></i> In Stock</span>';
      } else if (matchedVariant.quantity > 0) {
        stockEl.innerHTML = `<span class="stock-low"><i class="fas fa-exclamation-circle"></i> Only ${matchedVariant.quantity} left!</span>`;
      } else {
        stockEl.innerHTML = '<span class="stock-out"><i class="fas fa-times-circle"></i> Out of Stock</span>';
      }

      variantInput.value = matchedVariant.id.toString();
      addToCartBtn.disabled = matchedVariant.quantity <= 0;

      // Update quantity input constraints
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

  if (toggleBtn && reviewForm) {
    toggleBtn.addEventListener('click', () => {
      reviewForm.classList.toggle('active');

      if (reviewForm.classList.contains('active')) {
        toggleBtn.innerHTML = '<i class="fas fa-times"></i> Cancel';
        reviewForm.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
      } else {
        toggleBtn.innerHTML = '<i class="fas fa-edit"></i> Write a Review';
      }
    });
  }
}

// ========================================
// Review Filtering and Sorting
// ========================================

function initReviews(): void {
  const filter = document.getElementById('review-filter') as HTMLSelectElement;
  const sort = document.getElementById('review-sort') as HTMLSelectElement;
  const list = document.querySelector('.reviews-list');

  if (!list) return;

  function filterAndSort(): void {
    const filterValue = filter.value;
    const sortValue = sort.value;
    const reviews = Array.from(list.querySelectorAll('.review-item')) as HTMLElement[];

    // 1. Filter reviews
    reviews.forEach(review => {
      const rating = review.dataset.rating;
      const shouldShow = filterValue === 'all' || rating === filterValue;
      review.style.display = shouldShow ? 'block' : 'none';

      // Add fade animation
      if (shouldShow) {
        review.style.animation = 'fadeIn 0.3s ease';
      }
    });

    // 2. Sort visible reviews
    const visibleReviews = reviews.filter(r => r.style.display !== 'none');

    visibleReviews.sort((a, b) => {
      const aDate = new Date(a.dataset.date || 0).getTime();
      const bDate = new Date(b.dataset.date || 0).getTime();
      const aRating = parseInt(a.dataset.rating || '0');
      const bRating = parseInt(b.dataset.rating || '0');
      const aHelpful = parseInt(a.dataset.helpful || '0');
      const bHelpful = parseInt(b.dataset.helpful || '0');

      switch (sortValue) {
        case 'newest': return bDate - aDate;
        case 'oldest': return aDate - bDate;
        case 'highest': return bRating - aRating;
        case 'lowest': return aRating - bRating;
        case 'most_helpful': return bHelpful - aHelpful;
        default: return 0;
      }
    });

    // Re-append in sorted order
    visibleReviews.forEach(review => list.appendChild(review));
  }

  filter?.addEventListener('change', filterAndSort);
  sort?.addEventListener('change', filterAndSort);

  // Helpful button handlers
  initHelpfulButtons();
}

/**
 * Initialize "Helpful" vote buttons on reviews
 */
function initHelpfulButtons(): void {
  document.querySelectorAll('.helpful-btn').forEach(btn => {
    btn.addEventListener('click', async (e) => {
      e.preventDefault();

      if (btn.classList.contains('voted')) {
        showNotification('You already voted this review as helpful', 'error');
        return;
      }

      const url = (btn as HTMLElement).dataset.url;
      if (!url) return;

      try {
        const response = await fetch(url, {
          method: 'POST',
          headers: {
            'X-CSRFToken': getCsrfToken(),
            'X-Requested-With': 'XMLHttpRequest'
          }
        });

        const data = await response.json();

        if (data.success) {
          btn.classList.add('voted');
          const countEl = btn.querySelector('.helpful-count');
          if (countEl) {
            countEl.textContent = `(${data.new_count})`;
          }

          // Update data attribute for sorting
          const reviewItem = btn.closest('.review-item') as HTMLElement;
          if (reviewItem) {
            reviewItem.dataset.helpful = data.new_count;
          }

          showNotification('Thank you for your feedback!', 'success');

            // Animate the button
            (btn as HTMLElement).style.transform = 'scale(1.1)';
            setTimeout(() => {
                (btn as HTMLElement).style.transform = 'scale(1)';
                }, 200);

        } else {
          showNotification(data.message || 'Unable to vote', 'error');
        }
      } catch (error) {
        showNotification('An error occurred. Please try again.', 'error');
      }
    });
  });
}

// ========================================
// Stock Notifications
// ========================================

function initStockNotifications(): void {
  const notifyBtn = document.querySelector('.notify-btn');

  notifyBtn?.addEventListener('click', async () => {
    const productId = (notifyBtn as HTMLElement).dataset.productId;
    const email = prompt('Enter your email to be notified when this product is back in stock:');

    if (!email) return;

    // Email validation
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    if (!emailRegex.test(email)) {
      showNotification('Please enter a valid email address.', 'error');
      return;
    }

    try {
      const response = await fetch('/notifications/stock/', {
        method: 'POST',
        headers: {
          'X-CSRFToken': getCsrfToken(),
          'Content-Type': 'application/json',
          'X-Requested-With': 'XMLHttpRequest'
        },
        body: JSON.stringify({ product_id: productId, email: email })
      });

      const data = await response.json();

      if (data.success) {
        showNotification(data.message || 'You will be notified when this item is back in stock!', 'success');
        (notifyBtn as HTMLButtonElement).disabled = true;
        (notifyBtn as HTMLElement).style.opacity = '0.6';
      } else {
        showNotification(data.message || 'Unable to register notification.', 'error');
      }
    } catch (error) {
      showNotification('An error occurred. Please try again later.', 'error');
    }
  });
}

// ========================================
// Social Sharing (Optional Enhancement)
// ========================================

function initSocialSharing(): void {
  const shareButtons = document.querySelectorAll('.share-btn');

  shareButtons.forEach(btn => {
    btn.addEventListener('click', (e) => {
      e.preventDefault();
      const platform = (btn as HTMLElement).dataset.platform;
      const url = encodeURIComponent(window.location.href);
      const title = encodeURIComponent(document.title);

      let shareUrl = '';

      switch (platform) {
        case 'facebook':
          shareUrl = `https://www.facebook.com/sharer/sharer.php?u=${url}`;
          break;
        case 'twitter':
          shareUrl = `https://twitter.com/intent/tweet?url=${url}&text=${title}`;
          break;
        case 'whatsapp':
          shareUrl = `https://wa.me/?text=${title}%20${url}`;
          break;
        case 'pinterest':
          const image = (document.getElementById('main-product-image') as HTMLImageElement)?.src || '';
          shareUrl = `https://pinterest.com/pin/create/button/?url=${url}&media=${encodeURIComponent(image)}&description=${title}`;
          break;
        case 'copy':
          navigator.clipboard.writeText(window.location.href).then(() => {
            showNotification('Link copied to clipboard!', 'success');
          });
          return;
      }

      if (shareUrl) {
        window.open(shareUrl, '_blank', 'width=600,height=400');
      }
    });
  });
}

// ========================================
// Questions Section (Optional)
// ========================================

function initQuestions(): void {
  const questionForm = document.getElementById('question-form');
  const toggleQuestionBtn = document.getElementById('toggle-question-form');

  if (toggleQuestionBtn && questionForm) {
    toggleQuestionBtn.addEventListener('click', () => {
      questionForm.classList.toggle('active');

      if (questionForm.classList.contains('active')) {
        toggleQuestionBtn.textContent = 'Cancel';
        questionForm.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
      } else {
        toggleQuestionBtn.textContent = 'Ask a Question';
      }
    });
  }
}

// ========================================
// Lazy Loading for Images
// ========================================

function initLazyLoading(): void {
  const lazyImages = document.querySelectorAll('img[data-src]');

  if ('IntersectionObserver' in window) {
    const imageObserver = new IntersectionObserver((entries, observer) => {
      entries.forEach(entry => {
        if (entry.isIntersecting) {
          const img = entry.target as HTMLImageElement;
          img.src = img.dataset.src || '';
          img.classList.add('loaded');
          observer.unobserve(img);
        }
      });
    });

    lazyImages.forEach(img => imageObserver.observe(img));
  } else {
    // Fallback for older browsers
    lazyImages.forEach(img => {
      const image = img as HTMLImageElement;
      image.src = image.dataset.src || '';
    });
  }
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
        if (entry.isIntersecting) {
          stickyCTA.style.transform = 'translateY(100%)';
        } else {
          stickyCTA.style.transform = 'translateY(0)';
        }
      });
    },
    { threshold: 0.1 }
  );

  observer.observe(addToCartForm);

  // Add smooth transition
  stickyCTA.style.transition = 'transform 0.3s ease';
}

// ========================================
// HTMX Event Handler for Cart Actions
// ========================================

function initHTMXHandlers(): void {
  document.body.addEventListener('htmx:afterRequest', (event: any) => {
    if (!event.detail || !event.detail.elt) return;

    const form = event.detail.elt.closest('.add-to-cart-form');

    if (form && event.detail.xhr.status === 200) {
      try {
        const response = JSON.parse(event.detail.xhr.responseText);

        if (response.success) {
          updateGlobalCartCount(response.cart_total_items);
          showNotification(response.message || 'Item added to cart!', 'success');

          // Visual feedback on button
          const btn = form.querySelector('.add-to-cart-btn') as HTMLButtonElement;
          if (btn) {
            const originalBg = btn.style.background;
            btn.style.background = '#16a34a';
            setTimeout(() => {
              btn.style.background = originalBg;
            }, 500);
          }
        } else {
          showNotification(response.message || 'Unable to add item to cart', 'error');
        }
      } catch (e) {
        // Fallback if response isn't JSON
        showNotification('Item added to cart!', 'success');
      }
    } else if (event.detail.failed) {
      showNotification('Failed to add item to cart. Please try again.', 'error');
    }
  });

  // Handle HTMX errors
  document.body.addEventListener('htmx:responseError', () => {
    showNotification('A network error occurred. Please check your connection.', 'error');
  });
}

// ========================================
// Scroll Animation for Reviews
// ========================================

function initScrollAnimations(): void {
  const animatedElements = document.querySelectorAll('.review-item, .product-info-card');

  const observer = new IntersectionObserver(
    (entries) => {
      entries.forEach(entry => {
        if (entry.isIntersecting) {
          entry.target.classList.add('fade-in-up');
        }
      });
    },
    { threshold: 0.1 }
  );

  animatedElements.forEach(el => observer.observe(el));

  // Add animation styles
  const style = document.createElement('style');
  style.textContent = `
    .fade-in-up {
      animation: fadeInUp 0.6s ease forwards;
    }
    @keyframes fadeInUp {
      from {
        opacity: 0;
        transform: translateY(20px);
      }
      to {
        opacity: 1;
        transform: translateY(0);
      }
    }
  `;
  document.head.appendChild(style);
}

// ========================================
// Main Initialization Function
// ========================================

export function initProductDetail(): void {
  // Core functionality
  initImageGallery();
  initQuantityControls();
  initVariantSelection();
  initRatingSystem();

  // Reviews
  initReviews();
  initReviewFormToggle();

  // Additional features
  initStockNotifications();
  initSocialSharing();
  initQuestions();

  // Enhancements
  initLazyLoading();
  initMobileStickyCTA();
  initScrollAnimations();

  // HTMX integration
  initHTMXHandlers();

  // Log initialization
  console.log('✓ Product detail page initialized');
}

// Auto-initialize if this is the only script
if (typeof window !== 'undefined') {
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initProductDetail);
  } else {
    initProductDetail();
  }
}