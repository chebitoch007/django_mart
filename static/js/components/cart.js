// Cart interaction animations
document.addEventListener('DOMContentLoaded', () => {
    const cartButtons = document.querySelectorAll('[data-cart-add]')

    cartButtons.forEach(button => {
        button.addEventListener('click', () => {
            const counter = document.querySelector('.cart-badge')
            if (counter) {
                counter.classList.add('animate-pulse')
                setTimeout(() => counter.classList.remove('animate-pulse'), 500)
            }
        })
    })
})