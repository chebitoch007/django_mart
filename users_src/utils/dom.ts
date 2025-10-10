import { BrowserTimeout } from '../types/dom';

export function getCSRFToken(): string | null {
    return document.querySelector('[name=csrfmiddlewaretoken]')?.getAttribute('value') || null;
}

export function showFieldError(field: HTMLInputElement, message: string): void {
    field.classList.add('error');

    let errorElement = field.parentElement?.querySelector('.field-error');
    if (!errorElement) {
        errorElement = document.createElement('div');
        errorElement.className = 'field-error text-red-600 text-xs mt-1';
        field.parentElement?.appendChild(errorElement);
    }

    errorElement.textContent = message;
    (errorElement as HTMLElement).style.animation = 'slideIn 0.3s ease-out';
}

export function clearFieldError(field: HTMLInputElement): void {
    field.classList.remove('error');
    const errorElement = field.parentElement?.querySelector('.field-error');
    if (errorElement) {
        errorElement.remove();
    }
}

export function debounce<T extends (...args: any[]) => any>(
    func: T,
    wait: number
): (...args: Parameters<T>) => void {
    let timeout: BrowserTimeout;
    return (...args: Parameters<T>) => {
        clearTimeout(timeout);
        timeout = setTimeout(() => func.apply(null, args), wait);
    };
}