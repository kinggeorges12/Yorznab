performReset = function() {
    const resetButton = document.getElementById('resetBtn');
    const btn = document.querySelector('.reset-btn');
    const originalText = btn.innerHTML;
    btn.innerHTML = '⏳ Resetting...';
    btn.disabled = true;
    
    fetch(resetButton.dataset.reset, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRF-Token': resetButton.dataset.csrf
        },
        body: JSON.stringify({ confirm: true })
    })
    .then(response => {
        // Check if it's a redirect
        if (response.redirected) {
            alert('✅ Keys reset successfully!');
            window.location.href = response.url;  // Follow redirect manually
            return;
        }
        
        if (!response.ok) {
            throw new Error('Reset failed with status: ' + response.status);
        }
        return response.json();
    })
    .catch(error => {
        alert('❌ ' + error.message);
        btn.innerHTML = originalText;
        btn.disabled = false;
    });
};
    
document.addEventListener('DOMContentLoaded', function() {
    window.confirmReset = function() {
        if (confirm("⚠️ Are you sure you want to reset ALL keys?\n\nThis action cannot be undone!")) {
            performReset();
        }
    };
});