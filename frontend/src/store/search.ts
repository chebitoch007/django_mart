import { StoreUtils } from './base';
import { SearchSuggestion } from './types';

export function initSearch(): void {
  console.log('Initializing enhanced search...');

  // Core search functionality
  initSearchFilters();
  initSearchSuggestions();
  initSearchResults();
  initSearchAnalytics();
  initSearchHistory();
  initVoiceSearch();
  initSearchSorting();
  initSearchPagination();
  initSearchSpellingCorrection();
  initSearchFacets();
}

function initSearchFilters(): void {
  const filterToggle = document.getElementById('filterToggle');
  const filterContent = document.getElementById('filterContent');
  const priceRange = document.getElementById('priceRange') as HTMLInputElement;
  const maxPriceInput = document.getElementById('maxPriceInput') as HTMLInputElement;
  const priceDisplay = document.getElementById('priceDisplay');
  const applyPriceBtn = document.getElementById('applyPriceBtn');
  const inStockCheckbox = document.getElementById('inStock') as HTMLInputElement;
  const sortSelect = document.getElementById('sortSelect') as HTMLSelectElement;

  // Mobile filter toggle
  if (filterToggle && filterContent) {
    filterToggle.addEventListener('click', () => {
      filterContent.classList.toggle('expanded');
      filterToggle.innerHTML = filterContent.classList.contains('expanded') ?
        '<i class="fas fa-times"></i> Hide Filters' :
        '<i class="fas fa-filter"></i> Show Filters';
    });
  }

  // Real-time price filter with debounce
  if (priceRange && priceDisplay) {
    priceRange.addEventListener('input', StoreUtils.debounce(() => {
      const value = priceRange.value;
      priceDisplay.textContent = StoreUtils.formatPrice(parseInt(value));
      if (maxPriceInput) maxPriceInput.value = value;

      // Auto-apply after user stops sliding
      updateSearchFilter('max_price', value);
    }, 500));
  }

  // Price input with validation
  if (maxPriceInput && priceRange && priceDisplay) {
    maxPriceInput.addEventListener('input', StoreUtils.debounce(() => {
      let value = parseInt(maxPriceInput.value);
      if (isNaN(value)) value = 0;
      if (value > 10000) value = 10000;
      if (value < 0) value = 0;

      maxPriceInput.value = value.toString();
      priceRange.value = value.toString();
      priceDisplay.textContent = StoreUtils.formatPrice(value);
    }, 500));
  }

  // Apply price filter
  if (applyPriceBtn && maxPriceInput) {
    applyPriceBtn.addEventListener('click', () => {
      const max = maxPriceInput.value || '10000';
      updateSearchFilter('max_price', max);
    });
  }

  // Instant stock filter
  if (inStockCheckbox) {
    inStockCheckbox.addEventListener('change', StoreUtils.debounce(() => {
      const value = inStockCheckbox.checked ? 'true' : '';
      updateSearchFilter('in_stock', value);
    }, 300));
  }

  // Enhanced sorting
  if (sortSelect) {
    sortSelect.addEventListener('change', StoreUtils.debounce(() => {
      updateSearchFilter('sort', sortSelect.value);
    }, 300));
  }

  // Category filters
  initCategoryFilters();
}

function initCategoryFilters(): void {
  const categoryLinks = document.querySelectorAll('.category-filter');

  categoryLinks.forEach(link => {
    link.addEventListener('click', (e) => {
      e.preventDefault();
      const category = link.getAttribute('data-category');
      if (category) {
        updateSearchFilter('category', category);
      }
    });
  });
}

function updateSearchFilter(param: string, value: string): void {
  const url = new URL(window.location.href);

  if (value) {
    url.searchParams.set(param, value);
  } else {
    url.searchParams.delete(param);
  }

  // Use History API for smooth navigation
  if (window.history && window.history.replaceState) {
    window.history.replaceState({}, '', url.toString());
  }

  // Reload search results via AJAX
  reloadSearchResults();
}

function reloadSearchResults(): void {
  const searchResults = document.getElementById('search-results');
  const loadingIndicator = document.getElementById('search-loading');

  if (searchResults && loadingIndicator) {
    // Show loading state
    searchResults.classList.add('loading');
    loadingIndicator.classList.remove('hidden');

    // Get current URL with filters
    const url = new URL(window.location.href);
    url.searchParams.set('ajax', 'true');

    // Fetch updated results
    fetch(url.toString())
      .then(response => response.text())
      .then(html => {
        const parser = new DOMParser();
        const doc = parser.parseFromString(html, 'text/html');
        const newResults = doc.getElementById('search-results');

        if (newResults) {
          searchResults.innerHTML = newResults.innerHTML;

          // Re-initialize product interactions
          initSearchResults();
        }
      })
      .catch(error => {
        console.error('Failed to reload search results:', error);
        showSearchError();
      })
      .finally(() => {
        searchResults.classList.remove('loading');
        loadingIndicator.classList.add('hidden');
      });
  }
}

function initSearchSuggestions(): void {
  const searchInput = document.querySelector('input[name="q"]') as HTMLInputElement;
  const suggestionsContainer = document.getElementById('search-suggestions');

  if (!searchInput || !suggestionsContainer) return;

  let abortController: AbortController | null = null;

  searchInput.addEventListener('input', StoreUtils.debounce(async () => {
    const query = searchInput.value.trim();

    // Cancel previous request
    if (abortController) {
      abortController.abort();
    }

    if (query.length < 2) {
      suggestionsContainer.classList.add('hidden');
      return;
    }

    // Show loading state
    suggestionsContainer.innerHTML = '<div class="suggestion-loading"><i class="fas fa-spinner fa-spin"></i> Searching...</div>';
    suggestionsContainer.classList.remove('hidden');

    // Create new abort controller
    abortController = new AbortController();

    try {
      const response = await fetch(`/api/search/suggestions?q=${encodeURIComponent(query)}`, {
        signal: abortController.signal
      });

      const suggestions: SearchSuggestion[] = await response.json();
      renderSearchSuggestions(suggestions, query);

    } catch (error: any) {
      if (error.name !== 'AbortError') {
        console.error('Failed to fetch search suggestions:', error);
        suggestionsContainer.classList.add('hidden');
      }
    }
  }, 300));

  // Keyboard navigation for suggestions
  searchInput.addEventListener('keydown', (e) => {
    if (!suggestionsContainer.classList.contains('hidden')) {
      const suggestions = suggestionsContainer.querySelectorAll('.suggestion-item');
      const currentFocus = suggestionsContainer.querySelector('.suggestion-item.focused');

      let index = Array.from(suggestions).indexOf(currentFocus as Element);

      switch (e.key) {
        case 'ArrowDown':
          e.preventDefault();
          index = (index + 1) % suggestions.length;
          break;
        case 'ArrowUp':
          e.preventDefault();
          index = index <= 0 ? suggestions.length - 1 : index - 1;
          break;
        case 'Enter':
          e.preventDefault();
          if (currentFocus) {
            (currentFocus as HTMLElement).click();
          }
          return;
        case 'Escape':
          suggestionsContainer.classList.add('hidden');
          return;
      }

      // Update focus
      suggestions.forEach(s => s.classList.remove('focused'));
      if (suggestions[index]) {
        suggestions[index].classList.add('focused');
      }
    }
  });

  // Hide suggestions when clicking outside
  document.addEventListener('click', (e) => {
    if (!suggestionsContainer.contains(e.target as Node) && e.target !== searchInput) {
      suggestionsContainer.classList.add('hidden');
    }
  });
}

function renderSearchSuggestions(suggestions: SearchSuggestion[], query: string): void {
  const container = document.getElementById('search-suggestions');
  if (!container) return;

  if (suggestions.length === 0) {
    container.innerHTML = `
      <div class="suggestion-item">
        <i class="fas fa-search"></i>
        <span>No results found for "${query}"</span>
      </div>
    `;
    return;
  }

  const suggestionsHTML = suggestions.map(suggestion => `
    <div class="suggestion-item ${suggestion.type}" data-url="${suggestion.url}">
      <div class="suggestion-icon">
        ${getSuggestionIcon(suggestion.type)}
      </div>
      <div class="suggestion-content">
        <div class="suggestion-title">${highlightQuery(suggestion.name, query)}</div>
        ${suggestion.category ? `<div class="suggestion-category">${suggestion.category}</div>` : ''}
        ${suggestion.price ? `<div class="suggestion-price">${suggestion.price}</div>` : ''}
      </div>
      ${suggestion.type === 'search' ? '<i class="fas fa-arrow-right suggestion-arrow"></i>' : ''}
    </div>
  `).join('');

  container.innerHTML = suggestionsHTML;

  // Add click handlers
  container.querySelectorAll('.suggestion-item').forEach(item => {
    item.addEventListener('click', () => {
      const url = item.getAttribute('data-url');
      if (url) {
        window.location.href = url;
      } else {
        // For search suggestions, update the input and submit
        const searchInput = document.querySelector('input[name="q"]') as HTMLInputElement;
        const title = item.querySelector('.suggestion-title')?.textContent;
        if (title && searchInput) {
          searchInput.value = title;
          searchInput.form?.submit();
        }
      }
    });
  });

  container.classList.remove('hidden');
}

function getSuggestionIcon(type: string): string {
  switch (type) {
    case 'product': return '<i class="fas fa-cube"></i>';
    case 'category': return '<i class="fas fa-folder"></i>';
    case 'trending': return '<i class="fas fa-fire"></i>';
    case 'brand': return '<i class="fas fa-tag"></i>';
    default: return '<i class="fas fa-search"></i>';
  }
}

function highlightQuery(text: string, query: string): string {
  const regex = new RegExp(`(${query.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')})`, 'gi');
  return text.replace(regex, '<mark>$1</mark>');
}

function initSearchResults(): void {
  const resultsContainer = document.getElementById('search-results');

  if (!resultsContainer) return;

  // Enhanced product interactions
  const productCards = resultsContainer.querySelectorAll('.product-card');

  productCards.forEach(card => {
    // Quick view
    const quickViewBtn = card.querySelector('.quick-view-btn');
    quickViewBtn?.addEventListener('click', (e) => {
      e.preventDefault();
      const productId = card.getAttribute('data-product-id');
      if (productId) {
        // Import and use quick view functionality from product-list
        import('./product-list').then(module => {
          module.initQuickView();
          // You would need to expose openQuickView from product-list
        });
      }
    });

    // Wishlist
    const wishlistBtn = card.querySelector('.wishlist-btn');
    wishlistBtn?.addEventListener('click', (e) => {
      e.preventDefault();
      const productId = card.getAttribute('data-product-id');
      if (productId) {
        document.dispatchEvent(new CustomEvent('wishlist:toggle', {
          detail: {
            product: { id: parseInt(productId) },
            action: wishlistBtn.classList.contains('active') ? 'remove' : 'add'
          }
        }));
      }
    });
  });

  // Search result analytics
  trackSearchResultInteractions();
}

function trackSearchResultInteractions(): void {
  const resultsContainer = document.getElementById('search-results');
  const query = new URLSearchParams(window.location.search).get('q');

  if (!resultsContainer || !query) return;

  const observer = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
      if (entry.isIntersecting) {
        const productCard = entry.target as HTMLElement;
        const productId = productCard.getAttribute('data-product-id');
        const position = Array.from(resultsContainer.querySelectorAll('.product-card')).indexOf(productCard) + 1;

        if (productId && !productCard.classList.contains('impression-tracked')) {
          productCard.classList.add('impression-tracked');

          // Track search impression
          document.dispatchEvent(new CustomEvent('analytics:searchImpression', {
            detail: {
              query,
              productId: parseInt(productId),
              position,
              page: getCurrentPage()
            }
          }));
        }
      }
    });
  }, {
    threshold: 0.5,
    rootMargin: '100px 0px'
  });

  resultsContainer.querySelectorAll('.product-card').forEach(card => {
    observer.observe(card);
  });
}

function initSearchAnalytics(): void {
  const query = new URLSearchParams(window.location.search).get('q');

  if (query) {
    // Track search query
    document.dispatchEvent(new CustomEvent('analytics:searchQuery', {
      detail: {
        query,
        resultsCount: getResultsCount(),
        filters: getActiveFilters()
      }
    }));

    // Save to search history
    saveSearchHistory(query);
  }
}

function initSearchHistory(): void {
  const searchInput = document.querySelector('input[name="q"]') as HTMLInputElement;
  const historyContainer = document.getElementById('search-history');

  if (!searchInput || !historyContainer) return;

  // Show history on focus
  searchInput.addEventListener('focus', () => {
    const history = getSearchHistory();
    if (history.length > 0) {
      renderSearchHistory(history);
      historyContainer.classList.remove('hidden');
    }
  });

  // Clear history
  const clearHistoryBtn = document.getElementById('clear-search-history');
  clearHistoryBtn?.addEventListener('click', () => {
    clearSearchHistory();
    historyContainer.classList.add('hidden');
  });
}

function getSearchHistory(): string[] {
  return StoreUtils.getStorage<string[]>('search-history') || [];
}

function saveSearchHistory(query: string): void {
  const history = getSearchHistory();
  const updatedHistory = [query, ...history.filter(q => q !== query)].slice(0, 10);
  StoreUtils.setStorage('search-history', updatedHistory);
}

function renderSearchHistory(history: string[]): void {
  const container = document.getElementById('search-history');
  if (!container) return;

  container.innerHTML = `
    <div class="search-history-header">
      <h4>Recent Searches</h4>
      <button id="clear-search-history" class="clear-history-btn">
        <i class="fas fa-times"></i> Clear
      </button>
    </div>
    <div class="search-history-items">
      ${history.map(term => `
        <div class="history-item" data-term="${term}">
          <i class="fas fa-clock"></i>
          <span>${term}</span>
        </div>
      `).join('')}
    </div>
  `;

  // Add click handlers
  container.querySelectorAll('.history-item').forEach(item => {
    item.addEventListener('click', () => {
      const term = item.getAttribute('data-term');
      if (term) {
        const searchInput = document.querySelector('input[name="q"]') as HTMLInputElement;
        searchInput.value = term;
        searchInput.form?.submit();
      }
    });
  });
}

function clearSearchHistory(): void {
  StoreUtils.removeStorage('search-history');
}

function initVoiceSearch(): void {
  const voiceSearchBtn = document.getElementById('voice-search-btn');

  if (!voiceSearchBtn || !('webkitSpeechRecognition' in window)) {
    return;
  }

  const recognition = new (window as any).webkitSpeechRecognition();
  recognition.continuous = false;
  recognition.interimResults = false;

  voiceSearchBtn.addEventListener('click', () => {
    recognition.start();
    voiceSearchBtn.classList.add('listening');
  });

  recognition.onresult = (event: any) => {
    const transcript = event.results[0][0].transcript;
    const searchInput = document.querySelector('input[name="q"]') as HTMLInputElement;

    if (searchInput) {
      searchInput.value = transcript;
      searchInput.form?.submit();
    }
  };

  recognition.onend = () => {
    voiceSearchBtn.classList.remove('listening');
  };

  recognition.onerror = () => {
    voiceSearchBtn.classList.remove('listening');
    showVoiceSearchError();
  };
}

function showVoiceSearchError(): void {
  const toast = StoreUtils.createElement('div', {
    className: 'toast error'
  }, ['Voice search failed. Please try again.']);
  document.body.appendChild(toast);
  setTimeout(() => toast.remove(), 3000);
}

function initSearchSorting(): void {
  const sortOptions = document.querySelectorAll('.search-sort-option');

  sortOptions.forEach(option => {
    option.addEventListener('click', (e) => {
      e.preventDefault();
      const sortValue = option.getAttribute('data-sort');
      if (sortValue) {
        updateSearchFilter('sort', sortValue);

        // Update active state
        sortOptions.forEach(opt => opt.classList.remove('active'));
        option.classList.add('active');
      }
    });
  });
}

function initSearchPagination(): void {
  const paginationLinks = document.querySelectorAll('.search-pagination a');

  paginationLinks.forEach(link => {
    link.addEventListener('click', (e) => {
      e.preventDefault();
      const url = (link as HTMLAnchorElement).href;

      // Smooth pagination with loading state
      const searchResults = document.getElementById('search-results');
      if (searchResults) {
        searchResults.classList.add('loading');

        fetch(url)
          .then(response => response.text())
          .then(html => {
            const parser = new DOMParser();
            const doc = parser.parseFromString(html, 'text/html');
            const newResults = doc.getElementById('search-results');

            if (newResults) {
              searchResults.innerHTML = newResults.innerHTML;
              initSearchResults();

              // Scroll to top of results
              searchResults.scrollIntoView({ behavior: 'smooth' });

              // Update URL without reload
              window.history.pushState({}, '', url);
            }
          })
          .catch(error => {
            console.error('Pagination failed:', error);
            window.location.href = url; // Fallback to full page load
          })
          .finally(() => {
            searchResults.classList.remove('loading');
          });
      }
    });
  });
}

function initSearchSpellingCorrection(): void {
  const spellingCorrection = document.getElementById('spelling-correction');

  if (spellingCorrection) {
    const correctedTerm = spellingCorrection.getAttribute('data-corrected-term');
    const originalTerm = spellingCorrection.getAttribute('data-original-term');

    spellingCorrection.querySelector('.corrected-link')?.addEventListener('click', (e) => {
      e.preventDefault();
      if (correctedTerm) {
        const searchInput = document.querySelector('input[name="q"]') as HTMLInputElement;
        if (searchInput) {
          searchInput.value = correctedTerm;
          searchInput.form?.submit();
        }
      }
    });

    spellingCorrection.querySelector('.original-link')?.addEventListener('click', (e) => {
      e.preventDefault();
      if (originalTerm) {
        const searchInput = document.querySelector('input[name="q"]') as HTMLInputElement;
        if (searchInput) {
          searchInput.value = originalTerm;
          searchInput.form?.submit();
        }
      }
    });
  }
}

function initSearchFacets(): void {
  const facetToggles = document.querySelectorAll('.facet-toggle');

  facetToggles.forEach(toggle => {
    toggle.addEventListener('click', () => {
      const facetContent = toggle.nextElementSibling as HTMLElement;
      if (facetContent) {
        const isExpanding = facetContent.classList.toggle('expanded');
        toggle.querySelector('.facet-arrow')?.classList.toggle('rotated', isExpanding);
      }
    });
  });

  // Facet value counts updating
  updateFacetCounts();
}

function updateFacetCounts(): void {
  // This would typically be called after AJAX results load
  // to update facet counts based on current results
  const facetValues = document.querySelectorAll('.facet-value');

  facetValues.forEach(facet => {
    const count = facet.getAttribute('data-count');
    const resultsCount = getResultsCount();

    if (count && resultsCount) {
      const percentage = (parseInt(count) / resultsCount) * 100;
      const bar = facet.querySelector('.facet-count-bar') as HTMLElement;
      if (bar) {
        bar.style.width = `${Math.max(percentage, 5)}%`; // Minimum 5% for visibility
      }
    }
  });
}

function getResultsCount(): number {
  const countElement = document.querySelector('.results-count');
  if (countElement) {
    const text = countElement.textContent || '';
    const match = text.match(/\d+/);
    return match ? parseInt(match[0]) : 0;
  }
  return 0;
}

function getCurrentPage(): number {
  const urlParams = new URLSearchParams(window.location.search);
  return parseInt(urlParams.get('page') || '1');
}

function getActiveFilters(): Record<string, string> {
  const filters: Record<string, string> = {};
  const urlParams = new URLSearchParams(window.location.search);

  urlParams.forEach((value, key) => {
    if (key !== 'q' && key !== 'page') {
      filters[key] = value;
    }
  });

  return filters;
}

function showSearchError(): void {
  const errorElement = StoreUtils.createElement('div', {
    className: 'search-error-message'
  }, [
    '<i class="fas fa-exclamation-triangle"></i>',
    '<h3>Search Temporarily Unavailable</h3>',
    '<p>Please try refreshing the page or come back later.</p>',
    '<button class="btn-primary" onclick="window.location.reload()">Refresh Page</button>'
  ]);

  const resultsContainer = document.getElementById('search-results');
  if (resultsContainer) {
    resultsContainer.innerHTML = '';
    resultsContainer.appendChild(errorElement);
  }
}

// Export for use in other modules
export {
  reloadSearchResults,
  updateSearchFilter,
  getSearchHistory
};