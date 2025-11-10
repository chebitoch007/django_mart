// Currency Selector JavaScript (Fixed for Mobile)
document.addEventListener('DOMContentLoaded', function() {
    const toggle = document.getElementById('currencyToggle');
    const dropdown = document.getElementById('currencyDropdown');
    const dropdownClose = dropdown?.querySelector('.currency-close');
    const bottomSheet = document.getElementById('currencyBottomSheet');
    const bottomSheetClose = bottomSheet?.querySelector('.bottom-sheet-close');
    const overlay = bottomSheet?.querySelector('.bottom-sheet-overlay');

    // --- Helper Functions ---
    function isMobile() {
        return window.innerWidth <= 768;
    }

    function openDropdown() {
        if (dropdown) {
            dropdown.hidden = false;
            toggle.setAttribute('aria-expanded', 'true');

            // On mobile, prevent body scroll and adjust positioning
            if (isMobile()) {
                document.body.style.overflow = 'hidden';

                // Ensure dropdown is visible and not cut off
                const navHeight = document.querySelector('.amazon-nav')?.offsetHeight || 60;
                dropdown.style.top = `${navHeight}px`;
            }
        }
    }

    function closeDropdown() {
        if (dropdown) {
            dropdown.hidden = true;
            toggle.setAttribute('aria-expanded', 'false');
            document.body.style.overflow = '';
        }
    }

    function openBottomSheet() {
        if (bottomSheet) {
            bottomSheet.hidden = false;
            toggle.setAttribute('aria-expanded', 'true');
            document.body.style.overflow = 'hidden';
        }
    }

    function closeBottomSheet() {
        if (bottomSheet) {
            bottomSheet.hidden = true;
            toggle.setAttribute('aria-expanded', 'false');
            document.body.style.overflow = '';
        }
    }

    function closeAll() {
        closeDropdown();
        closeBottomSheet();
    }

    // --- Event Listeners ---

    // Toggle button click - Always use dropdown
    if (toggle) {
        toggle.addEventListener('click', function(e) {
            e.stopPropagation();

            const isExpanded = toggle.getAttribute('aria-expanded') === 'true';

            if (isExpanded) {
                closeAll();
            } else {
                // Always use dropdown (works on all screen sizes)
                openDropdown();
            }
        });
    }

    // Close button clicks
    if (dropdownClose) {
        dropdownClose.addEventListener('click', function(e) {
            e.stopPropagation();
            closeDropdown();
        });
    }

    if (bottomSheetClose) {
        bottomSheetClose.addEventListener('click', function(e) {
            e.stopPropagation();
            closeBottomSheet();
        });
    }

    // Overlay click
    if (overlay) {
        overlay.addEventListener('click', closeBottomSheet);
    }

    // Close on outside click (including backdrop on mobile)
    document.addEventListener('click', function(e) {
        if (dropdown &&
            !dropdown.hidden &&
            !toggle.contains(e.target) &&
            !dropdown.contains(e.target)) {
            closeDropdown();
        }
    });

    // Special handling for mobile backdrop clicks
    if (isMobile()) {
        document.addEventListener('click', function(e) {
            if (dropdown && !dropdown.hidden) {
                // If clicking outside the dropdown content (on the backdrop)
                const rect = dropdown.getBoundingClientRect();
                const clickX = e.clientX;
                const clickY = e.clientY;

                if (clickX < rect.left || clickX > rect.right ||
                    clickY < rect.top || clickY > rect.bottom) {
                    // Clicked outside the dropdown
                    if (!toggle.contains(e.target)) {
                        closeDropdown();
                    }
                }
            }
        });
    }

    // Close on escape key
    document.addEventListener('keydown', function(e) {
        if (e.key === 'Escape') {
            closeAll();
        }
    });

    // Handle window resize
    let resizeTimer;
    window.addEventListener('resize', function() {
        clearTimeout(resizeTimer);
        resizeTimer = setTimeout(function() {
            // Close both modals on resize to prevent UI issues
            closeAll();
        }, 250);
    });

    // Prevent body scroll when dropdown is open on mobile
    if (dropdown) {
        const observer = new MutationObserver(function(mutations) {
            mutations.forEach(function(mutation) {
                if (mutation.attributeName === 'hidden') {
                    if (!dropdown.hidden && isMobile()) {
                        document.body.style.overflow = 'hidden';
                    } else if (dropdown.hidden) {
                        document.body.style.overflow = '';
                    }
                }
            });
        });

        observer.observe(dropdown, {
            attributes: true,
            attributeFilter: ['hidden']
        });
    }
});