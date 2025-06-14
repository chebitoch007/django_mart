document.querySelectorAll('a[href^="#"]').forEach(anchor => {
    anchor.addEventListener('click', function(e) {
        e.preventDefault()
        const target = document.querySelector(this.getAttribute('href'))
        if (target) {
            target.scrollIntoView({
                behavior: 'smooth',
                block: 'start'
            })
        }
    })
})

// Initialize Alpine.js components
document.addEventListener('alpine:init', () => {
    Alpine.data('cart', () => ({
        init() {
            // Cart initialization logic
        }
    }));
});

// Initialize password toggles
document.querySelectorAll('.password-toggle').forEach(button => {
    button.addEventListener('click', () => {
        const input = button.previousElementSibling;
        input.type = input.type === 'password' ? 'text' : 'password';
        button.querySelector('i').classList.toggle('fa-eye-slash');
        button.querySelector('i').classList.toggle('fa-eye');
    });
});