import { PasswordStrength } from '../types/auth';

export function validateEmail(email: string): boolean {
    const re = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    return re.test(email);
}

export function validatePassword(password: string): PasswordStrength {
    const requirements = {
        length: password.length >= 8,
        number: /\d/.test(password),
        lowercase: /[a-z]/.test(password),
        uppercase: /[A-Z]/.test(password),
        special: /[!@#$%^&*(),.?":{}|<>]/.test(password)
    };

    const score = Object.values(requirements).filter(Boolean).length;

    const strengthTexts = [
        'Very weak - Add more requirements',
        'Weak - Needs more complexity',
        'Fair - Getting stronger',
        'Good - Almost there',
        'Strong - Great password!',
        'Very strong - Excellent!'
    ];

    return {
        score,
        text: strengthTexts[score] || 'Enter a password',
        requirements
    };
}

export function isPasswordStrong(password: string): boolean {
    const strength = validatePassword(password);
    return strength.score >= 4;
}