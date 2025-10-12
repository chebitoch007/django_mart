interface PasswordRequirements {
    length: boolean;
    number: boolean;
    lowercase: boolean;
    uppercase: boolean;
    special: boolean;
}

interface StrengthBars {
    lengthBar: HTMLElement | null;
    numberBar: HTMLElement | null;
    caseBar: HTMLElement | null;
    specialBar: HTMLElement | null;
    strengthText: HTMLElement | null;
}

namespace PasswordValidator {
    export function validatePassword(password: string): PasswordRequirements {
        return {
            length: password.length >= 10,
            number: /\d/.test(password),
            lowercase: /[a-z]/.test(password),
            uppercase: /[A-Z]/.test(password),
            special: /[!@#$%^&*(),.?":{}|<>]/.test(password)
        };
    }

    export function isPasswordStrong(password: string): boolean {
        const requirements = validatePassword(password);
        const values = [
            requirements.length,
            requirements.number,
            requirements.lowercase && requirements.uppercase,
            requirements.special
        ];
        return values.every(req => req);
    }

    export function getStrengthText(strength: number): string {
        const strengthTexts: string[] = [
            'Very weak - Add more characters and complexity',
            'Weak - Try adding numbers or symbols',
            'Medium - Add uppercase letters or symbols',
            'Strong - Good job!',
            'Very strong - Excellent password!'
        ];
        return strengthTexts[strength] || 'Password must be at least 10 characters long';
    }

    export function updateStrengthBars(password: string, bars: StrengthBars): void {
        if (!bars.lengthBar || !bars.numberBar || !bars.caseBar || !bars.specialBar || !bars.strengthText) return;

        const allBars = [bars.lengthBar, bars.numberBar, bars.caseBar, bars.specialBar];

        // Reset all bars
        allBars.forEach(bar => {
            if (bar) bar.className = 'h-1 rounded bg-gray-200 flex-1';
        });

        const requirements = validatePassword(password);
        let strength = 0;

        // Update bars based on requirements
        if (requirements.length && bars.lengthBar) {
            bars.lengthBar.classList.add('bg-green-500');
            strength++;
        } else if (password.length > 0 && bars.lengthBar) {
            bars.lengthBar.classList.add('bg-red-500');
        }

        if (requirements.number && bars.numberBar) {
            bars.numberBar.classList.add('bg-green-500');
            strength++;
        } else if (password.length > 0 && bars.numberBar) {
            bars.numberBar.classList.add('bg-red-500');
        }

        if (requirements.lowercase && requirements.uppercase && bars.caseBar) {
            bars.caseBar.classList.add('bg-green-500');
            strength++;
        } else if (password.length > 0 && bars.caseBar) {
            bars.caseBar.classList.add('bg-red-500');
        }

        if (requirements.special && bars.specialBar) {
            bars.specialBar.classList.add('bg-green-500');
            strength++;
        } else if (password.length > 0 && bars.specialBar) {
            bars.specialBar.classList.add('bg-red-500');
        }

        // Update strength text
        if (bars.strengthText) {
            bars.strengthText.textContent = getStrengthText(strength);
            bars.strengthText.className = 'mt-2 text-xs ' + (
                strength < 2 ? 'text-red-600' :
                strength < 3 ? 'text-amber-600' :
                strength < 4 ? 'text-yellow-600' : 'text-green-600'
            );
        }
    }

    export function updateRequirementsList(requirements: PasswordRequirements): void {
        const requirementElements = document.querySelectorAll('.requirement');

        requirementElements.forEach(element => {
            const requirementType = element.getAttribute('data-requirement');
            const icon = element.querySelector('i');

            if (icon && requirementType && requirements[requirementType as keyof PasswordRequirements]) {
                icon.className = 'fas fa-check text-green-500 mr-2 text-xs';
                element.classList.add('text-green-600');
                element.classList.remove('text-gray-600');
            } else if (icon) {
                icon.className = 'fas fa-circle text-gray-300 mr-2 text-xs';
                element.classList.remove('text-green-600');
                element.classList.add('text-gray-600');
            }
        });
    }
}
