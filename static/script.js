// ===== DARK MODE TOGGLE =====
const themeToggle = document.getElementById('theme-toggle');
const htmlElement = document.documentElement;

// Check for saved theme
const savedTheme = localStorage.getItem('theme') || 'light';
htmlElement.setAttribute('data-theme', savedTheme);
themeToggle.textContent = savedTheme === 'dark' ? '☀️' : '🌙';

themeToggle.addEventListener('click', () => {
    const currentTheme = htmlElement.getAttribute('data-theme');
    const newTheme = currentTheme === 'dark' ? 'light' : 'dark';
    htmlElement.setAttribute('data-theme', newTheme);
    localStorage.setItem('theme', newTheme);
    themeToggle.textContent = newTheme === 'dark' ? '☀️' : '🌙';
});

// ===== SEARCH FUNCTIONALITY =====
// (Works on tools and blog pages with class .searchable-container)
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
        // Avoid adding multiple buttons
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

        // Wrap pre in a relative container if not already
        if (window.getComputedStyle(pre).position !== 'relative') {
            const wrapper = document.createElement('div');
            wrapper.className = 'code-block-container';
            pre.parentNode.insertBefore(wrapper, pre);
            wrapper.appendChild(pre);
        }
        pre.closest('.code-block-container').appendChild(button);
    });
}

// Run after page load and after any dynamic content changes
document.addEventListener('DOMContentLoaded', addCopyButtons);
// Also run after HTMX or similar if you use it
