import { ProductVariant } from './types';

export function initProductDetail(): void {
  // Enhanced image gallery with zoom and swipe
  initImageGallery();

  // Enhanced rating system
  initRatingSystem();

  // Quantity controls with validation
  initQuantityControls();

  // Variant selection
  initVariantSelection();

  // Dropshipping toggle
  initDropshippingToggle();

  // Product reviews
  initReviews();

  // Social sharing
  initSocialSharing();

  // Product questions
  initQuestions();

  // Stock notifications
  initStockNotifications();
}

function initImageGallery(): void {
  const mainImage = document.getElementById('main-product-image') as HTMLImageElement;
  const thumbnailItems = document.querySelectorAll('.thumbnail-item');
  const zoomContainer = document.getElementById('image-zoom-container');

  // Thumbnail click handler
  thumbnailItems.forEach(item => {
    const img = item.querySelector('.thumbnail-image') as HTMLImageElement;
    if (img && mainImage) {
      item.addEventListener('click', () => {
        const newSrc = img.dataset.largeSrc || img.dataset.src || img.src;
        mainImage.src = newSrc;

        // Update active thumbnail
        thumbnailItems.forEach(thumb => thumb.classList.remove('active'));
        item.classList.add('active');

        // Update zoom if available
        if (zoomContainer && img.dataset.largeSrc) {
          zoomContainer.style.backgroundImage = `url(${img.dataset.largeSrc})`;
        }
      });
    }
  });

  // Image zoom functionality
  if (mainImage && zoomContainer) {
    mainImage.addEventListener('mousemove', (e) => {
      const { left, top, width, height } = mainImage.getBoundingClientRect();
      const x = ((e.clientX - left) / width) * 100;
      const y = ((e.clientY - top) / height) * 100;
      zoomContainer.style.backgroundPosition = `${x}% ${y}%`;
    });

    mainImage.addEventListener('mouseenter', () => {
      zoomContainer.classList.add('active');
    });

    mainImage.addEventListener('mouseleave', () => {
      zoomContainer.classList.remove('active');
    });
  }

  // Touch swipe for mobile
  let touchStartX = 0;
  let touchEndX = 0;

  mainImage?.addEventListener('touchstart', (e) => {
    touchStartX = e.changedTouches[0].screenX;
  });

  mainImage?.addEventListener('touchend', (e) => {
    touchEndX = e.changedTouches[0].screenX;
    handleSwipe();
  });

  function handleSwipe(): void {
    const swipeThreshold = 50;
    if (touchEndX < touchStartX - swipeThreshold) {
      // Swipe left - next image
      navigateImages(1);
    } else if (touchEndX > touchStartX + swipeThreshold) {
      // Swipe right - previous image
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
}

function initRatingSystem(): void {
  const ratingInput = document.querySelector('.rating-input');
  if (!ratingInput) return;

  const stars = ratingInput.querySelectorAll('label');
  const hiddenInput = ratingInput.querySelector('input[type="hidden"]') as HTMLInputElement;

  stars.forEach((label, index) => {
    label.addEventListener('click', () => {
      const rating = 5 - index; // Since stars are in reverse order

      // Update visual state
      stars.forEach((star, starIndex) => {
        if (5 - starIndex <= rating) {
          (star as HTMLElement).style.color = '#f59e0b';
        } else {
          (star as HTMLElement).style.color = '#cbd5e1';
        }
      });

      // Update hidden input
      if (hiddenInput) {
        hiddenInput.value = rating.toString();
      }
    });

    // Hover effects
    label.addEventListener('mouseenter', () => {
      const hoverRating = 5 - index;
      stars.forEach((star, starIndex) => {
        if (5 - starIndex <= hoverRating) {
          (star as HTMLElement).style.color = '#fbbf24';
        }
      });
    });

    label.addEventListener('mouseleave', () => {
      const currentRating = hiddenInput ? parseInt(hiddenInput.value) : 0;
      stars.forEach((star, starIndex) => {
        if (5 - starIndex <= currentRating) {
          (star as HTMLElement).style.color = '#f59e0b';
        } else {
          (star as HTMLElement).style.color = '#cbd5e1';
        }
      });
    });
  });
}

function initQuantityControls(): void {
  const quantityInput = document.querySelector('input[name="quantity"]') as HTMLInputElement;
  const quantityMinus = document.querySelector('.quantity-minus');
  const quantityPlus = document.querySelector('.quantity-plus');
  const maxStock = parseInt(quantityInput?.max || '99');

  if (quantityMinus && quantityInput) {
    quantityMinus.addEventListener('click', () => {
      const currentValue = parseInt(quantityInput.value) || 1;
      if (currentValue > 1) {
        quantityInput.value = (currentValue - 1).toString();
        updateAddToCartButton(parseInt(quantityInput.value));
      }
    });
  }

  if (quantityPlus && quantityInput) {
    quantityPlus.addEventListener('click', () => {
      const currentValue = parseInt(quantityInput.value) || 1;
      if (currentValue < maxStock) {
        quantityInput.value = (currentValue + 1).toString();
        updateAddToCartButton(parseInt(quantityInput.value));
      }
    });
  }

  // Direct input validation
  quantityInput?.addEventListener('input', () => {
    let value = parseInt(quantityInput.value) || 1;
    if (value < 1) value = 1;
    if (value > maxStock) value = maxStock;
    quantityInput.value = value.toString();
    updateAddToCartButton(value);
  });
}

function updateAddToCartButton(quantity: number): void {
  const addToCartBtn = document.querySelector('.add-to-cart-btn') as HTMLButtonElement;
  const maxStock = parseInt(addToCartBtn?.dataset.maxStock || '99');

  if (addToCartBtn) {
    if (quantity >= maxStock) {
      addToCartBtn.textContent = 'Maximum Quantity Reached';
      addToCartBtn.disabled = true;
    } else {
      addToCartBtn.textContent = `Add ${quantity} to Cart`;
      addToCartBtn.disabled = false;
    }
  }
}

function initVariantSelection(): void {
  const variantSelects = document.querySelectorAll('.variant-select');

  variantSelects.forEach(select => {
    select.addEventListener('change', updateVariant);
  });

  function updateVariant(): void {
    const selectedOptions: Record<string, string> = {};

    variantSelects.forEach(select => {
      const name = (select as HTMLSelectElement).name;
      const value = (select as HTMLSelectElement).value;
      selectedOptions[name] = value;
    });

    // Find matching variant and update price, stock, image
    const productElement = document.querySelector('[data-product-variants]');
    if (productElement) {
      const variants: ProductVariant[] = JSON.parse(
        productElement.getAttribute('data-product-variants') || '[]'
      );

      const matchedVariant = variants.find(variant =>
        Object.keys(selectedOptions).every(key =>
          variant.attributes[key] === selectedOptions[key]
        )
      );

      if (matchedVariant) {
        updateProductDisplay(matchedVariant);
      }
    }
  }

  function updateProductDisplay(variant: ProductVariant): void {
    // Update price
    const priceElement = document.querySelector('.current-price');
    if (priceElement) {
      priceElement.textContent = `KES ${variant.price.toLocaleString()}`;
    }

    // Update stock
    const stockElement = document.querySelector('.stock-status');
    if (stockElement) {
      if (variant.stock > 10) {
        stockElement.innerHTML = '<span class="stock-in">In Stock</span>';
      } else if (variant.stock > 0) {
        stockElement.innerHTML = `<span class="stock-low">Only ${variant.stock} left!</span>`;
      } else {
        stockElement.innerHTML = '<span class="stock-out">Out of Stock</span>';
      }
    }

    // Update variant ID in form
    const variantInput = document.querySelector('input[name="variant_id"]') as HTMLInputElement;
    if (variantInput) {
      variantInput.value = variant.id.toString();
    }

    // Update add to cart button
    const addToCartBtn = document.querySelector('.add-to-cart-btn') as HTMLButtonElement;
    if (addToCartBtn) {
      addToCartBtn.disabled = variant.stock <= 0;
    }
  }
}

function initDropshippingToggle(): void {
  const dropshipCheckbox = document.getElementById('id_is_dropship') as HTMLInputElement;
  const dropshipFields = document.getElementById('dropship-fields');

  if (dropshipCheckbox && dropshipFields) {
    dropshipFields.style.display = dropshipCheckbox.checked ? 'block' : 'none';

    dropshipCheckbox.addEventListener('change', () => {
      dropshipFields.style.display = dropshipCheckbox.checked ? 'block' : 'none';
    });
  }
}

function initReviews(): void {
  // Review filtering and sorting
  const reviewFilter = document.getElementById('review-filter') as HTMLSelectElement;
  const reviewSort = document.getElementById('review-sort') as HTMLSelectElement;

  reviewFilter?.addEventListener('change', filterReviews);
  reviewSort?.addEventListener('change', sortReviews);

  // Review helpfulness
  document.querySelectorAll('.helpful-btn').forEach(btn => {
    btn.addEventListener('click', markHelpful);
  });
}

function filterReviews(): void {
  const filterValue = (document.getElementById('review-filter') as HTMLSelectElement).value;
  const reviews = document.querySelectorAll('.review-item');

  reviews.forEach(review => {
    const rating = parseInt(review.getAttribute('data-rating') || '0');

    if (filterValue === 'all' || rating === parseInt(filterValue)) {
      (review as HTMLElement).style.display = 'block';
    } else {
      (review as HTMLElement).style.display = 'none';
    }
  });
}

function sortReviews(): void {
  const sortValue = (document.getElementById('review-sort') as HTMLSelectElement).value;
  const reviewsContainer = document.querySelector('.reviews-list');
  const reviews = Array.from(document.querySelectorAll('.review-item'));

  reviews.sort((a, b) => {
    const aDate = new Date(a.getAttribute('data-date') || '');
    const bDate = new Date(b.getAttribute('data-date') || '');
    const aRating = parseInt(a.getAttribute('data-rating') || '0');
    const bRating = parseInt(b.getAttribute('data-rating') || '0');
    const aHelpful = parseInt(a.getAttribute('data-helpful') || '0');
    const bHelpful = parseInt(b.getAttribute('data-helpful') || '0');

    switch (sortValue) {
      case 'newest':
        return bDate.getTime() - aDate.getTime();
      case 'oldest':
        return aDate.getTime() - bDate.getTime();
      case 'highest':
        return bRating - aRating;
      case 'lowest':
        return aRating - bRating;
      case 'most_helpful':
        return bHelpful - aHelpful;
      default:
        return 0;
    }
  });

  // Reappend sorted reviews
  reviews.forEach(review => reviewsContainer?.appendChild(review));
}

function markHelpful(event: Event): void {
  const button = event.target as HTMLButtonElement;
  const reviewId = button.getAttribute('data-review-id');

  if (reviewId && !button.classList.contains('voted')) {
    // Send API request to mark helpful
    fetch(`/reviews/${reviewId}/helpful/`, {
      method: 'POST',
      headers: {
        'X-CSRFToken': (document.querySelector('[name=csrfmiddlewaretoken]') as HTMLInputElement).value,
        'X-Requested-With': 'XMLHttpRequest'
      }
    })
    .then(response => response.json())
    .then(data => {
      if (data.success) {
        button.classList.add('voted');
        const countElement = button.querySelector('.helpful-count');
        if (countElement) {
          const currentCount = parseInt(countElement.textContent || '0');
          countElement.textContent = (currentCount + 1).toString();
        }
      }
    })
    .catch(error => {
      console.error('Failed to mark review as helpful:', error);
    });
  }
}

function initSocialSharing(): void {
  const shareButtons = document.querySelectorAll('.share-btn');

  shareButtons.forEach(btn => {
    btn.addEventListener('click', (e) => {
      e.preventDefault();
      const platform = btn.getAttribute('data-platform');
      shareProduct(platform);
    });
  });

  function shareProduct(platform: string | null): void {
    const productName = document.querySelector('.product-title')?.textContent || '';
    const productUrl = window.location.href;
    const productImage = (document.querySelector('.main-image') as HTMLImageElement)?.src || '';

    let shareUrl = '';

    switch (platform) {
      case 'facebook':
        shareUrl = `https://www.facebook.com/sharer/sharer.php?u=${encodeURIComponent(productUrl)}`;
        break;
      case 'twitter':
        shareUrl = `https://twitter.com/intent/tweet?text=${encodeURIComponent(productName)}&url=${encodeURIComponent(productUrl)}`;
        break;
      case 'pinterest':
        shareUrl = `https://pinterest.com/pin/create/button/?url=${encodeURIComponent(productUrl)}&media=${encodeURIComponent(productImage)}&description=${encodeURIComponent(productName)}`;
        break;
      case 'whatsapp':
        shareUrl = `https://wa.me/?text=${encodeURIComponent(`${productName} ${productUrl}`)}`;
        break;
      default:
        // Web Share API
        if (navigator.share) {
          navigator.share({
            title: productName,
            text: `Check out this product: ${productName}`,
            url: productUrl,
          });
          return;
        }
    }

    if (shareUrl) {
      window.open(shareUrl, '_blank', 'width=600,height=400');
    }
  }
}

function initQuestions(): void {
  const questionForm = document.getElementById('question-form');
  const questionToggle = document.getElementById('toggle-question-form');

  questionToggle?.addEventListener('click', () => {
    questionForm?.classList.toggle('hidden');
  });

  // Question voting
  document.querySelectorAll('.question-vote-btn').forEach(btn => {
    btn.addEventListener('click', voteOnQuestion);
  });
}

function voteOnQuestion(event: Event): void {
  const button = event.target as HTMLButtonElement;
  const questionId = button.getAttribute('data-question-id');
  const voteType = button.getAttribute('data-vote-type');

  if (questionId && voteType && !button.classList.contains('voted')) {
    fetch(`/questions/${questionId}/vote/`, {
      method: 'POST',
      headers: {
        'X-CSRFToken': (document.querySelector('[name=csrfmiddlewaretoken]') as HTMLInputElement).value,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ vote_type: voteType })
    })
    .then(response => response.json())
    .then(data => {
      if (data.success) {
        button.classList.add('voted');
        const scoreElement = document.querySelector(`[data-question-score="${questionId}"]`);
        if (scoreElement) {
          scoreElement.textContent = data.new_score.toString();
        }
      }
    })
    .catch(error => {
      console.error('Failed to vote on question:', error);
    });
  }
}

function initStockNotifications(): void {
  const notifyBtn = document.querySelector('.notify-btn');

  notifyBtn?.addEventListener('click', () => {
    const productId = notifyBtn.getAttribute('data-product-id');

    if (productId) {
      const email = prompt('Enter your email to be notified when this product is back in stock:');
      if (email && /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
        fetch('/notifications/stock/', {
          method: 'POST',
          headers: {
            'X-CSRFToken': (document.querySelector('[name=csrfmiddlewaretoken]') as HTMLInputElement).value,
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({
            product_id: productId,
            email: email
          })
        })
        .then(response => response.json())
        .then(data => {
          if (data.success) {
            alert('You will be notified when this product is back in stock!');
          } else {
            alert('Failed to set up notification. Please try again.');
          }
        })
        .catch(error => {
          console.error('Failed to set up stock notification:', error);
          alert('An error occurred. Please try again.');
        });
      }
    }
  });
}

// Export additional functions for use in other modules
export {
  initImageGallery,
  initRatingSystem,
  initVariantSelection
};