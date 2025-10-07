export function validateEmail(email: string): boolean {
  const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
  return emailRegex.test(email);
}

export function validateAmount(amount: number): boolean {
  return amount > 0 && amount < 1000000; // Example validation
}

export function sanitizeInput(input: string): string {
  return input.trim().replace(/[<>]/g, '');
}