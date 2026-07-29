document.addEventListener('DOMContentLoaded', function() {
    document.querySelectorAll('.edit-btn').forEach(button => {
        button.addEventListener('click', function() {
            const container = document.querySelector('#YorznabEditContainer');
            const span = container.querySelector('#YorznabTitle');
            const input = container.querySelector('#YorznabInput');
            const saveUrl = container.dataset.save;
            const csrfToken = container.dataset.csrf;
            
            // Toggle edit mode
            if (this.textContent === '✏️') {
                // Enter edit mode
                input.value = span.textContent.trim();
                input.classList.remove('error-message');
                span.style.display = 'none';
                input.style.display = 'inline-block';
                this.textContent = '💾';
                input.focus();
            } else {
                // Save mode
                const newValue = input.value.trim() || input.placeholder;
                if (!newValue) {
                    input.classList.add('error-message');
                    return;
                }
                if (span.textContent === newValue) {
                    this.textContent = '✏️';
                    span.style.display = 'inline-block';
                    input.style.display = 'none';
                    return;
                }
                
                // Send update
                fetch(saveUrl + encodeURIComponent(newValue), {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-CSRF-Token': csrfToken
                    }
                })
                .then(res => {
                    if (!res.ok) {
                        throw new Error('Network response was not ok');
                    }
                    // 204 No Content - no JSON to parse
                    span.textContent = newValue;
                    span.style.display = 'inline-block';
                    input.style.display = 'none';
                    this.textContent = '✏️';
                    // Ask user to reload the page
                    if (confirm('Hello ' + newValue + '! Do you want to refresh the page to view the changes?')) {
                        window.location.reload();
                    }
                })
                .catch(err => {
                    this.textContent = '✏️';
                    span.style.display = 'inline-block';
                    input.style.display = 'none';
                });
            }
        });
    });
});
