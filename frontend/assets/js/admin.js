/**
 * CaféNest — Administrator & Staff Operations Portal Logic
 * Pure Vanilla JavaScript communicating with Python/MySQL backend
 */

let adminUser = null;
let currentAdminTab = 'dashboard';
let cachedCategories = [];
let cachedInventory = [];

async function initAdminPortal() {
    await checkAdminAuth();
    if (adminUser) {
        refreshDashboard();
    }
}

async function checkAdminAuth() {
    try {
        const res = await fetch('/api/auth/me');
        const result = await res.json();
        if (result.success && result.authenticated && result.data.user_type === 'staff') {
            adminUser = result.data;
            document.getElementById('staffNameDisplay').textContent = adminUser.name;
            document.getElementById('staffRoleDisplay').textContent = adminUser.role;
            document.getElementById('staffAvatar').textContent = adminUser.name ? adminUser.name[0].toUpperCase() : 'S';
            closeModal('staffLoginModal');
        } else {
            openModal('staffLoginModal');
        }
    } catch (e) {
        openModal('staffLoginModal');
    }
}

async function handleStaffLogin(e) {
    e.preventDefault();
    const email = document.getElementById('staffEmail').value;
    const password = document.getElementById('staffPassword').value;

    try {
        const res = await fetch('/api/auth/login', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ email, password, login_type: 'staff' })
        });
        const result = await res.json();
        if (result.success) {
            showToast(result.message, 'success');
            adminUser = result.data;
            closeModal('staffLoginModal');
            document.getElementById('staffNameDisplay').textContent = adminUser.name;
            document.getElementById('staffRoleDisplay').textContent = adminUser.role;
            refreshDashboard();
        } else {
            showToast(result.message || 'Staff authentication failed.', 'error');
        }
    } catch (err) {
        showToast('Login request error.', 'error');
    }
}

function switchAdminTab(tabName) {
    currentAdminTab = tabName;
    document.querySelectorAll('.admin-nav-item').forEach(el => {
        el.classList.toggle('active', el.getAttribute('data-tab') === tabName);
    });

    document.querySelectorAll('.tab-pane').forEach(pane => {
        pane.style.display = 'none';
    });

    const activePane = document.getElementById(`tabContent-${tabName}`);
    if (activePane) {
        activePane.style.display = 'block';
    }

    if (tabName === 'dashboard') refreshDashboard();
    if (tabName === 'orders') loadAdminOrdersQueue();
    if (tabName === 'menu') loadAdminMenu();
    if (tabName === 'tables') loadAdminTables();
    if (tabName === 'inventory') loadAdminInventory();
    if (tabName === 'staff') loadAdminStaff();
    if (tabName === 'reports') loadAdminReports();
}

// 1. Dashboard Metrics
async function refreshDashboard() {
    try {
        const res = await fetch('/api/admin/dashboard');
        const result = await res.json();
        if (result.success) {
            const data = result.data;
            document.getElementById('kpiTodaySales').textContent = `₹${data.today_sales.toFixed(2)}`;
            document.getElementById('kpiActiveOrders').textContent = data.active_orders;
            document.getElementById('kpiTablesRatio').textContent = `${data.tables.occupied} / ${data.tables.total}`;
            document.getElementById('kpiLowStock').textContent = data.low_stock_count;

            // Render Recent Orders
            const tbody = document.getElementById('dashOrdersTbody');
            if (data.recent_orders && data.recent_orders.length > 0) {
                tbody.innerHTML = data.recent_orders.map(o => `
                    <tr>
                        <td><strong>#${o.order_reference}</strong></td>
                        <td>${o.created_at}</td>
                        <td>${o.customer_name || 'Guest Patron'}</td>
                        <td>${o.order_type} (${o.table_number || 'Takeaway'})</td>
                        <td><strong>₹${o.total_amount.toFixed(2)}</strong></td>
                        <td><span class="badge badge-${o.status.toLowerCase()}">${o.status}</span></td>
                        <td>
                            ${getNextStatusButton(o.order_id, o.status)}
                        </td>
                    </tr>
                `).join('');
            } else {
                tbody.innerHTML = '<tr><td colspan="7" style="text-align: center; padding: 2rem;">No orders today.</td></tr>';
            }

            // Render Popular Items
            const popTbody = document.getElementById('dashPopularTbody');
            if (data.popular_items && data.popular_items.length > 0) {
                popTbody.innerHTML = data.popular_items.map(p => `
                    <tr>
                        <td><strong>${p.name}</strong></td>
                        <td>${p.category_name}</td>
                        <td>₹${p.price.toFixed(2)}</td>
                        <td><strong style="color: var(--secondary);">${p.total_sold} units</strong></td>
                        <td><strong>₹${p.total_revenue.toFixed(2)}</strong></td>
                    </tr>
                `).join('');
            }
        }
    } catch (e) {
        console.error('Error refreshing dashboard:', e);
    }
}

function getNextStatusButton(orderId, currentStatus) {
    const transitions = {
        'Pending': 'Confirmed',
        'Confirmed': 'Preparing',
        'Preparing': 'Ready',
        'Ready': 'Completed'
    };

    const next = transitions[currentStatus];
    if (!next) {
        return `<span style="color: var(--text-muted); font-size: 0.8rem;">${currentStatus}</span>`;
    }

    return `
        <button onclick="advanceOrderStatus(${orderId}, '${next}')" class="btn btn-amber btn-sm" style="padding: 0.25rem 0.6rem; font-size: 0.75rem;">
            Advance to ${next} ➔
        </button>
    `;
}

async function advanceOrderStatus(orderId, nextStatus) {
    try {
        const res = await fetch('/api/orders/update-status', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ order_id: orderId, status: nextStatus })
        });
        const result = await res.json();
        if (result.success) {
            showToast(result.message, 'success');
            if (currentAdminTab === 'dashboard') refreshDashboard();
            if (currentAdminTab === 'orders') loadAdminOrdersQueue();
        } else {
            showToast(result.message, 'error');
        }
    } catch (e) {
        showToast('Error updating status.', 'error');
    }
}

// 2. Orders Queue
let activeQueueFilter = null;

async function loadAdminOrdersQueue() {
    try {
        let url = '/api/orders?limit=100';
        if (activeQueueFilter) url += `&status=${activeQueueFilter}`;

        const res = await fetch(url);
        const result = await res.json();
        const tbody = document.getElementById('ordersManagementTbody');

        if (result.success && result.data.length > 0) {
            tbody.innerHTML = result.data.map(o => `
                <tr>
                    <td><strong>#${o.order_reference}</strong></td>
                    <td>${o.created_at}</td>
                    <td>${o.customer_name || 'Walk-in Guest'}<br><small style="color: var(--text-light);">${o.customer_phone || ''}</small></td>
                    <td>${o.order_type}<br><small>${o.table_number || 'Pickup'}</small></td>
                    <td><strong>₹${o.total_amount.toFixed(2)}</strong></td>
                    <td><span style="font-size: 0.8rem;">${o.payment_method || 'Unpaid'}</span></td>
                    <td><span class="badge badge-${o.status.toLowerCase()}">${o.status}</span></td>
                    <td>
                        <div style="display: flex; gap: 0.4rem; flex-wrap: wrap;">
                            ${getNextStatusButton(o.order_id, o.status)}
                            ${o.status !== 'Cancelled' && o.status !== 'Completed' ? `
                                <button onclick="advanceOrderStatus(${o.order_id}, 'Cancelled')" class="btn btn-secondary btn-sm" style="padding: 0.25rem 0.5rem; font-size: 0.72rem; color: var(--non-veg);">
                                    Cancel
                                </button>
                            ` : ''}
                        </div>
                    </td>
                </tr>
            `).join('');
        } else {
            tbody.innerHTML = '<tr><td colspan="8" style="text-align: center; padding: 2rem;">No orders matching selected filter.</td></tr>';
        }
    } catch (e) {
        console.error(e);
    }
}

function filterOrderQueue(status, btn) {
    activeQueueFilter = status;
    document.querySelectorAll('#tabContent-orders .cat-pill').forEach(b => b.classList.remove('active'));
    if (btn) btn.classList.add('active');
    loadAdminOrdersQueue();
}

// 3. Menu Management
async function loadAdminMenu() {
    try {
        const catRes = await fetch('/api/menu/categories');
        const catData = await catRes.json();
        if (catData.success) {
            cachedCategories = catData.data;
            const sel = document.getElementById('menuCategorySelect');
            sel.innerHTML = cachedCategories.map(c => `<option value="${c.category_id}">${c.category_name}</option>`).join('');
        }

        const res = await fetch('/api/menu?include_unavailable=true');
        const result = await res.json();
        const tbody = document.getElementById('menuAdminTbody');

        if (result.success) {
            tbody.innerHTML = result.data.map(item => `
                <tr>
                    <td>
                        <div style="display: flex; align-items: center; gap: 0.8rem;">
                            <img src="${item.image_url}" alt="${item.name}" style="width: 44px; height: 44px; border-radius: var(--radius-sm); object-fit: cover;">
                            <div>
                                <strong>${item.name}</strong>
                                <div style="font-size: 0.75rem; color: var(--text-light); max-width: 250px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">
                                    ${item.description || ''}
                                </div>
                            </div>
                        </div>
                    </td>
                    <td>${item.category_name}</td>
                    <td>
                        <span class="diet-tag ${item.is_veg ? 'veg' : 'non-veg'}" style="font-size: 0.7rem;">
                            ${item.is_veg ? 'Veg' : 'Non-Veg'}
                        </span>
                    </td>
                    <td><strong>₹${item.price.toFixed(2)}</strong></td>
                    <td>
                        <button onclick="toggleItemAvailability(${item.menu_id})" class="btn btn-sm ${item.is_available ? 'btn-secondary' : 'btn-danger'}" style="padding: 0.2rem 0.6rem; font-size: 0.75rem;">
                            ${item.is_available ? '🟢 In Stock' : '🔴 Sold Out'}
                        </button>
                    </td>
                    <td>
                        <button onclick="editMenuItem(${JSON.stringify(item).replace(/"/g, '&quot;')})" class="btn btn-secondary btn-sm" style="padding: 0.2rem 0.6rem; font-size: 0.75rem;">
                            ✏️ Edit / Price
                        </button>
                    </td>
                </tr>
            `).join('');
        }
    } catch (e) {
        console.error(e);
    }
}

async function toggleItemAvailability(menuId) {
    try {
        const res = await fetch('/api/menu/toggle-availability', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ menu_id: menuId })
        });
        const result = await res.json();
        if (result.success) {
            showToast(result.message, 'info');
            loadAdminMenu();
        }
    } catch (e) {
        showToast('Error toggling availability.', 'error');
    }
}

function openAddMenuModal() {
    document.getElementById('menuModalTitle').textContent = 'Add New Menu Item';
    document.getElementById('menuEditId').value = '';
    document.getElementById('menuName').value = '';
    document.getElementById('menuPrice').value = '';
    document.getElementById('menuDesc').value = '';
    document.getElementById('menuImageUrl').value = '';
    document.getElementById('menuIsVeg').checked = true;
    document.getElementById('menuIsAvailable').checked = true;
    openModal('menuItemModal');
}

function editMenuItem(item) {
    document.getElementById('menuModalTitle').textContent = `Edit '${item.name}'`;
    document.getElementById('menuEditId').value = item.menu_id;
    document.getElementById('menuName').value = item.name;
    document.getElementById('menuCategorySelect').value = item.category_id;
    document.getElementById('menuPrice').value = item.price;
    document.getElementById('menuDesc').value = item.description || '';
    document.getElementById('menuImageUrl').value = item.image_url || '';
    document.getElementById('menuIsVeg').checked = item.is_veg;
    document.getElementById('menuIsAvailable').checked = item.is_available;
    openModal('menuItemModal');
}

async function handleSaveMenuItem(e) {
    e.preventDefault();
    const menuId = document.getElementById('menuEditId').value;
    const payload = {
        menu_id: menuId ? parseInt(menuId) : null,
        name: document.getElementById('menuName').value,
        category_id: parseInt(document.getElementById('menuCategorySelect').value),
        price: parseFloat(document.getElementById('menuPrice').value),
        description: document.getElementById('menuDesc').value,
        image_url: document.getElementById('menuImageUrl').value,
        is_veg: document.getElementById('menuIsVeg').checked,
        is_available: document.getElementById('menuIsAvailable').checked
    };

    try {
        const res = await fetch('/api/menu/save', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        const result = await res.json();
        if (result.success) {
            showToast(result.message, 'success');
            closeModal('menuItemModal');
            loadAdminMenu();
        } else {
            showToast(result.message, 'error');
        }
    } catch (e) {
        showToast('Error saving item.', 'error');
    }
}

// 4. Cafe Tables Grid
async function loadAdminTables() {
    try {
        const res = await fetch('/api/tables');
        const result = await res.json();
        const container = document.getElementById('tablesGridContainer');

        if (result.success) {
            container.innerHTML = result.data.map(t => {
                let badgeClass = 'badge-ok';
                if (t.status === 'Occupied') badgeClass = 'badge-preparing';
                if (t.status === 'Reserved') badgeClass = 'badge-pending';

                return `
                    <div class="cart-card" style="padding: 1.2rem; display: flex; flex-direction: column; justify-content: space-between; border-left: 5px solid ${t.status === 'Available' ? 'var(--tertiary)' : (t.status === 'Occupied' ? 'var(--secondary)' : '#856404')};">
                        <div>
                            <div style="display: flex; justify-content: space-between; align-items: start; margin-bottom: 0.6rem;">
                                <h3 style="font-size: 1.25rem;">${t.table_number}</h3>
                                <span class="badge ${badgeClass}">${t.status}</span>
                            </div>
                            <div style="font-size: 0.85rem; color: var(--text-muted); margin-bottom: 0.3rem;">
                                Capacity: <strong>${t.seating_capacity} Guests</strong>
                            </div>
                            <div style="font-size: 0.8rem; color: var(--text-light); margin-bottom: 0.8rem;">
                                Area: ${t.location_area}
                            </div>
                            ${t.active_order_ref ? `
                                <div style="background: var(--surface-card); padding: 0.5rem; border-radius: var(--radius-sm); border: 1px dashed var(--border); font-size: 0.8rem; margin-bottom: 0.8rem;">
                                    Active Order: <strong>#${t.active_order_ref}</strong> (${t.active_order_status})
                                </div>
                            ` : ''}
                        </div>

                        <div style="display: flex; gap: 0.3rem; margin-top: 0.8rem;">
                            <button onclick="setTableStatus(${t.table_id}, 'Available')" class="btn btn-secondary btn-sm" style="flex: 1; padding: 0.2rem; font-size: 0.72rem; ${t.status === 'Available' ? 'background: var(--surface-alt);' : ''}">Free</button>
                            <button onclick="setTableStatus(${t.table_id}, 'Occupied')" class="btn btn-secondary btn-sm" style="flex: 1; padding: 0.2rem; font-size: 0.72rem; ${t.status === 'Occupied' ? 'background: #FFE8D6;' : ''}">Occupy</button>
                            <button onclick="setTableStatus(${t.table_id}, 'Reserved')" class="btn btn-secondary btn-sm" style="flex: 1; padding: 0.2rem; font-size: 0.72rem; ${t.status === 'Reserved' ? 'background: #FFF3CD;' : ''}">Reserve</button>
                        </div>
                    </div>
                `;
            }).join('');
        }
    } catch (e) {
        console.error(e);
    }
}

async function setTableStatus(tableId, status) {
    try {
        const res = await fetch('/api/tables/status', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ table_id: tableId, status })
        });
        const result = await res.json();
        if (result.success) {
            showToast(result.message, 'info');
            loadAdminTables();
        }
    } catch (e) {
        showToast('Error updating table.', 'error');
    }
}

// 5. Inventory & Suppliers
async function loadAdminInventory() {
    try {
        const res = await fetch('/api/inventory');
        const result = await res.json();
        const tbody = document.getElementById('inventoryTbody');

        if (result.success) {
            cachedInventory = result.data;
            tbody.innerHTML = result.data.map(item => `
                <tr>
                    <td><strong>${item.item_name}</strong></td>
                    <td><strong style="color: ${item.is_low_stock ? 'var(--non-veg)' : 'inherit'}; font-size: 1.05rem;">${item.quantity.toFixed(1)}</strong></td>
                    <td>${item.unit}</td>
                    <td>${item.reorder_level.toFixed(1)} ${item.unit}</td>
                    <td>${item.supplier_name || 'Direct Wholesale'}</td>
                    <td>
                        ${item.is_low_stock ? `
                            <span class="badge badge-low-stock">⚠️ LOW STOCK ALERT</span>
                        ` : `
                            <span class="badge badge-ok">✓ Healthy</span>
                        `}
                    </td>
                    <td>
                        <button onclick="quickStockAdjust(${item.inventory_id})" class="btn btn-secondary btn-sm" style="padding: 0.2rem 0.6rem; font-size: 0.75rem;">
                            ± Adjust
                        </button>
                    </td>
                </tr>
            `).join('');
        }

        // Movements log
        const movRes = await fetch('/api/inventory/movements');
        const movData = await movRes.json();
        const movTbody = document.getElementById('movementsTbody');
        if (movData.success) {
            movTbody.innerHTML = movData.data.map(m => `
                <tr>
                    <td>${m.created_at}</td>
                    <td><strong>${m.item_name}</strong></td>
                    <td>
                        <strong style="color: ${m.quantity_change > 0 ? 'var(--tertiary)' : 'var(--non-veg)'};">
                            ${m.quantity_change > 0 ? '+' : ''}${m.quantity_change} ${m.unit}
                        </strong>
                    </td>
                    <td><span class="badge badge-ok">${m.reason}</span></td>
                    <td>${m.staff_name || 'Staff'}</td>
                    <td><small style="color: var(--text-muted);">${m.notes || '-'}</small></td>
                </tr>
            `).join('');
        }
    } catch (e) {
        console.error(e);
    }
}

function openStockMovementModal() {
    const sel = document.getElementById('stockItemSelect');
    sel.innerHTML = cachedInventory.map(i => `
        <option value="${i.inventory_id}">${i.item_name} (Current: ${i.quantity} ${i.unit})</option>
    `).join('');
    openModal('stockMovementModal');
}

function quickStockAdjust(invId) {
    openStockMovementModal();
    document.getElementById('stockItemSelect').value = invId;
}

async function handleSaveStockMovement(e) {
    e.preventDefault();
    const payload = {
        inventory_id: parseInt(document.getElementById('stockItemSelect').value),
        quantity_change: parseFloat(document.getElementById('stockQtyChange').value),
        reason: document.getElementById('stockReasonSelect').value,
        notes: document.getElementById('stockNotes').value
    };

    try {
        const res = await fetch('/api/inventory/movement', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        const result = await res.json();
        if (result.success) {
            showToast(result.message, 'success');
            closeModal('stockMovementModal');
            loadAdminInventory();
        } else {
            showToast(result.message, 'error');
        }
    } catch (e) {
        showToast('Error recording stock movement.', 'error');
    }
}

function openAddSupplierModal() {
    openModal('supplierModal');
}

async function handleSaveSupplier(e) {
    e.preventDefault();
    const payload = {
        supplier_name: document.getElementById('supName').value,
        contact_name: document.getElementById('supContact').value,
        phone: document.getElementById('supPhone').value,
        supplied_items: document.getElementById('supItems').value
    };

    try {
        const res = await fetch('/api/inventory/suppliers', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        const result = await res.json();
        if (result.success) {
            showToast(result.message, 'success');
            closeModal('supplierModal');
            loadAdminInventory();
        } else {
            showToast(result.message, 'error');
        }
    } catch (e) {
        showToast('Error adding supplier.', 'error');
    }
}

// 6. Staff Management
async function loadAdminStaff() {
    try {
        const res = await fetch('/api/staff');
        const result = await res.json();
        const tbody = document.getElementById('staffTbody');

        if (result.success) {
            tbody.innerHTML = result.data.map(s => `
                <tr>
                    <td><strong>${s.name}</strong></td>
                    <td>${s.email}</td>
                    <td>${s.phone || '-'}</td>
                    <td><span class="badge badge-confirmed">${s.role}</span></td>
                    <td>
                        <span class="badge ${s.is_active ? 'badge-ok' : 'badge-cancelled'}">
                            ${s.is_active ? 'Active' : 'Inactive'}
                        </span>
                    </td>
                    <td>
                        <button onclick="toggleStaffActive(${s.staff_id})" class="btn btn-secondary btn-sm" style="padding: 0.2rem 0.5rem; font-size: 0.72rem;">
                            ${s.is_active ? 'Deactivate' : 'Activate'}
                        </button>
                    </td>
                </tr>
            `).join('');
        }
    } catch (e) {
        console.error(e);
    }
}

function openAddStaffModal() {
    openModal('staffModal');
}

async function handleSaveStaff(e) {
    e.preventDefault();
    const payload = {
        name: document.getElementById('newStaffName').value,
        email: document.getElementById('newStaffEmail').value,
        role: document.getElementById('newStaffRole').value,
        password: document.getElementById('newStaffPassword').value
    };

    try {
        const res = await fetch('/api/staff', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        const result = await res.json();
        if (result.success) {
            showToast(result.message, 'success');
            closeModal('staffModal');
            loadAdminStaff();
        } else {
            showToast(result.message, 'error');
        }
    } catch (e) {
        showToast('Error saving staff member.', 'error');
    }
}

async function toggleStaffActive(staffId) {
    try {
        const res = await fetch('/api/staff/toggle', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ staff_id: staffId })
        });
        const result = await res.json();
        if (result.success) {
            showToast(result.message, 'info');
            loadAdminStaff();
        }
    } catch (e) {
        showToast('Error updating staff status.', 'error');
    }
}

// 7. Sales Reports & Analytics
async function loadAdminReports() {
    try {
        const res = await fetch('/api/admin/sales');
        const result = await res.json();
        if (result.success) {
            const data = result.data;

            // Category breakdown
            const catList = document.getElementById('categoryReportList');
            if (data.category_breakdown) {
                catList.innerHTML = data.category_breakdown.map(c => `
                    <div style="display: flex; justify-content: space-between; align-items: center; padding: 0.6rem 0; border-bottom: 1px solid var(--border-light);">
                        <div>
                            <strong>${c.category_name}</strong>
                            <div style="font-size: 0.78rem; color: var(--text-light);">${c.items_sold} units sold</div>
                        </div>
                        <div style="font-size: 1.1rem; font-weight: 700; color: var(--primary);">₹${c.revenue.toFixed(2)}</div>
                    </div>
                `).join('');
            }

            // Payment breakdown
            const payList = document.getElementById('paymentMethodsReport');
            if (data.payment_breakdown) {
                payList.innerHTML = data.payment_breakdown.map(p => `
                    <div style="display: flex; justify-content: space-between; align-items: center; padding: 0.6rem 0; border-bottom: 1px solid var(--border-light);">
                        <div>
                            <strong>${p.method === 'Simulated_UPI' ? '📱 Simulated UPI' : '💵 Cash on Delivery / Counter'}</strong>
                            <div style="font-size: 0.78rem; color: var(--text-light);">${p.count} transactions</div>
                        </div>
                        <div style="font-size: 1.1rem; font-weight: 700; color: var(--secondary);">₹${p.total.toFixed(2)}</div>
                    </div>
                `).join('');
            }
        }
    } catch (e) {
        console.error(e);
    }
}

document.addEventListener('DOMContentLoaded', initAdminPortal);
