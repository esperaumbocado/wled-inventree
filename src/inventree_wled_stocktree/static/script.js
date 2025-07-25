function toggleTheme() {
    document.documentElement.dataset.theme =
        document.documentElement.dataset.theme === 'dark' ? 'light' : 'dark';
}

function toggleYFields() {
    const ySelect = document.getElementById('wled_instance_id_y');
    const yFields = document.getElementById('y_fields');
    yFields.style.display = ySelect.value ? 'block' : 'none';
}

document.addEventListener('DOMContentLoaded', () => {
    toggleYFields();
});
