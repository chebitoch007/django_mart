// Desktop dropdown hover handling
document.querySelectorAll('.nav-dropdown-trigger').forEach(trigger => {
    let timeout

    trigger.addEventListener('mouseenter', () => {
        clearTimeout(timeout)
        trigger.querySelector('.nav-dropdown').classList.remove('hidden')
    })

    trigger.addEventListener('mouseleave', () => {
        timeout = setTimeout(() => {
            trigger.querySelector('.nav-dropdown').classList.add('hidden')
        }, 300)
    })

    trigger.querySelector('.nav-dropdown').addEventListener('mouseenter', () => {
        clearTimeout(timeout)
    })

    trigger.querySelector('.nav-dropdown').addEventListener('mouseleave', () => {
        trigger.querySelector('.nav-dropdown').classList.add('hidden')
    })
})