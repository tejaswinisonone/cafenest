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

// 1. Dashboard Metrics & Date Filters
let dashFilterStartDate = '';
let dashFilterEndDate = '';
let cachedLowStockItems = [];

async function refreshDashboard() {
    const tbody = document.getElementById('dashOrdersTbody');
    const popTbody = document.getElementById('dashPopularTbody');
    const btn = document.getElementById('btnRefreshDash');
    if (btn) btn.disabled = true;

    try {
        let url = '/api/admin/dashboard';
        const params = new URLSearchParams();
        if (dashFilterStartDate) params.append('start_date', dashFilterStartDate);
        if (dashFilterEndDate) params.append('end_date', dashFilterEndDate);
        const q = params.toString();
        if (q) url += `?${q}`;

        const res = await fetch(url);
        const result = await res.json();

        if (!result.success) {
            showToast(result.message || 'Failed to fetch dashboard metrics.', 'error');
            if (tbody) tbody.innerHTML = `<tr><td colspan="8" style="text-align: center; color: var(--non-veg); padding: 2rem;">Error: ${result.message || 'Server error'}</td></tr>`;
            return;
        }

        const data = result.data;
        const summary = data.summary || {};
        cachedLowStockItems = data.low_stock_items || [];

        // 1. Five Summary Cards (Live SQL Calculations)
        const totalOrders = summary.total_orders ?? 0;
        const totalSales = summary.total_sales ?? 0.0;
        const settledSales = summary.settled_sales ?? 0.0;
        const pendingSales = summary.pending_sales ?? 0.0;
        const pendingOrders = summary.pending_orders ?? 0;
        const activeOrders = summary.active_orders ?? 0;
        const completedOrders = summary.completed_orders ?? 0;
        const lowStockCount = summary.low_stock_count ?? (data.low_stock_count ?? 0);

        if (document.getElementById('kpiTotalOrders')) document.getElementById('kpiTotalOrders').textContent = totalOrders;
        if (document.getElementById('kpiTotalSales')) document.getElementById('kpiTotalSales').textContent = `₹${totalSales.toFixed(2)}`;
        if (document.getElementById('kpiSettledSales')) document.getElementById('kpiSettledSales').textContent = `₹${settledSales.toFixed(2)}`;
        if (document.getElementById('kpiPendingSales')) document.getElementById('kpiPendingSales').textContent = `₹${pendingSales.toFixed(2)}`;
        if (document.getElementById('kpiPendingOrders')) document.getElementById('kpiPendingOrders').textContent = pendingOrders;
        if (document.getElementById('kpiActiveOrders')) document.getElementById('kpiActiveOrders').textContent = activeOrders;
        if (document.getElementById('kpiCompletedOrders')) document.getElementById('kpiCompletedOrders').textContent = completedOrders;
        if (document.getElementById('kpiLowStock')) document.getElementById('kpiLowStock').textContent = lowStockCount;

        // Legacy / fallback element IDs
        if (document.getElementById('kpiTodaySales')) document.getElementById('kpiTodaySales').textContent = `₹${totalSales.toFixed(2)}`;
        if (document.getElementById('kpiTablesRatio') && data.tables) {
            document.getElementById('kpiTablesRatio').textContent = `${data.tables.occupied} / ${data.tables.total}`;
        }

        // Last updated timestamp
        const timeSpan = document.getElementById('dashLastUpdated');
        if (timeSpan) {
            timeSpan.textContent = `Updated: ${new Date().toLocaleTimeString()}`;
        }

        // 2. Recent Orders Queue
        if (tbody) {
            if (data.recent_orders && data.recent_orders.length > 0) {
                tbody.innerHTML = data.recent_orders.map(o => `
                    <tr>
                        <td><strong>#${o.order_reference}</strong></td>
                        <td><small style="color: var(--text-muted);">${o.created_at || 'Just now'}</small></td>
                        <td>${o.customer_name || 'Walk-in Patron'}</td>
                        <td>
                            <span style="font-weight: 600;">${o.order_type}</span>
                            ${o.table_number ? `<span class="badge badge-confirmed" style="margin-left: 0.3rem;">Table ${o.table_number}</span>` : '<span style="color: var(--text-muted); font-size: 0.8rem;"> (Counter)</span>'}
                        </td>
                        <td><strong style="color: var(--primary);">₹${o.total_amount.toFixed(2)}</strong></td>
                        <td>
                            <span class="badge badge-${(o.payment_status || 'Pending').toLowerCase()}">${o.payment_status || 'Pending'}</span>
                            <small style="display: block; font-size: 0.72rem; color: var(--text-muted);">${o.payment_method || 'Cash'}</small>
                        </td>
                        <td><span class="badge badge-${o.status.toLowerCase()}">${o.status}</span></td>
                        <td>
                            ${getNextStatusButton(o.order_id, o.status)}
                        </td>
                    </tr>
                `).join('');
            } else {
                tbody.innerHTML = '<tr><td colspan="8" style="text-align: center; padding: 2rem; color: var(--text-muted);">No orders found for the selected period.</td></tr>';
            }
        }

        // 3. Popular Menu Items
        if (popTbody) {
            if (data.popular_items && data.popular_items.length > 0) {
                popTbody.innerHTML = data.popular_items.map((p, idx) => `
                    <tr>
                        <td><span style="font-weight: 700; color: ${idx === 0 ? 'var(--secondary)' : 'var(--text-light)'};">#${idx + 1}</span></td>
                        <td><strong>${p.name}</strong></td>
                        <td><span class="badge badge-ok">${p.category_name}</span></td>
                        <td>₹${p.price.toFixed(2)}</td>
                        <td><strong style="color: var(--secondary);">${p.total_sold} units</strong></td>
                        <td><strong style="color: var(--primary);">₹${p.total_revenue.toFixed(2)}</strong></td>
                    </tr>
                `).join('');
            } else {
                popTbody.innerHTML = '<tr><td colspan="6" style="text-align: center; padding: 2rem; color: var(--text-muted);">No sales data available to rank items.</td></tr>';
            }
        }
    } catch (e) {
        console.error('Error refreshing dashboard:', e);
        if (tbody) tbody.innerHTML = '<tr><td colspan="8" style="text-align: center; color: var(--non-veg); padding: 2rem;">Connection failure loading dashboard.</td></tr>';
    } finally {
        if (btn) btn.disabled = false;
    }
}

function applyDashboardDateFilter() {
    const startInput = document.getElementById('dashStartDate');
    const endInput = document.getElementById('dashEndDate');
    const start = startInput ? startInput.value : '';
    const end = endInput ? endInput.value : '';

    if (start && end && start > end) {
        showToast('Start date cannot be after end date.', 'error');
        return;
    }

    dashFilterStartDate = start;
    dashFilterEndDate = end;

    const banner = document.getElementById('dashFilterActiveBanner');
    const rangeText = document.getElementById('dashFilterRangeText');
    if (dashFilterStartDate || dashFilterEndDate) {
        if (banner) banner.style.display = 'block';
        if (rangeText) rangeText.textContent = `${dashFilterStartDate || 'Beginning'} to ${dashFilterEndDate || 'Today'}`;
    } else {
        if (banner) banner.style.display = 'none';
    }

    refreshDashboard();
}

function clearDashboardDateFilter() {
    const startInput = document.getElementById('dashStartDate');
    const endInput = document.getElementById('dashEndDate');
    if (startInput) startInput.value = '';
    if (endInput) endInput.value = '';
    dashFilterStartDate = '';
    dashFilterEndDate = '';
    const banner = document.getElementById('dashFilterActiveBanner');
    if (banner) banner.style.display = 'none';
    refreshDashboard();
}

function setDashboardDateShortcut(period) {
    const today = new Date();
    const pad = (n) => String(n).padStart(2, '0');
    const format = (d) => `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;

    const endStr = format(today);
    let startStr = endStr;

    if (period === 'today') {
        startStr = endStr;
    } else if (period === '7days') {
        const past = new Date(today);
        past.setDate(today.getDate() - 7);
        startStr = format(past);
    } else if (period === '30days') {
        const past = new Date(today);
        past.setDate(today.getDate() - 30);
        startStr = format(past);
    }

    const startInput = document.getElementById('dashStartDate');
    const endInput = document.getElementById('dashEndDate');
    if (startInput) startInput.value = startStr;
    if (endInput) endInput.value = endStr;
    applyDashboardDateFilter();
}

function openLowStockModal() {
    const tbody = document.getElementById('lowStockModalTbody');
    if (!tbody) return;
    if (!cachedLowStockItems || cachedLowStockItems.length === 0) {
        tbody.innerHTML = '<tr><td colspan="5" style="text-align: center; padding: 2rem; color: var(--tertiary); font-weight: 600;">✅ Excellent! All ingredients and supplies are above reorder thresholds.</td></tr>';
    } else {
        tbody.innerHTML = cachedLowStockItems.map(item => `
            <tr>
                <td><strong>${item.item_name}</strong></td>
                <td><strong style="color: var(--non-veg);">${item.quantity} ${item.unit}</strong></td>
                <td>${item.reorder_level} ${item.unit}</td>
                <td>${item.supplier_name || 'Local Producer'}</td>
                <td><span class="badge badge-low-stock">Low Stock</span></td>
            </tr>
        `).join('');
    }
    openModal('adminLowStockModal');
}

const VALID_TRANSITIONS = {
    'Pending': ['Confirmed', 'Cancelled'],
    'Confirmed': ['Preparing', 'Cancelled'],
    'Preparing': ['Ready', 'Cancelled'],
    'Ready': ['Completed', 'Cancelled'],
    'Completed': [],
    'Cancelled': []
};

let currentModalOrder = null;

function getNextStatusButton(orderId, currentStatus) {
    const transitions = {
        'Pending': 'Confirmed',
        'Confirmed': 'Preparing',
        'Preparing': 'Ready',
        'Ready': 'Completed'
    };

    const next = transitions[currentStatus];
    if (!next) {
        return `<span style="color: var(--text-muted); font-size: 0.78rem;">${currentStatus}</span>`;
    }

    return `
        <button onclick="advanceOrderStatus(${orderId}, '${next}')" class="btn btn-amber btn-sm" style="padding: 0.25rem 0.55rem; font-size: 0.75rem;">
            Advance to ${next} ➔
        </button>
    `;
}

async function advanceOrderStatus(orderId, nextStatus, notes = '') {
    try {
        const res = await fetch('/api/orders/update-status', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ order_id: orderId, status: nextStatus, notes: notes || null })
        });
        const result = await res.json();
        if (result.success) {
            showToast(result.message, 'success');
            if (currentAdminTab === 'dashboard') refreshDashboard();
            if (currentAdminTab === 'orders') loadAdminOrdersQueue();
        } else {
            showToast(result.message || 'Status transition rejected.', 'error');
        }
    } catch (e) {
        showToast('Error updating status.', 'error');
    }
}

// 2. Orders Queue with Multi-Filter & Search
function applyAdminOrderFilters() {
    loadAdminOrdersQueue();
}

function resetAdminOrderFilters() {
    const searchEl = document.getElementById('adminOrderSearch');
    const statusEl = document.getElementById('adminFilterStatus');
    const payMethodEl = document.getElementById('adminFilterPayMethod');
    const payStatusEl = document.getElementById('adminFilterPayStatus');
    const dateEl = document.getElementById('adminFilterDate');

    if (searchEl) searchEl.value = '';
    if (statusEl) statusEl.value = '';
    if (payMethodEl) payMethodEl.value = '';
    if (payStatusEl) payStatusEl.value = '';
    if (dateEl) dateEl.value = '';

    loadAdminOrdersQueue();
}

async function loadAdminOrdersQueue() {
    try {
        let url = '/api/orders?limit=100';

        const search = document.getElementById('adminOrderSearch') ? document.getElementById('adminOrderSearch').value.trim() : '';
        const status = document.getElementById('adminFilterStatus') ? document.getElementById('adminFilterStatus').value : '';
        const payMethod = document.getElementById('adminFilterPayMethod') ? document.getElementById('adminFilterPayMethod').value : '';
        const payStatus = document.getElementById('adminFilterPayStatus') ? document.getElementById('adminFilterPayStatus').value : '';
        const date = document.getElementById('adminFilterDate') ? document.getElementById('adminFilterDate').value : '';

        if (search) url += `&search=${encodeURIComponent(search)}`;
        if (status) url += `&status=${encodeURIComponent(status)}`;
        if (payMethod) url += `&payment_method=${encodeURIComponent(payMethod)}`;
        if (payStatus) url += `&payment_status=${encodeURIComponent(payStatus)}`;
        if (date) url += `&date=${encodeURIComponent(date)}`;

        const res = await fetch(url);
        const result = await res.json();
        const tbody = document.getElementById('ordersManagementTbody');

        if (result.success && result.data.length > 0) {
            tbody.innerHTML = result.data.map(o => {
                const isCashPending = o.payment_method === 'Cash' && o.payment_status === 'Pending';
                const isPaid = o.payment_status === 'Completed';

                return `
                    <tr>
                        <td>
                            <strong>#${o.order_reference}</strong>
                            <div style="font-size: 0.72rem; color: var(--text-light);">${o.cafe_name || 'CaféNest'}</div>
                        </td>
                        <td><small>${o.created_at}</small></td>
                        <td>
                            <strong>${o.customer_name || 'Walk-in Guest'}</strong>
                            ${o.customer_phone ? `<br><small style="color: var(--text-light);">${o.customer_phone}</small>` : ''}
                        </td>
                        <td>${o.order_type}<br><small style="color: var(--secondary); font-weight: 600;">${o.table_number ? 'Table ' + o.table_number : 'Takeaway'}</small></td>
                        <td><strong style="font-family: 'Playfair Display', serif;">₹${o.total_amount.toFixed(2)}</strong></td>
                        <td>
                            <div style="font-size: 0.8rem; font-weight: 600;">${o.payment_method || 'Unpaid'}</div>
                            <span class="badge ${isPaid ? 'badge-completed' : 'badge-pending'}" style="font-size: 0.72rem;">
                                ${o.payment_status || 'Pending'}
                            </span>
                            ${isCashPending ? `
                                <div style="margin-top: 0.3rem;">
                                    <button onclick="confirmCashForOrder(${o.order_id})" class="btn btn-amber btn-sm" style="padding: 0.2rem 0.45rem; font-size: 0.7rem;">
                                        💵 Settle Cash
                                    </button>
                                </div>
                            ` : ''}
                        </td>
                        <td><span class="badge badge-${o.status.toLowerCase()}">${o.status}</span></td>
                        <td>
                            <div style="display: flex; gap: 0.3rem; flex-wrap: wrap;">
                                ${getNextStatusButton(o.order_id, o.status)}
                                ${o.status !== 'Cancelled' && o.status !== 'Completed' ? `
                                    <button onclick="advanceOrderStatus(${o.order_id}, 'Cancelled', 'Cancelled from admin queue')" class="btn btn-secondary btn-sm" style="padding: 0.25rem 0.5rem; font-size: 0.72rem; color: var(--non-veg);">
                                        Cancel
                                    </button>
                                ` : ''}
                            </div>
                        </td>
                        <td>
                            <button onclick="openOrderDetailModal(${o.order_id})" class="btn btn-secondary btn-sm" style="padding: 0.25rem 0.55rem; font-size: 0.75rem;">
                                👁️ View
                            </button>
                        </td>
                    </tr>
                `;
            }).join('');
        } else {
            tbody.innerHTML = '<tr><td colspan="9" style="text-align: center; padding: 2.5rem; color: var(--text-muted);">No orders matching current search or filters.</td></tr>';
        }
    } catch (e) {
        console.error(e);
    }
}

async function confirmCashForOrder(orderId) {
    if (!confirm(`Confirm receipt of cash for Order ID #${orderId}?`)) return;

    try {
        const res = await fetch('/api/payments/confirm-cash', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ order_id: orderId })
        });
        const result = await res.json();
        if (result.success) {
            showToast(result.message, 'success');
            loadAdminOrdersQueue();
            if (currentModalOrder && currentModalOrder.order_id === orderId) {
                openOrderDetailModal(orderId);
            }
        } else {
            showToast(result.message || 'Failed to confirm cash.', 'error');
        }
    } catch (e) {
        showToast('Error confirming cash payment.', 'error');
    }
}

async function openOrderDetailModal(orderId) {
    try {
        const res = await fetch(`/api/orders/${orderId}`);
        const result = await res.json();
        if (!result.success) {
            showToast(result.message || 'Failed to fetch order details.', 'error');
            return;
        }

        const o = result.data;
        currentModalOrder = o;

        document.getElementById('modalOrderRefTitle').textContent = `Order #${o.order_reference} (${o.cafe_name || 'CaféNest'})`;
        document.getElementById('modalOrderDateSubtitle').textContent = `Placed on ${o.created_at} • ${o.order_type}`;

        document.getElementById('modalCustName').textContent = o.customer_name || 'Walk-in Patron';
        document.getElementById('modalCustContact').textContent = `${o.customer_phone || 'No phone'} | ${o.customer_email || 'No email'}`;
        document.getElementById('modalOrderType').textContent = o.order_type === 'Dine-In' ? `Dine-In • Table ${o.table_number || 'Assigned'}` : 'Takeaway';
        document.getElementById('modalSpecialInstructions').textContent = o.special_instructions ? `Note: "${o.special_instructions}"` : 'No special instructions';

        // Line items
        const itemsTbody = document.getElementById('modalOrderItemsTbody');
        if (o.items && o.items.length > 0) {
            itemsTbody.innerHTML = o.items.map(it => `
                <tr>
                    <td><strong>${it.item_name}</strong></td>
                    <td>${it.quantity}</td>
                    <td>₹${it.unit_price.toFixed(2)}</td>
                    <td><strong>₹${it.subtotal.toFixed(2)}</strong></td>
                </tr>
            `).join('');
        } else {
            itemsTbody.innerHTML = '<tr><td colspan="4" style="text-align: center; color: var(--text-muted);">No line items</td></tr>';
        }

        // Totals
        document.getElementById('modalSubtotal').textContent = `₹${o.subtotal.toFixed(2)}`;
        document.getElementById('modalTax').textContent = `₹${o.tax_amount.toFixed(2)}`;
        document.getElementById('modalTotal').textContent = `₹${o.total_amount.toFixed(2)}`;

        // Payment
        const payMethodStatus = document.getElementById('modalPayMethodStatus');
        const payRef = document.getElementById('modalPayRef');
        const confirmCashContainer = document.getElementById('modalConfirmCashContainer');

        if (o.payment) {
            const isPaid = o.payment.status === 'Completed';
            payMethodStatus.innerHTML = `
                ${o.payment.method} • 
                <span class="badge ${isPaid ? 'badge-completed' : 'badge-pending'}">
                    ${o.payment.status}
                </span>
            `;
            payRef.textContent = `Ref: ${o.payment.transaction_ref} ${o.payment.paid_at ? '• ' + o.payment.paid_at : ''}`;

            if (o.payment.method === 'Cash' && o.payment.status === 'Pending') {
                confirmCashContainer.style.display = 'block';
            } else {
                confirmCashContainer.style.display = 'none';
            }
        } else {
            payMethodStatus.innerHTML = '<span class="badge badge-pending">Unpaid</span>';
            payRef.textContent = 'No payment record';
            confirmCashContainer.style.display = 'none';
        }

        // Status transition selector
        const currentBadge = document.getElementById('modalCurrentStatusBadge');
        currentBadge.textContent = o.status;
        currentBadge.className = `badge badge-${o.status.toLowerCase()}`;

        const nextSelect = document.getElementById('modalNextStatusSelect');
        const allowed = VALID_TRANSITIONS[o.status] || [];
        if (allowed.length > 0) {
            nextSelect.innerHTML = allowed.map(st => `<option value="${st}">Advance to ${st}</option>`).join('');
            nextSelect.disabled = false;
            document.getElementById('btnUpdateStatusModal').disabled = false;
        } else {
            nextSelect.innerHTML = '<option value="">Terminal state (No transitions)</option>';
            nextSelect.disabled = true;
            document.getElementById('btnUpdateStatusModal').disabled = true;
        }
        document.getElementById('modalStatusNotes').value = '';

        // Status history audit trail
        const histTbody = document.getElementById('modalStatusHistoryTbody');
        const history = o.status_history || [];
        if (history.length > 0) {
            histTbody.innerHTML = history.map(h => `
                <tr>
                    <td><strong>${h.previous_status || 'Initiated'} ➔ ${h.new_status}</strong></td>
                    <td>${h.changed_by_name || 'System / Customer'} (${h.changed_by_role || 'Auto'})</td>
                    <td><small>${h.created_at}</small></td>
                    <td><small>${h.notes || '—'}</small></td>
                </tr>
            `).join('');
        } else {
            histTbody.innerHTML = '<tr><td colspan="4" style="text-align: center; color: var(--text-muted);">No prior status transitions recorded.</td></tr>';
        }

        openModal('adminOrderDetailModal');
    } catch (e) {
        console.error(e);
        showToast('Error opening order detail modal.', 'error');
    }
}

async function handleAdvanceStatusFromModal() {
    if (!currentModalOrder) return;
    const nextStatus = document.getElementById('modalNextStatusSelect').value;
    const notes = document.getElementById('modalStatusNotes').value.trim();

    if (!nextStatus) {
        showToast('Please select a valid next status.', 'error');
        return;
    }

    const btn = document.getElementById('btnUpdateStatusModal');
    btn.disabled = true;
    btn.textContent = 'Updating...';

    try {
        const res = await fetch('/api/orders/update-status', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                order_id: currentModalOrder.order_id,
                status: nextStatus,
                notes: notes || `Updated via admin order modal by ${adminUser ? adminUser.name : 'Staff'}`
            })
        });
        const result = await res.json();
        if (result.success) {
            showToast(result.message, 'success');
            openOrderDetailModal(currentModalOrder.order_id);
            loadAdminOrdersQueue();
            if (currentAdminTab === 'dashboard') refreshDashboard();
        } else {
            showToast(result.message || 'Status transition rejected.', 'error');
        }
    } catch (e) {
        showToast('Error updating status.', 'error');
    } finally {
        btn.disabled = false;
        btn.textContent = 'Update Status ➔';
    }
}

async function handleConfirmCashModal() {
    if (!currentModalOrder) return;
    await confirmCashForOrder(currentModalOrder.order_id);
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

// 4. Café Table Management Logic
let cachedAdminTables = [];
let currentTableFilterStatus = 'All';

async function loadAdminTables() {
    const grid = document.getElementById('tablesGridContainer');
    if (grid) {
        grid.innerHTML = '<div style="grid-column: 1 / -1; text-align: center; padding: 3rem; color: var(--text-muted);">Fetching table records from MySQL...</div>';
    }

    try {
        const res = await fetch('/api/tables');
        const result = await res.json();
        if (result.success) {
            cachedAdminTables = result.data || [];
            updateTableSummaryStats(cachedAdminTables);
            renderAdminTablesGrid();
        } else {
            showToast(result.message || 'Failed to load tables.', 'error');
            if (grid) grid.innerHTML = `<div style="grid-column: 1 / -1; text-align: center; color: var(--non-veg); padding: 3rem;">Error: ${result.message}</div>`;
        }
    } catch (e) {
        console.error('Error fetching tables:', e);
        if (grid) grid.innerHTML = '<div style="grid-column: 1 / -1; text-align: center; color: var(--non-veg); padding: 3rem;">Connection error loading tables.</div>';
    }
}

function updateTableSummaryStats(tables) {
    const total = tables.length;
    let available = 0;
    let occupied = 0;
    let reserved = 0;
    let totalCap = 0;

    tables.forEach(t => {
        if (t.status === 'Available') available++;
        else if (t.status === 'Occupied') occupied++;
        else if (t.status === 'Reserved') reserved++;
        totalCap += (parseInt(t.seating_capacity) || 0);
    });

    if (document.getElementById('tblSummaryTotal')) document.getElementById('tblSummaryTotal').textContent = total;
    if (document.getElementById('tblSummaryAvailable')) document.getElementById('tblSummaryAvailable').textContent = available;
    if (document.getElementById('tblSummaryOccupied')) document.getElementById('tblSummaryOccupied').textContent = occupied;
    if (document.getElementById('tblSummaryReserved')) document.getElementById('tblSummaryReserved').textContent = reserved;
    if (document.getElementById('tblSummaryCapacity')) document.getElementById('tblSummaryCapacity').textContent = `${totalCap} seats`;
}

function filterAdminTablesByStatus(status) {
    currentTableFilterStatus = status;
    const pills = ['All', 'Available', 'Occupied', 'Reserved'];
    pills.forEach(p => {
        const btn = document.getElementById(`pillTbl${p}`);
        if (btn) {
            if (p === status) {
                btn.classList.add('btn-primary');
                btn.classList.remove('btn-secondary');
            } else {
                btn.classList.remove('btn-primary');
                btn.classList.add('btn-secondary');
            }
        }
    });
    renderAdminTablesGrid();
}

function renderAdminTablesGrid() {
    const grid = document.getElementById('tablesGridContainer');
    if (!grid) return;

    const search = (document.getElementById('adminTableSearchInput')?.value || '').trim().toLowerCase();

    const filtered = cachedAdminTables.filter(t => {
        if (currentTableFilterStatus !== 'All' && t.status !== currentTableFilterStatus) {
            return false;
        }
        if (search) {
            const num = (t.table_number || '').toLowerCase();
            const area = (t.location_area || '').toLowerCase();
            const cafe = (t.cafe_name || '').toLowerCase();
            if (!num.includes(search) && !area.includes(search) && !cafe.includes(search)) {
                return false;
            }
        }
        return true;
    });

    if (filtered.length === 0) {
        grid.innerHTML = `
            <div style="grid-column: 1 / -1; text-align: center; padding: 3rem; background: var(--surface); border-radius: var(--radius-lg); border: 1px dashed var(--border);">
                <div style="font-size: 2.2rem; margin-bottom: 0.5rem;">🪑</div>
                <h4 style="color: var(--primary); margin-bottom: 0.4rem;">No Café Tables Found</h4>
                <p style="color: var(--text-muted); font-size: 0.88rem; margin-bottom: 1rem;">No tables match the current filter or search criteria.</p>
                <button onclick="openAddTableModal()" class="btn btn-primary btn-sm">+ Add New Table</button>
            </div>
        `;
        return;
    }

    grid.innerHTML = filtered.map(t => {
        const statusClass = (t.status || 'Available').toLowerCase();
        const activeOrderHtml = t.active_order ? `
            <div style="background: rgba(217, 119, 54, 0.08); border: 1px solid rgba(217, 119, 54, 0.25); padding: 0.45rem 0.65rem; border-radius: var(--radius-sm); margin-top: 0.7rem; font-size: 0.78rem;">
                <span style="font-weight: 700; color: var(--secondary);">Active Order:</span>
                <span style="font-weight: 600;">#${t.active_order.order_reference}</span>
                <span class="badge badge-${t.active_order.status.toLowerCase()}" style="font-size: 0.65rem; padding: 0.15rem 0.4rem; margin-left: 0.3rem;">${t.active_order.status}</span>
                <div style="color: var(--text-muted); font-size: 0.72rem; margin-top: 0.2rem;">
                    Patron: ${t.active_order.customer_name || 'Guest'} (${t.active_order.party_size || 1} guests)
                </div>
            </div>
        ` : `
            <div style="color: var(--text-light); font-size: 0.75rem; margin-top: 0.7rem;">
                No active order attached
            </div>
        `;

        return `
            <div class="cafe-table-card status-${statusClass}" id="tableCard-${t.table_id}">
                <div>
                    <!-- Card Top: Table # and Status -->
                    <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 0.5rem;">
                        <div>
                            <h3 style="font-size: 1.25rem; font-weight: 700; color: var(--primary); margin: 0;">
                                ${t.table_number}
                            </h3>
                            <span style="font-size: 0.75rem; color: var(--text-muted);">
                                📍 ${t.location_area || 'Main Dining'}
                            </span>
                        </div>
                        <span class="badge badge-${statusClass}">
                            ${t.status}
                        </span>
                    </div>

                    <!-- Café Association & Capacity -->
                    <div style="font-size: 0.8rem; color: var(--text-light); margin-bottom: 0.4rem;">
                        🏢 ${t.cafe_name || 'CaféNest Flagship Roastery'}
                    </div>

                    <div style="display: flex; gap: 0.4rem; align-items: center; margin-bottom: 0.6rem;">
                        <span style="background: var(--surface-alt); padding: 0.25rem 0.55rem; border-radius: var(--radius-sm); font-size: 0.75rem; font-weight: 600; color: var(--primary);">
                            👥 ${t.seating_capacity} Seats
                        </span>
                        <span style="font-size: 0.72rem; color: var(--text-muted);">ID: #${t.table_id}</span>
                    </div>

                    <!-- Active Order details if Occupied -->
                    ${activeOrderHtml}
                </div>

                <!-- Card Actions -->
                <div style="margin-top: 1.2rem; border-top: 1px solid var(--border-light); padding-top: 0.8rem;">
                    <div style="display: flex; justify-content: space-between; align-items: center; gap: 0.4rem;">
                        <div style="flex: 1;">
                            <select class="form-select" style="font-size: 0.75rem; padding: 0.3rem 0.5rem;" onchange="handleQuickTableStatusChange(${t.table_id}, this.value)" title="Change table status">
                                <option value="Available" ${t.status === 'Available' ? 'selected' : ''}>Available</option>
                                <option value="Occupied" ${t.status === 'Occupied' ? 'selected' : ''}>Occupied</option>
                                <option value="Reserved" ${t.status === 'Reserved' ? 'selected' : ''}>Reserved</option>
                            </select>
                        </div>
                        <button onclick="openEditTableModal(${t.table_id})" class="btn btn-secondary btn-sm" style="font-size: 0.75rem; padding: 0.3rem 0.6rem;" title="Edit Table Details">
                            ✏️ Edit
                        </button>
                        <button onclick="handleDeleteTable(${t.table_id}, '${t.table_number}')" class="btn btn-danger btn-sm" style="font-size: 0.75rem; padding: 0.3rem 0.6rem;" title="Safely Delete Table">
                            🗑️
                        </button>
                    </div>
                </div>
            </div>
        `;
    }).join('');
}

function openAddTableModal() {
    document.getElementById('tableModalTitle').textContent = 'Add New Café Table';
    document.getElementById('adminTableId').value = '';
    document.getElementById('adminTableNumber').value = '';
    document.getElementById('adminTableCafeName').value = 'CaféNest Flagship Roastery';
    document.getElementById('adminTableCapacity').value = '4';
    document.getElementById('adminTableArea').value = 'Main Dining';
    document.getElementById('adminTableStatus').value = 'Available';
    const err = document.getElementById('tableModalError');
    if (err) err.style.display = 'none';
    openModal('adminTableModal');
}

function openEditTableModal(tableId) {
    const table = cachedAdminTables.find(t => t.table_id === tableId);
    if (!table) {
        showToast('Table not found in cache.', 'error');
        return;
    }
    document.getElementById('tableModalTitle').textContent = `Edit Café Table: ${table.table_number}`;
    document.getElementById('adminTableId').value = table.table_id;
    document.getElementById('adminTableNumber').value = table.table_number;
    document.getElementById('adminTableCafeName').value = table.cafe_name || 'CaféNest Flagship Roastery';
    document.getElementById('adminTableCapacity').value = table.seating_capacity;
    document.getElementById('adminTableArea').value = table.location_area || 'Main Dining';
    document.getElementById('adminTableStatus').value = table.status;
    const err = document.getElementById('tableModalError');
    if (err) err.style.display = 'none';
    openModal('adminTableModal');
}

async function handleSaveTable(e) {
    e.preventDefault();
    const tableId = document.getElementById('adminTableId').value;
    const tableNumber = document.getElementById('adminTableNumber').value.trim();
    const cafeName = document.getElementById('adminTableCafeName').value.trim();
    const capacity = parseInt(document.getElementById('adminTableCapacity').value);
    const area = document.getElementById('adminTableArea').value;
    const status = document.getElementById('adminTableStatus').value;
    const errBox = document.getElementById('tableModalError');

    if (!tableNumber) {
        if (errBox) {
            errBox.textContent = 'Table number is required.';
            errBox.style.display = 'block';
        }
        return;
    }

    if (!capacity || capacity <= 0) {
        if (errBox) {
            errBox.textContent = 'Seating capacity must be a positive integer greater than zero.';
            errBox.style.display = 'block';
        }
        return;
    }

    const payload = {
        table_number: tableNumber,
        cafe_name: cafeName,
        seating_capacity: capacity,
        location_area: area,
        status: status
    };

    const isEdit = Boolean(tableId);
    const url = isEdit ? `/api/tables/${tableId}` : '/api/tables';
    const method = isEdit ? 'PUT' : 'POST';

    const saveBtn = document.getElementById('btnSaveTable');
    if (saveBtn) {
        saveBtn.disabled = true;
        saveBtn.textContent = 'Saving to MySQL...';
    }

    try {
        const res = await fetch(url, {
            method: method,
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        const result = await res.json();

        if (result.success) {
            showToast(result.message || 'Table saved successfully.', 'success');
            closeModal('adminTableModal');
            loadAdminTables();
            if (currentAdminTab === 'dashboard') refreshDashboard();
        } else {
            if (errBox) {
                errBox.textContent = result.message || 'Failed to save table.';
                errBox.style.display = 'block';
            }
            showToast(result.message || 'Validation error saving table.', 'error');
        }
    } catch (err) {
        if (errBox) {
            errBox.textContent = 'Connection error saving table.';
            errBox.style.display = 'block';
        }
        showToast('Request error saving table.', 'error');
    } finally {
        if (saveBtn) {
            saveBtn.disabled = false;
            saveBtn.textContent = 'Save Table';
        }
    }
}

async function handleQuickTableStatusChange(tableId, newStatus) {
    try {
        const res = await fetch(`/api/tables/${tableId}/status`, {
            method: 'PATCH',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ status: newStatus })
        });
        const result = await res.json();
        if (result.success) {
            showToast(result.message, 'success');
            loadAdminTables();
            if (currentAdminTab === 'dashboard') refreshDashboard();
        } else {
            showToast(result.message || 'Failed to update table status.', 'error');
            loadAdminTables();
        }
    } catch (e) {
        showToast('Error updating table status.', 'error');
        loadAdminTables();
    }
}

async function handleDeleteTable(tableId, tableNumber) {
    if (!confirm(`Are you sure you want to delete table "${tableNumber}"? Active or historical order references will safely prevent deletion.`)) {
        return;
    }

    try {
        const res = await fetch(`/api/tables/${tableId}`, {
            method: 'DELETE'
        });
        const result = await res.json();
        if (result.success) {
            showToast(result.message, 'success');
            loadAdminTables();
            if (currentAdminTab === 'dashboard') refreshDashboard();
        } else {
            alert(`⚠️ Cannot Delete Table:\n\n${result.message}`);
            showToast(result.message || 'Cannot delete table.', 'error');
        }
    } catch (e) {
        showToast('Connection error attempting to delete table.', 'error');
    }
}

document.addEventListener('DOMContentLoaded', initAdminPortal);
