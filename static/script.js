// ===== DARK MODE TOGGLE =====
const themeToggle = document.getElementById('theme-toggle');
const htmlElement = document.documentElement;

// Check for saved theme
const savedTheme = localStorage.getItem('theme') || 'light';
htmlElement.setAttribute('data-theme', savedTheme);
if (themeToggle) {
    themeToggle.textContent = savedTheme === 'dark' ? '☀️' : '🌙';
}

if (themeToggle) {
    themeToggle.addEventListener('click', () => {
        const currentTheme = htmlElement.getAttribute('data-theme');
        const newTheme = currentTheme === 'dark' ? 'light' : 'dark';
        htmlElement.setAttribute('data-theme', newTheme);
        localStorage.setItem('theme', newTheme);
        themeToggle.textContent = newTheme === 'dark' ? '☀️' : '🌙';
    });
}

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
            const submitBtn = uploadForm.querySelector('button[type="submit"]');

            if (progressBar) progressBar.style.display = 'block';
            if (submitBtn) submitBtn.disabled = true;

            xhr.upload.addEventListener('progress', function(e) {
                if (e.lengthComputable) {
                    const percent = (e.loaded / e.total) * 100;
                    if (progressFill) progressFill.style.width = percent + '%';
                }
            });

            xhr.onload = function() {
                if (progressBar) progressBar.style.display = 'none';
                if (progressFill) progressFill.style.width = '0%';
                if (submitBtn) submitBtn.disabled = false;

                if (xhr.status === 200) {
                    const response = JSON.parse(xhr.responseText);
                    showFlashMessage(response.message || 'File uploaded successfully!', 'success');
                    setTimeout(() => location.reload(), 1500);
                } else {
                    showFlashMessage('Upload failed. Please try again.', 'danger');
                }
            };

            xhr.open('POST', uploadForm.action, true);
            xhr.send(formData);
        });
    }
});

// ===== FLASH MESSAGE HELPER =====
function showFlashMessage(message, category) {
    let flashes = document.querySelector('.flashes');
    if (!flashes) {
        flashes = document.createElement('ul');
        flashes.className = 'flashes';
        const main = document.querySelector('main');
        if (main) main.prepend(flashes);
    }
    const li = document.createElement('li');
    li.className = `flash-${category}`;
    li.textContent = message;
    flashes.appendChild(li);
    setTimeout(() => li.remove(), 5000);
}

// ===== SEARCH FUNCTIONALITY =====
const searchInput = document.getElementById('search-input');
if (searchInput) {
    searchInput.addEventListener('input', function() {
        const query = this.value.toLowerCase();
        const items = document.querySelectorAll('.searchable-item');
        items.forEach(item => {
            const text = item.textContent.toLowerCase();
            item.style.display = text.includes(query) ? 'block' : 'none';
        });
    });
}

// ===== COPY CODE BUTTONS =====
function addCopyButtons() {
    document.querySelectorAll('pre').forEach(pre => {
        if (pre.querySelector('.copy-btn')) return;

        const button = document.createElement('button');
        button.className = 'copy-btn';
        button.textContent = 'Copy';

        button.addEventListener('click', async () => {
            const code = pre.querySelector('code')?.textContent || pre.textContent;
            try {
                await navigator.clipboard.writeText(code);
                button.textContent = 'Copied!';
                setTimeout(() => { button.textContent = 'Copy'; }, 2000);
            } catch (err) {
                button.textContent = 'Error';
            }
        });

        // Ensure pre is wrapped in a container
        if (window.getComputedStyle(pre).position !== 'relative') {
            const wrapper = document.createElement('div');
            wrapper.className = 'code-block-container';
            pre.parentNode.insertBefore(wrapper, pre);
            wrapper.appendChild(pre);
        }
        pre.closest('.code-block-container').appendChild(button);
    });
}

document.addEventListener('DOMContentLoaded', addCopyButtons);
