export function validateEmail(email) {
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    return emailRegex.test(email);
}
export function validateAmount(amount) {
    return amount > 0 && amount < 1000000; // Example validation
}
export function sanitizeInput(input) {
    return input.trim().replace(/[<>]/g, '');
}
//# sourceMappingURL=validation.js.map