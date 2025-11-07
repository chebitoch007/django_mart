// Complete corrected account.ts file
interface BrowserTimeout {
    (callback: (...args: any[]) => void, ms: number): number;
}

interface SessionData {
    sessionTimeout: string | null;
    logoutUrl: string | null;
    keepaliveUrl: string | null;
    csrfToken: string | null;
}

class AccountPage {
    private timeoutWarning: number | null = null;
    private logoutTimer: number | null = null;
    private sessionTimer: number | null = null;
    private timeLeft: number = 120;

    constructor() {
        this.initialize();
    }

    private initialize(): void {
        this.initializeSmoothScrolling();
        this.initializeCardAnimations();
        this.initializeProfileImageErrorHandling();
        this.initializeSessionTimeout();
        this.initializeModals();
        this.initializeAccessibility();
        this.initializeProfileImageUpload();
        this.initializeImageModal();
        this.updateRemoveButtonVisibility();
    }

    private initializeSmoothScrolling(): void {
        const navItems = document.querySelectorAll('.account-nav-item');

        navItems.forEach(item => {
            item.addEventListener('click', (e: Event) => {
                e.preventDefault();
                const targetId = (e.currentTarget as HTMLElement).getAttribute('href');

                if (targetId && targetId.startsWith('#')) {
                    const targetElement = document.querySelector(targetId);

                    if (targetElement) {
                        targetElement.scrollIntoView({
                            behavior: 'smooth',
                            block: 'start'
                        });
                    }
                }
            });
        });
    }

    private initializeCardAnimations(): void {
        const cards = document.querySelectorAll('.card-hover');

        cards.forEach(card => {
            card.addEventListener('mouseenter', () => {
                (card as HTMLElement).style.transform = 'translateY(-5px)';
            });

            card.addEventListener('mouseleave', () => {
                (card as HTMLElement).style.transform = 'translateY(0)';
            });
        });
    }

    private initializeProfileImageErrorHandling(): void {
        const profileImage = document.getElementById('profile-image') as HTMLImageElement;

        if (profileImage) {
            profileImage.addEventListener('error', () => {
                const defaultImage = profileImage.getAttribute('data-default-src');
                if (defaultImage) {
                    profileImage.src = defaultImage;
                }
            });
        }
    }

    private initializeProfileImageUpload(): void {
        const profileImageInput = document.getElementById('profileImageInput') as HTMLInputElement;

        if (profileImageInput) {
            profileImageInput.addEventListener('change', (event: Event) => {
                this.handleProfileImageUpload(event);
            });
        }
    }

    private initializeImageModal(): void {
        // Close modal on ESC key
        document.addEventListener('keydown', (event: KeyboardEvent) => {
            if (event.key === 'Escape') {
                const modal = document.getElementById('imageViewModal');
                if (modal && !modal.classList.contains('hidden')) {
                    this.hideImageViewModal();
                }
            }
        });
    }

    private updateRemoveButtonVisibility(): void {
        const profileImage = document.getElementById('profile-image') as HTMLImageElement;
        const removeBtn = document.getElementById('removePhotoBtn');

        if (profileImage && removeBtn) {
            const hasCustomImage = profileImage.getAttribute('data-has-custom-image') === 'true';

            if (hasCustomImage) {
                removeBtn.style.display = 'flex';
                removeBtn.classList.remove('hidden');
            } else {
                removeBtn.style.display = 'none';
                removeBtn.classList.add('hidden');
            }
        }
    }

    public showImageViewModal(): void {
        const modal = document.getElementById('imageViewModal');
        const fullImage = document.getElementById('fullProfileImage') as HTMLImageElement;
        const profileImage = document.getElementById('profile-image') as HTMLImageElement;

        if (modal && fullImage && profileImage) {
            fullImage.src = profileImage.src;
            modal.classList.remove('hidden');
            modal.classList.add('flex');

            // Update remove button visibility in modal
            this.updateRemoveButtonVisibility();

            // Prevent body scroll
            document.body.style.overflow = 'hidden';
        }
    }

    public hideImageViewModal(): void {
        const modal = document.getElementById('imageViewModal');
        if (modal) {
            modal.classList.add('hidden');
            modal.classList.remove('flex');

            // Restore body scroll
            document.body.style.overflow = 'auto';
        }
    }

    public triggerImageUpload(): void {
        this.hideImageViewModal();
        const input = document.getElementById('profileImageInput') as HTMLInputElement;
        if (input) {
            input.click();
        }
    }

    public removeProfileImage(): void {
        const profileImage = document.getElementById('profile-image') as HTMLImageElement;
        const removeBtn = document.getElementById('removePhotoBtn') as HTMLButtonElement;

        if (!profileImage) return;

        const hasCustomImage = profileImage.getAttribute('data-has-custom-image') === 'true';
        if (!hasCustomImage) {
            this.showErrorMessage('No custom profile picture to remove');
            return;
        }

        // Show confirmation
        if (!confirm('Are you sure you want to remove your profile picture? Your account will use the default image.')) {
            return;
        }

        // Get CSRF token
        const csrfToken = this.getCookie('csrftoken');
        if (!csrfToken) {
            this.showErrorMessage('Security token missing. Please refresh the page.');
            return;
        }

        // Show loading state
        const originalSrc = profileImage.src;
        profileImage.style.opacity = '0.5';

        if (removeBtn) {
            removeBtn.disabled = true;
            const originalHTML = removeBtn.innerHTML;
            removeBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i><span>Removing...</span>';
        }

        const removeUrl = '/accounts/profile/image/remove/';

        fetch(removeUrl, {
            method: 'POST',
            headers: {
                'X-CSRFToken': csrfToken,
                'Content-Type': 'application/json'
            }
        })
        .then(response => {
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            return response.json();
        })
        .then(data => {
            if (data.success) {
                // Update to default image
                const defaultImage = profileImage.getAttribute('data-default-src');
                if (defaultImage) {
                    const newImageUrl = defaultImage + '?t=' + new Date().getTime();
                    profileImage.src = newImageUrl;
                    profileImage.setAttribute('data-has-custom-image', 'false');
                }

                profileImage.style.opacity = '1';

                // Update full image modal if open
                const fullImage = document.getElementById('fullProfileImage') as HTMLImageElement;
                if (fullImage && defaultImage) {
                    fullImage.src = defaultImage;
                }

                // Hide remove button
                this.updateRemoveButtonVisibility();

                // Close modal
                this.hideImageViewModal();

                this.showSuccessMessage('Profile picture removed successfully!');
            } else {
                throw new Error(data.error || 'Remove failed');
            }
        })
        .catch(error => {
            console.error('Error:', error);
            this.showErrorMessage('Failed to remove image. Please try again.');
            profileImage.src = originalSrc;
            profileImage.style.opacity = '1';
        })
        .finally(() => {
            if (removeBtn) {
                removeBtn.disabled = false;
                removeBtn.innerHTML = '<i class="fas fa-trash"></i><span>Remove</span>';
            }
        });
    }

    public downloadProfileImage(): void {
        const profileImage = document.getElementById('profile-image') as HTMLImageElement;
        if (!profileImage) return;

        const imageUrl = profileImage.src;

        fetch(imageUrl)
            .then(response => response.blob())
            .then(blob => {
                const url = window.URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                a.download = 'profile-picture.jpg';
                document.body.appendChild(a);
                a.click();
                window.URL.revokeObjectURL(url);
                document.body.removeChild(a);
            })
            .catch(error => {
                console.error('Download failed:', error);
                this.showErrorMessage('Failed to download image');
            });
    }

    private initializeSessionTimeout(): void {
        const sessionTimeoutModal = document.getElementById('sessionTimeoutModal');
        if (!sessionTimeoutModal) return;

        const sessionData: SessionData = {
            sessionTimeout: document.body.getAttribute('data-session-timeout'),
            logoutUrl: document.body.getAttribute('data-logout-url'),
            keepaliveUrl: document.body.getAttribute('data-keepalive-url'),
            csrfToken: document.body.getAttribute('data-csrf-token')
        };

        if (!sessionData.sessionTimeout || !sessionData.logoutUrl) return;

        const SESSION_TIMEOUT = parseInt(sessionData.sessionTimeout);
        const WARNING_TIME = 120;

        this.startTimers(SESSION_TIMEOUT, WARNING_TIME, sessionData);

        document.addEventListener('mousemove', () => this.resetTimers(SESSION_TIMEOUT, WARNING_TIME, sessionData));
        document.addEventListener('keypress', () => this.resetTimers(SESSION_TIMEOUT, WARNING_TIME, sessionData));
    }

    private startTimers(sessionTimeout: number, warningTime: number, sessionData: SessionData): void {
        this.timeoutWarning = window.setTimeout(() => {
            this.showTimeoutWarning(warningTime, sessionData);
        }, (sessionTimeout - warningTime) * 1000);

        this.logoutTimer = window.setTimeout(() => {
            this.logoutUser(sessionData);
        }, sessionTimeout * 1000);
    }

    private showTimeoutWarning(warningTime: number, sessionData: SessionData): void {
        const modalElement = document.getElementById('sessionTimeoutModal');
        if (!modalElement) return;

        const modal = new (window as any).bootstrap.Modal(modalElement);
        modal.show();

        this.timeLeft = warningTime;

        const countdown = setInterval(() => {
            this.timeLeft--;
            const timeLeftElement = document.getElementById('timeLeft');

            if (timeLeftElement) {
                const minutes = Math.floor(this.timeLeft / 60).toString().padStart(2, '0');
                const seconds = (this.timeLeft % 60).toString().padStart(2, '0');

                timeLeftElement.textContent = `${minutes}:${seconds}`;
            }

            const progress = (this.timeLeft / warningTime) * 100;
            const sessionProgress = document.getElementById('sessionProgress');

            if (sessionProgress) {
                sessionProgress.style.width = `${progress}%`;
            }

            if (this.timeLeft <= 0) {
                clearInterval(countdown);
                this.logoutUser(sessionData);
            }
        }, 1000);

        const extendSessionBtn = document.getElementById('extendSessionBtn');
        if (extendSessionBtn) {
            extendSessionBtn.addEventListener('click', () => {
                clearInterval(countdown);
                modal.hide();
                this.extendSession(sessionData);
            });
        }

        const logoutNowBtn = document.getElementById('logoutNowBtn');
        if (logoutNowBtn) {
            logoutNowBtn.addEventListener('click', () => {
                clearInterval(countdown);
                this.logoutUser(sessionData);
            });
        }
    }

    private logoutUser(sessionData: SessionData): void {
        if (!sessionData.logoutUrl || !sessionData.csrfToken) return;

        const form = document.createElement('form');
        form.method = 'post';
        form.action = sessionData.logoutUrl;

        const csrf = document.createElement('input');
        csrf.type = 'hidden';
        csrf.name = 'csrfmiddlewaretoken';
        csrf.value = sessionData.csrfToken;
        form.appendChild(csrf);

        document.body.appendChild(form);
        form.submit();
    }

    private extendSession(sessionData: SessionData): void {
        if (this.timeoutWarning) clearTimeout(this.timeoutWarning);
        if (this.logoutTimer) clearTimeout(this.logoutTimer);
        if (this.sessionTimer) clearInterval(this.sessionTimer);

        if (sessionData.keepaliveUrl) {
            fetch(sessionData.keepaliveUrl, { method: 'HEAD' })
                .then(() => {
                    this.timeLeft = 120;
                    const SESSION_TIMEOUT = parseInt(sessionData.sessionTimeout || '1800');
                    this.startTimers(SESSION_TIMEOUT, 120, sessionData);
                })
                .catch(() => {
                    this.timeLeft = 120;
                    const SESSION_TIMEOUT = parseInt(sessionData.sessionTimeout || '1800');
                    this.startTimers(SESSION_TIMEOUT, 120, sessionData);
                });
        } else {
            this.timeLeft = 120;
            const SESSION_TIMEOUT = parseInt(sessionData.sessionTimeout || '1800');
            this.startTimers(SESSION_TIMEOUT, 120, sessionData);
        }
    }

    private resetTimers(sessionTimeout: number, warningTime: number, sessionData: SessionData): void {
        if (this.timeoutWarning) clearTimeout(this.timeoutWarning);
        if (this.logoutTimer) clearTimeout(this.logoutTimer);
        if (this.sessionTimer) clearInterval(this.sessionTimer);
        this.startTimers(sessionTimeout, warningTime, sessionData);
    }

    private getCookie(name: string): string | null {
        let cookieValue = null;
        if (document.cookie && document.cookie !== '') {
            const cookies = document.cookie.split(';');
            for (let i = 0; i < cookies.length; i++) {
                const cookie = cookies[i].trim();
                if (cookie.substring(0, name.length + 1) === (name + '=')) {
                    cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                    break;
                }
            }
        }
        return cookieValue;
    }

    private showSuccessMessage(message: string): void {
        const messageDiv = document.createElement('div');
        messageDiv.className = 'upload-success-message';
        messageDiv.innerHTML = `
            <div class="flex items-center">
                <i class="fas fa-check-circle mr-2"></i>
                <span>${message}</span>
            </div>
        `;
        document.body.appendChild(messageDiv);

        setTimeout(() => {
            messageDiv.style.animation = 'slideIn 0.3s ease reverse';
            setTimeout(() => messageDiv.remove(), 300);
        }, 3000);
    }

    private showErrorMessage(message: string): void {
        const messageDiv = document.createElement('div');
        messageDiv.className = 'upload-success-message';
        messageDiv.style.background = '#ef4444';
        messageDiv.innerHTML = `
            <div class="flex items-center">
                <i class="fas fa-exclamation-circle mr-2"></i>
                <span>${message}</span>
            </div>
        `;
        document.body.appendChild(messageDiv);

        setTimeout(() => {
            messageDiv.style.animation = 'slideIn 0.3s ease reverse';
            setTimeout(() => messageDiv.remove(), 300);
        }, 3000);
    }

    private handleProfileImageUpload(event: Event): void {
        const target = event.target as HTMLInputElement;
        if (!target.files || target.files.length === 0) return;

        const file = target.files[0];

        // Validate file type
        if (!file.type.startsWith('image/')) {
            this.showErrorMessage('Please select a valid image file');
            target.value = '';
            return;
        }

        // Validate file size (max 5MB)
        if (file.size > 5 * 1024 * 1024) {
            this.showErrorMessage('Image size should not exceed 5MB');
            target.value = '';
            return;
        }

        const formData = new FormData();
        formData.append('profile_image', file);

        // Show loading state
        const profileImg = document.getElementById('profile-image') as HTMLImageElement;
        const originalSrc = profileImg.src;
        profileImg.style.opacity = '0.5';

        // Get CSRF token
        const csrfToken = this.getCookie('csrftoken');
        if (!csrfToken) {
            this.showErrorMessage('Security token missing. Please refresh the page.');
            profileImg.style.opacity = '1';
            target.value = '';
            return;
        }

        const updateUrl = '/accounts/profile/image/';

        fetch(updateUrl, {
            method: 'POST',
            body: formData,
            headers: {
                'X-CSRFToken': csrfToken
            }
        })
        .then(response => {
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            return response.json();
        })
        .then(data => {
            if (data.success) {
                // Add timestamp to prevent caching
                const newImageUrl = data.profile_image_url + '?t=' + new Date().getTime();
                profileImg.src = newImageUrl;
                profileImg.setAttribute('data-has-custom-image', 'true');
                profileImg.style.opacity = '1';

                // Update full image modal if open
                const fullImage = document.getElementById('fullProfileImage') as HTMLImageElement;
                if (fullImage) {
                    fullImage.src = newImageUrl;
                }

                // Update remove button visibility
                this.updateRemoveButtonVisibility();

                this.showSuccessMessage('Profile picture updated successfully!');
            } else {
                throw new Error(data.error || 'Upload failed');
            }
        })
        .catch(error => {
            console.error('Error:', error);
            this.showErrorMessage('Failed to upload image. Please try again.');
            profileImg.src = originalSrc;
            profileImg.style.opacity = '1';
        })
        .finally(() => {
            target.value = '';
        });
    }

    public showDeleteModal(addressId: number, addressName: string): void {
        const modal = document.getElementById('deleteAddressModal') as HTMLElement;
        const form = document.getElementById('deleteAddressForm') as HTMLFormElement;
        const nameSpan = document.getElementById('deleteAddressName') as HTMLElement;

        form.action = `/accounts/address/${addressId}/delete/`;
        nameSpan.textContent = addressName;

        modal.classList.remove('hidden');
        modal.classList.add('flex');
    }

    public hideDeleteModal(): void {
        const modal = document.getElementById('deleteAddressModal') as HTMLElement;
        modal.classList.add('hidden');
        modal.classList.remove('flex');
    }

    private initializeModals(): void {
        const deleteModal = document.getElementById('deleteAddressModal');
        if (deleteModal) {
            deleteModal.addEventListener('click', (event: Event) => {
                if (event.target === deleteModal) {
                    this.hideDeleteModal();
                }
            });
        }

        // Image view modal backdrop click
        const imageModal = document.getElementById('imageViewModal');
        if (imageModal) {
            imageModal.addEventListener('click', (event: Event) => {
                if (event.target === imageModal) {
                    this.hideImageViewModal();
                }
            });
        }
    }

    private initializeAccessibility(): void {
        const profileContainer = document.querySelector('.profile-image-container') as HTMLElement;
        if (profileContainer) {
            // Add click event listener for mouse/touch
            profileContainer.addEventListener('click', (e: MouseEvent) => {
                e.preventDefault();
                this.showImageViewModal();
            });

            // Keep the keydown listener for accessibility
            profileContainer.addEventListener('keydown', (e: KeyboardEvent) => {
                if (e.key === 'Enter' || e.key === ' ') {
                    e.preventDefault();
                    this.showImageViewModal();
                }
            });

            // Set ARIA attributes
            profileContainer.setAttribute('tabindex', '0');
            profileContainer.setAttribute('role', 'button');
            profileContainer.setAttribute('aria-label', 'Click to view or change profile picture');
        }
    }
}

// Initialize the account page when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    const accountPage = new AccountPage();

    // Expose methods to global scope for inline handlers
    (window as any).showDeleteModal = accountPage.showDeleteModal.bind(accountPage);
    (window as any).hideDeleteModal = accountPage.hideDeleteModal.bind(accountPage);
    (window as any).showImageViewModal = accountPage.showImageViewModal.bind(accountPage);
    (window as any).hideImageViewModal = (event?: Event) => {
        if (!event || event.target === document.getElementById('imageViewModal') || (event.currentTarget as HTMLElement)?.tagName === 'BUTTON') {
            accountPage.hideImageViewModal();
        }
    };
    (window as any).triggerImageUpload = (event: Event) => {
        event.stopPropagation();
        accountPage.triggerImageUpload();
    };
    (window as any).removeProfileImage = (event: Event) => {
        event.stopPropagation();
        accountPage.removeProfileImage();
    };
    (window as any).downloadProfileImage = (event: Event) => {
        event.stopPropagation();
        accountPage.downloadProfileImage();
    };
});