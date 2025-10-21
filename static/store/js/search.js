// static/store/js/search.js
(function () {
  'use strict';

  function getCSRFToken() {
    const cookie = document.cookie.split(';').map(c => c.trim()).find(c => c.startsWith('csrftoken='));
    return cookie ? cookie.split('=')[1] : '';
  }

  function isSameOrigin(url) {
    try {
      const u = new URL(url, window.location.href);
      return u.origin === window.location.origin;
    } catch (e) {
      return false;
    }
  }

  function fetchAndReplace(url, push = true) {
    const headers = {
      'X-Requested-With': 'XMLHttpRequest',
      'X-CSRFToken': getCSRFToken()
    };
    fetch(url, { headers, credentials: 'same-origin' })
      .then(resp => {
        if (!resp.ok) throw new Error('Network failure');
        return resp.text();
      })
      .then(html => {
        const parser = new DOMParser();
        const doc = parser.parseFromString(html, 'text/html');

        const newResults = doc.querySelector('.results-grid');
        const newPagination = doc.querySelector('.pagination-container');

        const root = document.getElementById('resultsRoot');
        if (newResults) {
          // replace the results grid region inside resultsRoot
          const oldGrid = root.querySelector('.results-grid');
          if (oldGrid) oldGrid.replaceWith(newResults);
          else root.insertAdjacentElement('afterbegin', newResults);
        }
        // replace pagination if present
        const oldPagination = document.querySelector('.pagination-container');
        if (newPagination && oldPagination) {
          oldPagination.replaceWith(newPagination);
        } else if (newPagination && !oldPagination) {
          document.getElementById('resultsRoot').insertAdjacentElement('beforeend', newPagination);
        }

        if (push) history.pushState({}, '', url);
        // rebind if needed (no heavy re-init)
      })
      .catch(err => console.error('AJAX fetch failed', err));
  }

  // Intercept click on links with query params for AJAX
  document.addEventListener('click', function (e) {
    const el = e.target.closest('a');
    if (!el) return;
    if (!el.href) return;
    if (!isSameOrigin(el.href)) return;

    // Only handle links that contain '?' (filters/pagination)
    if (el.href.indexOf('?') !== -1) {
      // allow bypass by data-no-ajax="true"
      if (el.dataset.noAjax === 'true') return;
      e.preventDefault();
      fetchAndReplace(el.href);
    }
  });

  // Helper debounce
  function debounce(fn, wait = 250) {
    let t;
    return function () {
      const args = arguments;
      clearTimeout(t);
      t = setTimeout(() => fn.apply(this, args), wait);
    };
  }

  // Sort select (if exists)
  const sortSelect = document.getElementById('sortSelect');
  if (sortSelect) {
    sortSelect.addEventListener('change', function () {
      const url = new URL(window.location.href);
      url.searchParams.set('sort', this.value);
      url.searchParams.delete('page');
      fetchAndReplace(url.toString());
    });
  }

  // Price apply
  const applyPriceBtn = document.getElementById('applyPriceBtn');
  if (applyPriceBtn) {
    applyPriceBtn.addEventListener('click', function () {
      const maxInput = document.getElementById('maxPriceInput');
      const minInput = document.getElementById('minPriceInput');
      const url = new URL(window.location.href);
      if (maxInput && maxInput.value) url.searchParams.set('max_price', maxInput.value);
      else url.searchParams.delete('max_price');
      if (minInput && minInput.value) url.searchParams.set('min_price', minInput.value);
      else url.searchParams.delete('min_price');
      url.searchParams.delete('page');
      fetchAndReplace(url.toString());
    });
  }

  // Price slider quick UX
  const priceRange = document.getElementById('priceRange');
  const priceDisplay = document.getElementById('priceDisplay');
  if (priceRange && priceDisplay) {
    priceRange.addEventListener('input', function () {
      priceDisplay.textContent = this.value + ' KES';
    });
    // debounce applying change
    priceRange.addEventListener('change', debounce(function () {
      const url = new URL(window.location.href);
      url.searchParams.set('max_price', this.value);
      url.searchParams.delete('page');
      fetchAndReplace(url.toString());
    }, 450));
  }

  // Stock checkbox
  const inStockCheckbox = document.getElementById('inStock');
  if (inStockCheckbox) {
    inStockCheckbox.addEventListener('change', function () {
      const url = new URL(window.location.href);
      if (this.checked) url.searchParams.set('in_stock', 'true');
      else url.searchParams.delete('in_stock');
      url.searchParams.delete('page');
      fetchAndReplace(url.toString());
    });
  }

  // History handling
  window.addEventListener('popstate', function () {
    fetchAndReplace(window.location.href, false);
  });

})();
