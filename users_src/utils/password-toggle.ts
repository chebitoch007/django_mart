namespace PasswordToggle {
    export function initialize(): void {
        const toggleButtons = document.querySelectorAll('.password-toggle');

        toggleButtons.forEach(button => {
            button.addEventListener('click', (e: Event) => {
                const target = e.currentTarget as HTMLElement;
                const parent = target.parentElement;
                if (!parent) return;

                const input = parent.querySelector('input') as HTMLInputElement;
                if (!input) return;

                const type = input.getAttribute('type') === 'password' ? 'text' : 'password';
                input.setAttribute('type', type);

                const icon = target.querySelector('i');
                if (icon) {
                    icon.className = type === 'password' ? 'far fa-eye' : 'far fa-eye-slash';
                }
            });
        });
    }
}