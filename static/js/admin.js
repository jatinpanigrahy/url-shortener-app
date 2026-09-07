let adminActiveSubTab = 'users';

let adminUsersCache = [];
let adminUsersOffset = 0;
let adminUsersLimit = 15;
let adminUsersHasMore = false;

let adminUrlsCache = [];
let adminUrlsOffset = 0;
let adminUrlsLimit = 15;
let adminUrlsHasMore = false;

let currentInspectUserId = null;
let currentInspectUserCache = null;

function initAdminDashboard() {
    if (!getIsAdmin()) {
        navigateTo('/', true);
        return;
    }
    if (adminActiveSubTab === 'users') {
        refreshAdminUsers();
    } else {
        refreshAdminUrls();
    }
}

function switchAdminSubTab(tab) {
    adminActiveSubTab = tab;
    const btnUsers = document.getElementById('adminTabBtnUsers');
    const btnUrls = document.getElementById('adminTabBtnUrls');
    const secUsers = document.getElementById('adminUsersSection');
    const secUrls = document.getElementById('adminUrlsSection');

    if (tab === 'users') {
        if (btnUsers) btnUsers.className = 'text-xs sm:text-sm font-semibold px-4 py-2 rounded-xl bg-white dark:bg-white/[0.08] shadow-sm text-brand-600 dark:text-brand-400 cursor-pointer transition';
        if (btnUrls) btnUrls.className = 'text-xs sm:text-sm font-semibold px-4 py-2 rounded-xl text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white cursor-pointer transition';
        if (secUsers) secUsers.classList.remove('hidden');
        if (secUrls) secUrls.classList.add('hidden');
        if (adminUsersCache.length === 0) refreshAdminUsers();
    } else {
        if (btnUrls) btnUrls.className = 'text-xs sm:text-sm font-semibold px-4 py-2 rounded-xl bg-white dark:bg-white/[0.08] shadow-sm text-brand-600 dark:text-brand-400 cursor-pointer transition';
        if (btnUsers) btnUsers.className = 'text-xs sm:text-sm font-semibold px-4 py-2 rounded-xl text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white cursor-pointer transition';
        if (secUrls) secUrls.classList.remove('hidden');
        if (secUsers) secUsers.classList.add('hidden');
        if (adminUrlsCache.length === 0) refreshAdminUrls();
    }
}

async function fetchAdminUsers(offset = 0, query = '') {
    const apiKey = getApiKey();
    if (!apiKey) return null;

    try {
        const params = new URLSearchParams({
            limit: adminUsersLimit,
            offset: offset,
            search: query
        });
        const res = await fetch(`/admin/users?${params.toString()}`, {
            headers: { 'X-API-Key': apiKey }
        });
        if (!res.ok) {
            if (res.status === 403 || res.status === 401) {
                alert('Administrative access denied.');
                navigateTo('/', true);
            }
            return null;
        }
        return await res.json();
    } catch (err) {
        console.error('Failed to load admin users:', err);
        return null;
    }
}

async function refreshAdminUsers() {
    adminUsersOffset = 0;
    adminUsersCache = [];
    const q = document.getElementById('adminUserSearchInput')?.value.trim() || '';
    const data = await fetchAdminUsers(0, q);
    if (!data) return;

    adminUsersCache = data.users || [];
    adminUsersHasMore = Boolean(data.has_more);
    adminUsersOffset = adminUsersCache.length;
    renderAdminUsersTable(adminUsersCache);
}

async function loadMoreAdminUsers() {
    const q = document.getElementById('adminUserSearchInput')?.value.trim() || '';
    const data = await fetchAdminUsers(adminUsersOffset, q);
    if (!data) return;

    const newUsers = data.users || [];
    adminUsersCache = adminUsersCache.concat(newUsers);
    adminUsersHasMore = Boolean(data.has_more);
    adminUsersOffset = adminUsersCache.length;
    renderAdminUsersTable(adminUsersCache);
}

function renderAdminUsersTable(users) {
    const tbody = document.getElementById('adminUsersTableBody');
    const emptyMsg = document.getElementById('adminUsersEmptyMessage');
    const loadMoreBtn = document.getElementById('adminUsersLoadMoreBtn');
    if (!tbody) return;
    tbody.innerHTML = '';

    if (users.length === 0) {
        if (emptyMsg) emptyMsg.classList.remove('hidden');
        if (loadMoreBtn) loadMoreBtn.classList.add('hidden');
        return;
    }
    if (emptyMsg) emptyMsg.classList.add('hidden');

    if (loadMoreBtn) {
        if (adminUsersHasMore) {
            loadMoreBtn.classList.remove('hidden');
        } else {
            loadMoreBtn.classList.add('hidden');
        }
    }

    users.forEach(u => {
        const row = document.createElement('tr');
        row.className = 'hover:bg-slate-100/60 dark:hover:bg-white/[0.02] transition cursor-pointer';
        
        const isBanned = Boolean(u.is_banned);
        const isAdmin = Boolean(u.is_admin);
        const statusBadge = isBanned 
            ? '<span class="text-[10px] font-bold px-2 py-0.5 rounded bg-rose-500/10 text-rose-600 dark:text-rose-400">Banned</span>'
            : '<span class="text-[10px] font-bold px-2 py-0.5 rounded bg-emerald-500/10 text-emerald-600 dark:text-emerald-400">Active</span>';
        
        const roleBadge = isAdmin
            ? '<span class="text-[10px] font-bold px-2 py-0.5 rounded bg-brand-500/10 text-brand-600 dark:text-brand-400">Admin</span>'
            : '<span class="text-[10px] font-medium px-2 py-0.5 rounded bg-slate-100 dark:bg-white/[0.06] text-slate-500">User</span>';

        const joinedDate = u.created_at ? new Date(u.created_at).toLocaleDateString() : '—';

        row.innerHTML = `
            <td class="py-3.5 px-4 font-semibold text-slate-900 dark:text-white">
                <div class="truncate max-w-[200px]" title="${u.email}">${u.email}</div>
            </td>
            <td class="py-3.5 px-4">${roleBadge}</td>
            <td class="py-3.5 px-4">${statusBadge}</td>
            <td class="py-3.5 px-4 text-center font-bold text-slate-600 dark:text-slate-300">${u.total_links || 0}</td>
            <td class="py-3.5 px-4 text-center font-bold text-slate-600 dark:text-slate-300">${(u.total_clicks || 0).toLocaleString()}</td>
            <td class="py-3.5 px-4 text-slate-400 whitespace-nowrap">${joinedDate}</td>
            <td class="py-3.5 px-4 text-right">
                <button onclick="event.stopPropagation(); openAdminInspector(${u.id})" class="text-xs font-bold text-brand-600 dark:text-brand-400 hover:underline cursor-pointer">
                    Inspect &rarr;
                </button>
            </td>
        `;
        row.addEventListener('click', () => openAdminInspector(u.id));
        tbody.appendChild(row);
    });
}

const adminUserSearchInput = document.getElementById('adminUserSearchInput');
if (adminUserSearchInput) {
    let timeout = null;
    adminUserSearchInput.addEventListener('input', () => {
        clearTimeout(timeout);
        timeout = setTimeout(() => {
            refreshAdminUsers();
        }, 300);
    });
}

async function fetchAdminUrls(offset = 0, query = '') {
    const apiKey = getApiKey();
    if (!apiKey) return null;

    try {
        const params = new URLSearchParams({
            limit: adminUrlsLimit,
            offset: offset,
            search: query
        });
        const res = await fetch(`/admin/urls?${params.toString()}`, {
            headers: { 'X-API-Key': apiKey }
        });
        if (!res.ok) return null;
        return await res.json();
    } catch (err) {
        console.error('Failed to load global links:', err);
        return null;
    }
}

async function refreshAdminUrls() {
    adminUrlsOffset = 0;
    adminUrlsCache = [];
    const q = document.getElementById('adminUrlSearchInput')?.value.trim() || '';
    const data = await fetchAdminUrls(0, q);
    if (!data) return;

    adminUrlsCache = data.urls || [];
    adminUrlsHasMore = Boolean(data.has_more);
    adminUrlsOffset = adminUrlsCache.length;
    renderAdminUrlsTable(adminUrlsCache);
}

async function loadMoreAdminUrls() {
    const q = document.getElementById('adminUrlSearchInput')?.value.trim() || '';
    const data = await fetchAdminUrls(adminUrlsOffset, q);
    if (!data) return;

    const newUrls = data.urls || [];
    adminUrlsCache = adminUrlsCache.concat(newUrls);
    adminUrlsHasMore = Boolean(data.has_more);
    adminUrlsOffset = adminUrlsCache.length;
    renderAdminUrlsTable(adminUrlsCache);
}

function renderAdminUrlsTable(urls) {
    const tbody = document.getElementById('adminUrlsTableBody');
    const emptyMsg = document.getElementById('adminUrlsEmptyMessage');
    const loadMoreBtn = document.getElementById('adminUrlsLoadMoreBtn');
    if (!tbody) return;
    tbody.innerHTML = '';

    if (urls.length === 0) {
        if (emptyMsg) emptyMsg.classList.remove('hidden');
        if (loadMoreBtn) loadMoreBtn.classList.add('hidden');
        return;
    }
    if (emptyMsg) emptyMsg.classList.add('hidden');

    if (loadMoreBtn) {
        if (adminUrlsHasMore) {
            loadMoreBtn.classList.remove('hidden');
        } else {
            loadMoreBtn.classList.add('hidden');
        }
    }

    urls.forEach(u => {
        const row = document.createElement('tr');
        row.className = 'hover:bg-slate-100/60 dark:hover:bg-white/[0.02] transition';
        const formattedExpiry = u.expires_at ? new Date(u.expires_at).toLocaleDateString() : 'Permanent';
        const ownerEmail = u.user_email || u.owner_email || 'Guest';

        row.innerHTML = `
            <td class="py-3.5 px-4 font-mono text-brand-600 dark:text-brand-400 font-semibold">
                <a href="/${u.short_code}" target="_blank" class="hover:underline">/${u.short_code}</a>
            </td>
            <td class="py-3.5 px-4 text-slate-600 dark:text-slate-300 max-w-[200px] truncate" title="${u.original_url}">
                ${u.original_url}
            </td>
            <td class="py-3.5 px-4 text-slate-500 max-w-[150px] truncate" title="${ownerEmail}">
                ${ownerEmail}
            </td>
            <td class="py-3.5 px-4 text-center font-bold text-slate-700 dark:text-slate-200">
                ${(u.click_count || 0).toLocaleString()}
            </td>
            <td class="py-3.5 px-4 text-slate-400 whitespace-nowrap">
                ${formattedExpiry}
            </td>
            <td class="py-3.5 px-4 text-right whitespace-nowrap">
                <button onclick="deleteAdminUrl('${u.short_code}')" class="text-rose-600 dark:text-rose-400 hover:underline font-semibold cursor-pointer">
                    Delete
                </button>
            </td>
        `;
        tbody.appendChild(row);
    });
}

const adminUrlSearchInput = document.getElementById('adminUrlSearchInput');
if (adminUrlSearchInput) {
    let timeout = null;
    adminUrlSearchInput.addEventListener('input', () => {
        clearTimeout(timeout);
        timeout = setTimeout(() => {
            refreshAdminUrls();
        }, 300);
    });
}

async function deleteAdminUrl(shortCode) {
    const apiKey = getApiKey();
    if (!apiKey) return;

    if (!confirm(`Purge short URL /${shortCode} globally?`)) return;

    try {
        const res = await fetch(`/${shortCode}`, {
            method: 'DELETE',
            headers: { 'X-API-Key': apiKey }
        });
        if (res.ok) {
            refreshAdminUrls();
            if (typeof loadPlatformAnalytics === 'function') {
                loadPlatformAnalytics();
            }
        } else {
            const data = await res.json();
            alert(data.error || 'Failed to purge URL.');
        }
    } catch (err) {
        alert('Network error while deleting short link.');
    }
}

async function openAdminInspector(userId) {
    currentInspectUserId = userId;
    const dirContainer = document.getElementById('adminDirectoryContainer');
    const inspContainer = document.getElementById('adminInspectorContainer');
    if (dirContainer) dirContainer.classList.add('hidden');
    if (inspContainer) inspContainer.classList.remove('hidden');

    const apiKey = getApiKey();
    if (!apiKey) return;

    try {
        const res = await fetch(`/admin/users/${userId}`, {
            headers: { 'X-API-Key': apiKey }
        });
        if (!res.ok) {
            alert('Unable to load user details.');
            closeAdminInspector();
            return;
        }

        const data = await res.json();

        let userUrls = data.urls;
        if (!userUrls) {
            try {
                const urlsRes = await fetch(`/admin/urls?user_id=${userId}&limit=100`, {
                    headers: { 'X-API-Key': apiKey }
                });
                if (urlsRes.ok) {
                    const urlsData = await urlsRes.json();
                    userUrls = urlsData.urls || [];
                } else {
                    userUrls = [];
                }
            } catch {
                userUrls = [];
            }
        }
        data.urls = userUrls;
        currentInspectUserCache = data;

        const heading = document.getElementById('inspectUserHeading');
        const subheading = document.getElementById('inspectUserSubheading');
        const emailEl = document.getElementById('inspectEmail');
        const totalLinksEl = document.getElementById('inspectTotalLinks');
        const totalClicksEl = document.getElementById('inspectTotalClicks');
        const banBtn = document.getElementById('inspectToggleBanBtn');

        if (heading) heading.textContent = data.email;
        if (subheading) subheading.textContent = `User ID #${data.id} • Registered ${data.created_at ? new Date(data.created_at).toLocaleDateString() : '—'}`;
        if (emailEl) emailEl.textContent = data.email;
        if (totalLinksEl) totalLinksEl.textContent = (data.urls || []).length;

        const totalClicks = (data.urls || []).reduce((acc, curr) => acc + (curr.click_count || 0), 0);
        if (totalClicksEl) totalClicksEl.textContent = totalClicks.toLocaleString();

        if (banBtn) {
            if (data.is_banned) {
                banBtn.textContent = 'Unban User';
                banBtn.className = 'text-xs sm:text-sm font-semibold px-4 py-2.5 rounded-2xl bg-emerald-500/10 hover:bg-emerald-500/20 text-emerald-600 dark:text-emerald-400 border border-emerald-500/20 transition cursor-pointer';
            } else {
                banBtn.textContent = 'Ban User';
                banBtn.className = 'text-xs sm:text-sm font-semibold px-4 py-2.5 rounded-2xl bg-amber-500/10 hover:bg-amber-500/20 text-amber-600 dark:text-amber-400 border border-amber-500/20 transition cursor-pointer';
            }
        }

        renderInspectUserLinks(data.urls || []);
        window.scrollTo({ top: 0, behavior: 'smooth' });
    } catch (err) {
        console.error('Inspector failure:', err);
    }
}

function closeAdminInspector() {
    currentInspectUserId = null;
    currentInspectUserCache = null;
    const dirContainer = document.getElementById('adminDirectoryContainer');
    const inspContainer = document.getElementById('adminInspectorContainer');
    if (inspContainer) inspContainer.classList.add('hidden');
    if (dirContainer) dirContainer.classList.remove('hidden');
}

function renderInspectUserLinks(urls) {
    const tbody = document.getElementById('inspectLinksTableBody');
    const emptyMsg = document.getElementById('inspectEmptyMessage');
    if (!tbody) return;
    tbody.innerHTML = '';

    if (urls.length === 0) {
        if (emptyMsg) emptyMsg.classList.remove('hidden');
        return;
    }
    if (emptyMsg) emptyMsg.classList.add('hidden');

    urls.forEach(link => {
        const row = document.createElement('tr');
        row.className = 'hover:bg-slate-100/60 dark:hover:bg-white/[0.02] transition';
        const formattedExpiry = link.expires_at ? new Date(link.expires_at).toLocaleDateString() : 'Permanent';

        row.innerHTML = `
            <td class="py-3.5 px-3 font-mono text-brand-600 dark:text-brand-400 font-semibold">
                <a href="/${link.short_code}" target="_blank" class="hover:underline">/${link.short_code}</a>
            </td>
            <td class="py-3.5 px-3 text-slate-600 dark:text-slate-300 max-w-[200px] truncate" title="${link.original_url}">
                ${link.original_url}
            </td>
            <td class="py-3.5 px-3 text-center text-slate-500 font-bold">
                ${link.click_count}
            </td>
            <td class="py-3.5 px-3 text-slate-400 whitespace-nowrap">
                ${formattedExpiry}
            </td>
            <td class="py-3.5 px-3 text-right">
                <button onclick="deleteInspectUserLink('${link.short_code}')" class="text-rose-600 dark:text-rose-400 hover:underline font-semibold cursor-pointer">
                    Delete
                </button>
            </td>
        `;
        tbody.appendChild(row);
    });
}

async function toggleInspectUserBan() {
    if (!currentInspectUserId) return;
    const apiKey = getApiKey();
    if (!apiKey) return;

    try {
        const res = await fetch(`/admin/users/${currentInspectUserId}/toggle-ban`, {
            method: 'POST',
            headers: { 'X-API-Key': apiKey }
        });
        const data = await res.json();
        if (res.ok) {
            openAdminInspector(currentInspectUserId);
            refreshAdminUsers();
        } else {
            alert(data.error || 'Failed to toggle ban status.');
        }
    } catch (err) {
        alert('Network error while moderating user.');
    }
}

async function deleteInspectUser() {
    if (!currentInspectUserId || !currentInspectUserCache) return;
    const email = currentInspectUserCache.email;
    const apiKey = getApiKey();
    if (!apiKey) return;

    if (!confirm(`Are you sure you want to permanently delete user "${email}"?\n\nAll links generated by this account will be purged.`)) {
        return;
    }

    try {
        const res = await fetch(`/admin/users/${currentInspectUserId}`, {
            method: 'DELETE',
            headers: { 'X-API-Key': apiKey }
        });
        const data = await res.json();
        if (res.ok) {
            closeAdminInspector();
            refreshAdminUsers();
            if (typeof loadPlatformAnalytics === 'function') {
                loadPlatformAnalytics();
            }
        } else {
            alert(data.error || 'Failed to delete user account.');
        }
    } catch (err) {
        alert('Network error while deleting user account.');
    }
}

async function deleteInspectUserLink(shortCode) {
    const apiKey = getApiKey();
    if (!apiKey) return;

    if (!confirm(`Delete short link /${shortCode}?`)) return;

    try {
        const res = await fetch(`/${shortCode}`, {
            method: 'DELETE',
            headers: { 'X-API-Key': apiKey }
        });
        if (res.ok) {
            if (currentInspectUserId) {
                openAdminInspector(currentInspectUserId);
            }
            if (typeof loadPlatformAnalytics === 'function') {
                loadPlatformAnalytics();
            }
        } else {
            const data = await res.json();
            alert(data.error || 'Failed to delete short link.');
        }
    } catch (err) {
        alert('Network error while deleting short link.');
    }
}