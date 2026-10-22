/**
 * CaféNest — Core Frontend Application (Vanilla JavaScript)
 * Handles API communications, Auth state, Cart state, and UI feedback
 */

const API_BASE = '/api';

// Cart Management State
const Cart = {
    items: [],

    init() {
        try {
            const saved = localStorage.getItem('cafenest_cart');
            if (saved) {
                this.items = JSON.parse(saved);
            }
        } catch (e) {
            this.items = [];
        }
        this.updateBadge();
        this.renderFloatingBasket();
    },

    save() {
        localStorage.setItem('cafenest_cart', JSON.stringify(this.items));
        this.updateBadge();
        this.renderFloatingBasket();
        // Dispatch custom event for pages listening to cart changes
        window.dispatchEvent(new CustomEvent('cartUpdated', { detail: { items: this.items } }));
    },

    addItem(menuItem, qty = 1) {
        const existing = this.items.find(i => i.menu_id === menuItem.menu_id);
        if (existing) {
            existing.quantity += qty;
        } else {
            this.items.push({
                menu_id: menuItem.menu_id,
                name: menuItem.name,
                price: parseFloat(menuItem.price),
                image_url: menuItem.image_url,
                is_veg: menuItem.is_veg,
                quantity: qty
            });
        }
        this.save();
        showToast(`Added ${menuItem.name} to cup!`, 'success');
    },

    updateQuantity(menuId, qty) {
        const item = this.items.find(i => i.menu_id === menuId);
        if (item) {
            item.quantity = qty;
            if (item.quantity <= 0) {
                this.items = this.items.filter(i => i.menu_id !== menuId);
                showToast(`Removed item from cart.`, 'info');
            }
            this.save();
        }
    },

    removeItem(menuId) {
        this.items = this.items.filter(i => i.menu_id !== menuId);
        this.save();
        showToast('Item removed.', 'info');
    },

    clear() {
        this.items = [];
        this.save();
    },

    getItemCount() {
        return this.items.reduce((sum, i) => sum + i.quantity, 0);
    },

    getSubtotal() {
        return this.items.reduce((sum, i) => sum + (i.price * i.quantity), 0);
    },

    updateBadge() {
        const badges = document.querySelectorAll('.cart-badge');
        const count = this.getItemCount();
        badges.forEach(b => {
            b.textContent = count;
            b.style.display = count > 0 ? 'inline-block' : 'none';
        });
    },

    renderFloatingBasket() {
        const floating = document.getElementById('floatingBasket');
        if (!floating) return;

        const count = this.getItemCount();
        const total = this.getSubtotal();

        if (count > 0 && !window.location.pathname.includes('cart.html') && !window.location.pathname.includes('checkout.html')) {
            floating.classList.add('show');
            const countEl = floating.querySelector('.basket-item-count');
            const totalEl = floating.querySelector('.basket-total');
            if (countEl) countEl.textContent = `${count} ${count === 1 ? 'item' : 'items'}`;
            if (totalEl) totalEl.textContent = `₹${total.toFixed(2)}`;
        } else {
            floating.classList.remove('show');
        }
    }
};

// Toast Notifications
function showToast(message, type = 'info') {
    let container = document.getElementById('toastContainer');
    if (!container) {
        container = document.createElement('div');
        container.id = 'toastContainer';
        container.className = 'toast-container';
        document.body.appendChild(container);
    }

    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    
    let icon = '☕';
    if (type === 'success') icon = '✓';
    if (type === 'error') icon = '✕';

    toast.innerHTML = `<span>${icon}</span> <span>${message}</span>`;
    container.appendChild(toast);

    setTimeout(() => {
        toast.style.opacity = '0';
        toast.style.transform = 'translateY(-10px)';
        toast.style.transition = 'all 0.3s ease';
        setTimeout(() => toast.remove(), 300);
    }, 3200);
}

// Current User State
let currentUser = null;

async function checkAuth() {
    try {
        const res = await fetch(`${API_BASE}/auth/me`);
        const data = await res.json();
        if (data.success && data.authenticated) {
            currentUser = data.data;
            updateNavAuthUI(currentUser);
        } else {
            currentUser = null;
            updateNavAuthUI(null);
        }
    } catch (e) {
        currentUser = null;
        updateNavAuthUI(null);
    }
}

function updateNavAuthUI(user) {
    const authContainer = document.getElementById('navAuthContainer');
    if (!authContainer) return;

    if (user) {
        if (user.user_type === 'staff') {
            authContainer.innerHTML = `
                <a href="/frontend/administrator/index.html" class="btn btn-secondary btn-sm">Portal (${user.role})</a>
                <button onclick="handleLogout()" class="btn btn-primary btn-sm">Logout</button>
            `;
        } else {
            authContainer.innerHTML = `
                <a href="/frontend/customer/profile.html" class="btn btn-secondary btn-sm">👤 ${user.name.split(' ')[0]}</a>
                <button onclick="handleLogout()" class="btn btn-primary btn-sm">Logout</button>
            `;
        }
    } else {
        authContainer.innerHTML = `
            <a href="/frontend/customer/profile.html#login" class="btn btn-primary btn-sm">Sign In</a>
        `;
    }
}

async function handleLogout() {
    try {
        await fetch(`${API_BASE}/auth/logout`, { method: 'POST' });
        showToast('Logged out successfully.', 'info');
        setTimeout(() => {
            window.location.href = '/';
        }, 600);
    } catch (e) {
        window.location.reload();
    }
}

// Global modal helpers
function openModal(id) {
    const modal = document.getElementById(id);
    if (modal) modal.classList.add('open');
}

function closeModal(id) {
    const modal = document.getElementById(id);
    if (modal) modal.classList.remove('open');
}

// Initialize on DOM load
document.addEventListener('DOMContentLoaded', () => {
    Cart.init();
    checkAuth();
});
