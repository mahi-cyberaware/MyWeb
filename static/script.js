// ===== UPLOAD PROGRESS BAR =====
document.addEventListener('DOMContentLoaded', function() {
    const uploadForm = document.getElementById('uploadForm');
    if (uploadForm) {
        uploadForm.addEventListener('submit', function(e) {
            e.preventDefault();
            const formData = new FormData(uploadForm);
            const xhr = new XMLHttpRequest();
            const progressBar = document.getElementById('progress-bar');
            const progressFill = document.getElementById('progress-fill');

            if (progressBar) progressBar.style.display = 'block';

            xhr.upload.addEventListener('progress', function(e) {
                if (e.lengthComputable) {
                    const percent = (e.loaded / e.total) * 100;
                    if (progressFill) progressFill.style.width = percent + '%';
                }
            });

            xhr.onload = function() {
                if (xhr.status === 200) {
                    const response = JSON.parse(xhr.responseText);
                    if (response.message) {
                        flashMessage(response.message, 'success');
                    }
                    setTimeout(() => location.reload(), 1000);
                } else {
                    flashMessage('Upload failed', 'danger');
                }
                if (progressBar) progressBar.style.display = 'none';
                if (progressFill) progressFill.style.width = '0%';
            };

            xhr.open('POST', uploadForm.action, true);
            xhr.send(formData);
        });
    }
});

// Flash message helper
function flashMessage(message, category) {
    const flashes = document.querySelector('.flashes');
    if (!flashes) {
        const newFlashes = document.createElement('ul');
        newFlashes.className = 'flashes';
        document.querySelector('main').prepend(newFlashes);
    }
    const li = document.createElement('li');
    li.className = `flash-${category}`;
    li.textContent = message;
    document.querySelector('.flashes').appendChild(li);
    setTimeout(() => li.remove(), 5000);
}
