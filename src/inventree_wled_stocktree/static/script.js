// WLED Dashboard JavaScript
document.addEventListener('DOMContentLoaded', function() {
    console.log('DOM Content Loaded, initializing dashboard...');
    // Initialize the dashboard
    initializeDashboard();
});

function initializeDashboard() {
    console.log('Initializing dashboard...');
    // Set default active tab
    showTab('devices');
    
    // Add event listeners
    setupEventListeners();
    
    // Update theme based on saved preference
    const savedTheme = localStorage.getItem('theme') || 'light';
    document.documentElement.setAttribute('data-theme', savedTheme);
    updateThemeIcon(savedTheme);
    
    console.log('Dashboard initialized successfully');
}

function setupEventListeners() {
    // Modal event listeners
    setupModalEventListeners();
    
    // Form validation
    setupFormValidation();
}

// Tab Management
function showTab(tabName) {
    // Hide all tab contents
    const tabContents = document.querySelectorAll('.tab-content');
    tabContents.forEach(content => content.classList.remove('active'));
    
    // Remove active class from all tab buttons
    const tabButtons = document.querySelectorAll('.tab-button');
    tabButtons.forEach(button => button.classList.remove('active'));
    
    // Show selected tab content
    const selectedTab = document.getElementById(tabName + '-tab');
    if (selectedTab) {
        selectedTab.classList.add('active');
    }
    
    // Add active class to selected tab button
    const selectedButton = document.querySelector(`[onclick="showTab('${tabName}')"]`);
    if (selectedButton) {
        selectedButton.classList.add('active');
    }
}

// Theme Management
function toggleTheme() {
    const currentTheme = document.documentElement.getAttribute('data-theme');
    const newTheme = currentTheme === 'dark' ? 'light' : 'dark';
    
    document.documentElement.setAttribute('data-theme', newTheme);
    localStorage.setItem('theme', newTheme);
    updateThemeIcon(newTheme);
}

function updateThemeIcon(theme) {
    const themeIcon = document.querySelector('.theme-toggle i');
    if (themeIcon) {
        themeIcon.className = theme === 'dark' ? 'fas fa-sun' : 'fas fa-moon';
    }
}

// Modal Management
function showModal(modalId) {
    console.log('showModal called with:', modalId);
    const modal = document.getElementById(modalId);
    if (modal) {
        console.log('Modal found, showing...');
        modal.classList.add('show');
        document.body.style.overflow = 'hidden';
    } else {
        console.error('Modal not found:', modalId);
    }
}

function closeModal(modalId) {
    console.log('closeModal called with:', modalId);
    const modal = document.getElementById(modalId);
    if (modal) {
        console.log('Modal found, closing...');
        modal.classList.remove('show');
        document.body.style.overflow = '';
    } else {
        console.error('Modal not found:', modalId);
    }
}

function showAddDeviceModal() {
    console.log('showAddDeviceModal called');
    showModal('addDeviceModal');
}

function editDevice(deviceId, deviceName, deviceIp, deviceMaxLeds) {
    console.log('editDevice called with:', deviceId, deviceName, deviceIp, deviceMaxLeds);
    
    // Populate the edit form
    document.getElementById('edit_wled_name').value = deviceName || '';
    document.getElementById('edit_wled_ip').value = deviceIp;
    document.getElementById('edit_wled_max_leds').value = deviceMaxLeds;
    
    // Set the form action
    const form = document.getElementById('editDeviceForm');
    form.action = `/plugin/inventree-wled-stocktree/edit-wled/${deviceId}/`;
    
    showModal('editDeviceModal');
}

function removeDevice(deviceId) {
    console.log('removeDevice called with:', deviceId);
    if (confirm('Are you sure you want to remove this WLED device? All location mappings using this device will be cleared.')) {
        fetch(`/plugin/inventree-wled-stocktree/unregister-wled/${deviceId}/`, {
            method: 'POST',
            headers: {
                'X-CSRFToken': document.querySelector('[name="csrfmiddlewaretoken"]').value
            }
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                showNotification('WLED device removed successfully!', 'success');
                setTimeout(() => location.reload(), 1000);
            } else {
                showNotification(data.error || 'Failed to remove device', 'error');
            }
        })
        .catch(error => {
            console.error('Error:', error);
            showNotification('Network error occurred', 'error');
        });
    }
}

function showAddLocationModal() {
    console.log('showAddLocationModal called');
    const wledInstances = document.querySelectorAll('#wled_instance_id_x option:not([value=""])');
    console.log('WLED instances found:', wledInstances.length);
    if (wledInstances.length === 0) {
        alert('Please add WLED devices first before mapping locations.');
        showTab('devices');
        return;
    }
    
    // Reset form and ensure Y-axis fields are properly initialized
    const form = document.querySelector('#addLocationModal form');
    if (form) {
        form.reset();
        
        // Reset Y-mapping section
        const ySection = document.getElementById('y_mapping_section');
        const yCheckbox = document.getElementById('enable_y_mapping');
        const yFields = ySection.querySelectorAll('input, select');
        
        yCheckbox.checked = false;
        ySection.style.display = 'none';
        
        // Remove any validation attributes from Y-fields and disable them
        yFields.forEach(field => {
            field.setAttribute('disabled', 'disabled');
            field.removeAttribute('required');
            field.value = '';
        });
    }
    
    showModal('addLocationModal');
}

function editLocation(locationId) {
    console.log('editLocation called with:', locationId);
    
    // Find the location data from the table
    const locationRow = document.querySelector(`tr[data-location-id="${locationId}"]`);
    if (!locationRow) {
        console.error('Location row not found');
        return;
    }
    
    // Get location data from data attributes
    const locationName = locationRow.getAttribute('data-location-name');
    const xMin = locationRow.getAttribute('data-x-min');
    const xMax = locationRow.getAttribute('data-x-max');
    const xInstance = locationRow.getAttribute('data-x-instance');
    const yMin = locationRow.getAttribute('data-y-min');
    const yMax = locationRow.getAttribute('data-y-max');
    const yInstance = locationRow.getAttribute('data-y-instance');
    
    console.log('Location data:', { locationName, xMin, xMax, xInstance, yMin, yMax, yInstance });
    
    // Populate the edit form
    document.getElementById('edit_location_name').textContent = locationName;
    document.getElementById('edit_wled_instance_id_x').value = xInstance || '';
    document.getElementById('edit_x_min').value = xMin || '';
    document.getElementById('edit_x_max').value = xMax || '';
    
    // Handle Y-axis mapping
    const hasYMapping = yMin && yMax && yInstance;
    const yMappingCheckbox = document.getElementById('edit_enable_y_mapping');
    const yMappingSection = document.getElementById('edit_y_mapping_section');
    
    if (hasYMapping) {
        yMappingCheckbox.checked = true;
        yMappingSection.style.display = 'block';
        document.getElementById('edit_wled_instance_id_y').value = yInstance;
        document.getElementById('edit_y_min').value = yMin;
        document.getElementById('edit_y_max').value = yMax;
        
        // Enable Y-axis fields
        const yFields = yMappingSection.querySelectorAll('input, select');
        yFields.forEach(field => {
            field.removeAttribute('disabled');
            if (field.name === 'wled_instance_id_y') {
                field.setAttribute('required', 'required');
            }
        });
    } else {
        yMappingCheckbox.checked = false;
        yMappingSection.style.display = 'none';
        document.getElementById('edit_wled_instance_id_y').value = '';
        document.getElementById('edit_y_min').value = '';
        document.getElementById('edit_y_max').value = '';
        
        // Disable Y-axis fields
        const yFields = yMappingSection.querySelectorAll('input, select');
        yFields.forEach(field => {
            field.setAttribute('disabled', 'disabled');
            field.removeAttribute('required');
        });
    }
    
    // Set the form action
    const form = document.getElementById('editLocationForm');
    form.action = `/plugin/inventree-wled-stocktree/edit-location/${locationId}/`;
    
    showModal('editLocationModal');
}

function testLocation(locationId) {
    console.log('testLocation called with:', locationId);
    fetch(`/plugin/inventree-wled-stocktree/locate/${locationId}/`, {
        method: 'POST',
        headers: {
            'X-CSRFToken': document.querySelector('[name="csrfmiddlewaretoken"]').value
        }
    })
    .then(response => {
        if (response.ok) {
            showNotification('Location LEDs activated!', 'success');
        } else {
            showNotification('Failed to test location', 'error');
        }
    })
    .catch(error => {
        console.error('Error:', error);
        showNotification('Network error occurred', 'error');
    });
}

function removeLocation(locationId) {
    console.log('removeLocation called with:', locationId);
    if (confirm('Are you sure you want to remove this location mapping?')) {
        fetch(`/plugin/inventree-wled-stocktree/unregister/${locationId}/`, {
            method: 'POST',
            headers: {
                'X-CSRFToken': document.querySelector('[name="csrfmiddlewaretoken"]').value
            }
        })
        .then(response => {
            if (response.ok) {
                showNotification('Location mapping removed successfully!', 'success');
                setTimeout(() => location.reload(), 1000);
            } else {
                showNotification('Failed to remove location mapping', 'error');
            }
        })
        .catch(error => {
            console.error('Error:', error);
            showNotification('Network error occurred', 'error');
        });
    }
}

function setupModalEventListeners() {
    // Close modal when clicking outside
    document.querySelectorAll('.modal').forEach(modal => {
        modal.addEventListener('click', function(e) {
            if (e.target === modal) {
                closeModal(modal.id);
            }
        });
    });
    
    // Close modal with escape key
    document.addEventListener('keydown', function(e) {
        if (e.key === 'Escape') {
            const openModal = document.querySelector('.modal.show');
            if (openModal) {
                closeModal(openModal.id);
            }
        }
    });
}

// Form Management
function toggleYMapping() {
    const checkbox = document.getElementById('enable_y_mapping');
    const ySection = document.getElementById('y_mapping_section');
    const yFields = ySection.querySelectorAll('input, select');
    
    if (checkbox.checked) {
        ySection.style.display = 'block';
        yFields.forEach(field => {
            field.removeAttribute('disabled');
            // Re-add required attribute for select field when visible
            if (field.name === 'wled_instance_id_y') {
                field.setAttribute('required', 'required');
            }
        });
    } else {
        ySection.style.display = 'none';
        yFields.forEach(field => {
            field.setAttribute('disabled', 'disabled');
            field.removeAttribute('required');
            field.value = '';
        });
    }
}

function toggleEditYMapping() {
    const checkbox = document.getElementById('edit_enable_y_mapping');
    const ySection = document.getElementById('edit_y_mapping_section');
    const yFields = ySection.querySelectorAll('input, select');
    
    if (checkbox.checked) {
        ySection.style.display = 'block';
        yFields.forEach(field => {
            field.removeAttribute('disabled');
            // Re-add required attribute for select field when visible
            if (field.name === 'wled_instance_id_y') {
                field.setAttribute('required', 'required');
            }
        });
    } else {
        ySection.style.display = 'none';
        yFields.forEach(field => {
            field.setAttribute('disabled', 'disabled');
            field.removeAttribute('required');
            field.value = '';
        });
    }
}

function setupFormValidation() {
    // IP address validation
    const ipInputs = document.querySelectorAll('input[name="wled_ip"]');
    ipInputs.forEach(input => {
        input.addEventListener('blur', validateIPAddress);
    });
    
    // LED range validation
    const ledInputs = document.querySelectorAll('input[type="number"]');
    ledInputs.forEach(input => {
        if (input.name.includes('_min') || input.name.includes('_max')) {
            input.addEventListener('change', validateLEDRange);
        }
    });
}

function validateIPAddress(e) {
    const input = e.target;
    const value = input.value.trim();
    const ipPattern = /^(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)$/;
    
    if (value && !ipPattern.test(value)) {
        input.style.borderColor = 'var(--danger)';
        showTooltip(input, 'Please enter a valid IP address (e.g., 192.168.1.100)');
    } else {
        input.style.borderColor = '';
        hideTooltip(input);
    }
}

function validateLEDRange(e) {
    const input = e.target;
    const value = parseInt(input.value);
    
    if (value < 0) {
        input.style.borderColor = 'var(--danger)';
        showTooltip(input, 'LED number cannot be negative');
        return;
    }
    
    // Check if min/max are properly ordered
    const form = input.closest('form');
    if (form) {
        const minInput = form.querySelector('[name$="_min"]');
        const maxInput = form.querySelector('[name$="_max"]');
        
        if (minInput && maxInput && minInput.value && maxInput.value) {
            const min = parseInt(minInput.value);
            const max = parseInt(maxInput.value);
            
            if (min > max) {
                input.style.borderColor = 'var(--danger)';
                showTooltip(input, 'Minimum LED number cannot be greater than maximum');
                return;
            }
        }
    }
    
    input.style.borderColor = '';
    hideTooltip(input);
}

function showTooltip(element, message) {
    hideTooltip(element); // Remove existing tooltip
    
    const tooltip = document.createElement('div');
    tooltip.className = 'field-tooltip';
    tooltip.textContent = message;
    tooltip.style.cssText = `
        position: absolute;
        background: var(--danger);
        color: white;
        padding: 0.5rem;
        border-radius: var(--radius);
        font-size: 0.75rem;
        z-index: 1000;
        max-width: 200px;
        box-shadow: var(--shadow);
    `;
    
    element.parentNode.style.position = 'relative';
    element.parentNode.appendChild(tooltip);
    
    // Position tooltip
    const rect = element.getBoundingClientRect();
    const parentRect = element.parentNode.getBoundingClientRect();
    tooltip.style.top = (rect.bottom - parentRect.top + 5) + 'px';
    tooltip.style.left = '0px';
}

function hideTooltip(element) {
    const tooltip = element.parentNode.querySelector('.field-tooltip');
    if (tooltip) {
        tooltip.remove();
    }
}

// Form Submission
function submitDeviceForm(e) {
    e.preventDefault();
    
    const form = e.target;
    const formData = new FormData(form);
    const submitBtn = form.querySelector('button[type="submit"]');
    
    // Validate form
    const ipInput = form.querySelector('[name="wled_ip"]');
    const ipValue = ipInput.value.trim();
    const ipPattern = /^(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)$/;
    
    if (!ipPattern.test(ipValue)) {
        showNotification('Please enter a valid IP address', 'error');
        return;
    }
    
    // Show loading state
    const originalText = submitBtn.innerHTML;
    submitBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Adding...';
    submitBtn.disabled = true;
    
    // Submit form
    fetch(form.action, {
        method: 'POST',
        body: formData,
        headers: {
            'X-CSRFToken': form.querySelector('[name="csrfmiddlewaretoken"]').value
        }
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            showNotification('WLED device added successfully!', 'success');
            closeModal('addDeviceModal');
            setTimeout(() => location.reload(), 1000);
        } else {
            showNotification(data.error || 'Failed to add device', 'error');
        }
    })
    .catch(error => {
        console.error('Error:', error);
        showNotification('Network error occurred', 'error');
    })
    .finally(() => {
        submitBtn.innerHTML = originalText;
        submitBtn.disabled = false;
    });
}

function submitLocationForm(e) {
    e.preventDefault();
    
    const form = e.target;
    const formData = new FormData(form);
    const submitBtn = form.querySelector('button[type="submit"]');
    
    // Validate all required fields
    const stockLocation = formData.get('stocklocation');
    const xDevice = formData.get('wled_instance_id_x');
    const xMin = formData.get('x_min');
    const xMax = formData.get('x_max');
    
    if (!stockLocation) {
        showNotification('Please select a stock location', 'error');
        return;
    }
    
    if (!xDevice) {
        showNotification('Please select a WLED device for X-axis mapping', 'error');
        return;
    }
    
    if (!xMin || !xMax) {
        showNotification('Please provide X-axis LED range (start and end)', 'error');
        return;
    }
    
    // Custom validation before submission
    const isYMappingEnabled = document.getElementById('enable_y_mapping').checked;
    
    // Validate Y-axis fields if Y-mapping is enabled
    if (isYMappingEnabled) {
        const yDevice = formData.get('wled_instance_id_y');
        const yMin = formData.get('y_min');
        const yMax = formData.get('y_max');
        
        if (!yDevice) {
            showNotification('Please select a WLED device for Y-axis mapping', 'error');
            return;
        }
        if (!yMin || !yMax) {
            showNotification('Please provide Y-axis LED range (start and end)', 'error');
            return;
        }
        if (parseInt(yMin) > parseInt(yMax)) {
            showNotification('Y minimum cannot be greater than Y maximum', 'error');
            return;
        }
    }
    
    // Validate LED ranges
    const xMinNum = parseInt(xMin);
    const xMaxNum = parseInt(xMax);
    
    if (xMinNum > xMaxNum) {
        showNotification('X minimum cannot be greater than X maximum', 'error');
        return;
    }
    
    // Show loading state
    const originalText = submitBtn.innerHTML;
    submitBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Mapping...';
    submitBtn.disabled = true;
    
    // Submit form
    fetch(form.action, {
        method: 'POST',
        body: formData,
        headers: {
            'X-CSRFToken': form.querySelector('[name="csrfmiddlewaretoken"]').value
        }
    })
    .then(response => {
        if (response.ok) {
            showNotification('Location mapped successfully!', 'success');
            closeModal('addLocationModal');
            setTimeout(() => location.reload(), 1000);
        } else {
            showNotification('Failed to map location', 'error');
        }
    })
    .catch(error => {
        console.error('Error:', error);
        showNotification('Network error occurred', 'error');
    })
    .finally(() => {
        submitBtn.innerHTML = originalText;
        submitBtn.disabled = false;
    });
}

// Device Actions
function removeDevice(deviceId) {
    if (!confirm('Are you sure you want to remove this WLED device?')) {
        return;
    }
    
    window.location.href = `/plugin/inventree-wled-stocktree/unregister-wled/${deviceId}/`;
}

function testDevice(ip) {
    showNotification('Testing device...', 'info');
    
    // Simple test by trying to turn on LED 0
    fetch(`http://${ip}/json/state`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({
            "seg": {"i": [0, "FF0000"]}
        })
    })
    .then(response => {
        if (response.ok) {
            showNotification('Device test successful!', 'success');
            // Turn off the LED after 2 seconds
            setTimeout(() => {
                fetch(`http://${ip}/json/state`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({
                        "seg": {"i": [0, "000000"]}
                    })
                });
            }, 2000);
        } else {
            showNotification('Device test failed', 'error');
        }
    })
    .catch(error => {
        console.error('Error testing device:', error);
        showNotification('Cannot reach device', 'error');
    });
}

// Location Actions
function removeLocation(locationId) {
    if (!confirm('Are you sure you want to unmap this location?')) {
        return;
    }
    
    window.location.href = `/plugin/inventree-wled-stocktree/unregister/${locationId}/`;
}

function testLocation(locationId) {
    showNotification('Testing location...', 'info');
    // This would trigger the locate_stock_location function
    // You could implement an AJAX call here to test the location
}

// Utility Functions
function turnOffAllLeds() {
    if (!confirm('Are you sure you want to turn off all LEDs?')) {
        return;
    }
    
    window.location.href = '/plugin/inventree-wled-stocktree/off/';
}

function testAllLocations() {
    showNotification('Testing all locations...', 'info');
    // TODO: Implement test all functionality
}

function showNotification(message, type = 'info') {
    // Remove existing notifications
    const existingNotifications = document.querySelectorAll('.notification');
    existingNotifications.forEach(notification => notification.remove());
    
    // Create notification element
    const notification = document.createElement('div');
    notification.className = `notification notification-${type}`;
    notification.style.cssText = `
        position: fixed;
        top: 1rem;
        right: 1rem;
        padding: 1rem 1.5rem;
        border-radius: var(--radius);
        color: white;
        font-weight: 500;
        z-index: 10000;
        max-width: 300px;
        box-shadow: var(--shadow-lg);
        animation: slideIn 0.3s ease-out;
    `;
    
    // Set background color based on type
    const colors = {
        success: 'var(--success)',
        error: 'var(--danger)',
        warning: 'var(--warning)',
        info: 'var(--primary)'
    };
    notification.style.backgroundColor = colors[type] || colors.info;
    
    // Add icon
    const icons = {
        success: 'fas fa-check-circle',
        error: 'fas fa-exclamation-circle',
        warning: 'fas fa-exclamation-triangle',
        info: 'fas fa-info-circle'
    };
    
    notification.innerHTML = `
        <i class="${icons[type] || icons.info}"></i>
        <span style="margin-left: 0.5rem;">${message}</span>
    `;
    
    // Add to document
    document.body.appendChild(notification);
    
    // Auto-remove after 5 seconds
    setTimeout(() => {
        if (notification.parentNode) {
            notification.style.animation = 'slideOut 0.3s ease-in';
            setTimeout(() => notification.remove(), 300);
        }
    }, 5000);
    
    // Click to dismiss
    notification.addEventListener('click', () => {
        notification.style.animation = 'slideOut 0.3s ease-in';
        setTimeout(() => notification.remove(), 300);
    });
}

// Add CSS animations
const style = document.createElement('style');
style.textContent = `
    @keyframes slideIn {
        from {
            transform: translateX(100%);
            opacity: 0;
        }
        to {
            transform: translateX(0);
            opacity: 1;
        }
    }
    
    @keyframes slideOut {
        from {
            transform: translateX(0);
            opacity: 1;
        }
        to {
            transform: translateX(100%);
            opacity: 0;
        }
    }
    
    .notification {
        cursor: pointer;
        transition: transform 0.2s;
    }
    
    .notification:hover {
        transform: translateY(-2px);
    }
`;
document.head.appendChild(style);

// Toggle Y-axis mapping section
function toggleYMapping() {
    const checkbox = document.getElementById('enable_y_mapping');
    const section = document.getElementById('y_mapping_section');
    
    if (checkbox.checked) {
        section.style.display = 'block';
        // Make Y-axis fields required when enabled
        document.getElementById('wled_instance_id_y').required = true;
        document.getElementById('y_min').required = true;
        document.getElementById('y_max').required = true;
    } else {
        section.style.display = 'none';
        // Remove required attribute when disabled
        document.getElementById('wled_instance_id_y').required = false;
        document.getElementById('y_min').required = false;
        document.getElementById('y_max').required = false;
        // Clear values
        document.getElementById('wled_instance_id_y').value = '';
        document.getElementById('y_min').value = '';
        document.getElementById('y_max').value = '';
    }
}

function submitEditDeviceForm(e) {
    e.preventDefault();
    
    const form = e.target;
    const formData = new FormData(form);
    const submitBtn = form.querySelector('button[type="submit"]');
    
    // Validate form
    const ipInput = form.querySelector('[name="wled_ip"]');
    const ipValue = ipInput.value.trim();
    const ipPattern = /^(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)$/;
    
    if (!ipPattern.test(ipValue)) {
        showNotification('Please enter a valid IP address', 'error');
        return;
    }
    
    // Show loading state
    const originalText = submitBtn.innerHTML;
    submitBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Saving...';
    submitBtn.disabled = true;
    
    // Submit form
    fetch(form.action, {
        method: 'POST',
        body: formData,
        headers: {
            'X-CSRFToken': form.querySelector('[name="csrfmiddlewaretoken"]').value
        }
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            showNotification('WLED device updated successfully!', 'success');
            closeModal('editDeviceModal');
            setTimeout(() => location.reload(), 1000);
        } else {
            showNotification(data.error || 'Failed to update device', 'error');
        }
    })
    .catch(error => {
        console.error('Error:', error);
        showNotification('Network error occurred', 'error');
    })
    .finally(() => {
        submitBtn.innerHTML = originalText;
        submitBtn.disabled = false;
    });
}

function submitEditLocationForm(e) {
    e.preventDefault();
    
    const form = e.target;
    const formData = new FormData(form);
    const submitBtn = form.querySelector('button[type="submit"]');
    
    // Validate all required fields
    const xDevice = formData.get('wled_instance_id_x');
    const xMin = formData.get('x_min');
    const xMax = formData.get('x_max');
    
    if (!xDevice) {
        showNotification('Please select a WLED device for X-axis mapping', 'error');
        return;
    }
    
    if (!xMin || !xMax) {
        showNotification('Please provide X-axis LED range (start and end)', 'error');
        return;
    }
    
    // Custom validation for Y-mapping if enabled
    const isYMappingEnabled = document.getElementById('edit_enable_y_mapping').checked;
    
    if (isYMappingEnabled) {
        const yDevice = formData.get('wled_instance_id_y');
        const yMin = formData.get('y_min');
        const yMax = formData.get('y_max');
        
        if (!yDevice) {
            showNotification('Please select a WLED device for Y-axis mapping', 'error');
            return;
        }
        if (!yMin || !yMax) {
            showNotification('Please provide Y-axis LED range (start and end)', 'error');
            return;
        }
        if (parseInt(yMin) > parseInt(yMax)) {
            showNotification('Y minimum cannot be greater than Y maximum', 'error');
            return;
        }
    }
    
    // Validate LED ranges
    const xMinNum = parseInt(xMin);
    const xMaxNum = parseInt(xMax);
    
    if (xMinNum > xMaxNum) {
        showNotification('X minimum cannot be greater than X maximum', 'error');
        return;
    }
    
    // Show loading state
    const originalText = submitBtn.innerHTML;
    submitBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Saving...';
    submitBtn.disabled = true;
    
    // Submit form
    fetch(form.action, {
        method: 'POST',
        body: formData,
        headers: {
            'X-CSRFToken': form.querySelector('[name="csrfmiddlewaretoken"]').value
        }
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            showNotification('Location mapping updated successfully!', 'success');
            closeModal('editLocationModal');
            setTimeout(() => location.reload(), 1000);
        } else {
            showNotification(data.error || 'Failed to update location mapping', 'error');
        }
    })
    .catch(error => {
        console.error('Error:', error);
        showNotification('Network error occurred', 'error');
    })
    .finally(() => {
        submitBtn.innerHTML = originalText;
        submitBtn.disabled = false;
    });
}
