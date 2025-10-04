document.addEventListener('DOMContentLoaded', () => {
    const form = document.getElementById('paymentForm');
    const phoneInput = document.getElementById('phoneNumber');

    form.addEventListener('submit', async (e) => {
        e.preventDefault();

        const formData = new FormData(form);
        const response = await fetch('/api/validate-payment/', {
            method: 'POST',
            body: formData,
            headers: {
                'X-Requested-With': 'XMLHttpRequest'
            }
        });

        const result = await response.json();

        if (result.valid) {
            form.submit();
        } else {
            showErrors(result.errors);
        }
    });

    // Real-time phone validation
    phoneInput.addEventListener('input', debounce(validatePhone, 500));
});