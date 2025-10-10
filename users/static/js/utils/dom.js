export function getCSRFToken() {
    return document.querySelector('[name=csrfmiddlewaretoken]')?.getAttribute('value') || null;
}
export function showFieldError(field, message) {
    field.classList.add('error');
    let errorElement = field.parentElement?.querySelector('.field-error');
    if (!errorElement) {
        errorElement = document.createElement('div');
        errorElement.className = 'field-error text-red-600 text-xs mt-1';
        field.parentElement?.appendChild(errorElement);
    }
    errorElement.textContent = message;
    errorElement.style.animation = 'slideIn 0.3s ease-out';
}
export function clearFieldError(field) {
    field.classList.remove('error');
    const errorElement = field.parentElement?.querySelector('.field-error');
    if (errorElement) {
        errorElement.remove();
    }
}
export function debounce(func, wait) {
    let timeout;
    return (...args) => {
        clearTimeout(timeout);
        timeout = setTimeout(() => func.apply(null, args), wait);
    };
}
//# sourceMappingURL=dom.js.map