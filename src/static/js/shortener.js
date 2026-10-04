function parseUTCDate(dateString) {
    if (!dateString) return null;
    let s = String(dateString).trim();
    if (s.includes(' ') && !s.includes('T')) {
        s = s.replace(' ', 'T');
    }
    if (s.includes('T')) {
        const timePart = s.split('T')[1];
        if (timePart !== undefined && !timePart.endsWith('Z') && !timePart.includes('+') && !timePart.match(/-\d{2}:\d{2}$/)) {
            s += 'Z';
        }
    }
    return new Date(s);
}

let userUrlsCache = [];
let platformTotalClicks = 0;
let qrcodeInstance = null;

function resetUserLinksCache() {
    userUrlsCache = [];
}

async function loadUserLinks() {
    const apiKey = getApiKey();
    if (!apiKey) return;

    try {
        const response = await fetch('/my-urls', {
            headers: { 'X-API-Key': apiKey }
        });
        const data = await response.json();

        if (!response.ok) {
            if (response.status === 401) clearSession();
            return;
        }

        userUrlsCache = data.urls || [];
        renderRecentLinks(userUrlsCache.slice(0, 5));
        updateProfileView();
    } catch (err) {
        console.error(err);
    }
}

function refreshMyLinksStats() {
    loadUserLinks();
    loadPlatformAnalytics();
}

function refreshProfileStats() {
    loadUserLinks();
    loadPlatformAnalytics();
}

function renderRecentLinks(urls) {
    const body = document.getElementById('recentLinksTableBody');
    if (!body) return;
    body.textContent = '';

    if (urls.length === 0) {
        const row = document.createElement('tr');
        const td = document.createElement('td');
        td.colSpan = 4;
        td.className = 'py-5 text-center text-slate-400 font-normal';
        td.textContent = 'No links created yet.';
        row.appendChild(td);
        body.appendChild(row);
        return;
    }

    urls.forEach(link => {
        const row = document.createElement('tr');
        row.className = 'hover:bg-slate-100/60 dark:hover:bg-white/[0.02] transition';

        const tdCode = document.createElement('td');
        tdCode.className = 'py-3.5 px-4 font-mono text-brand-600 dark:text-brand-400 font-semibold';
        const aCode = document.createElement('a');
        aCode.href = '/' + link.short_code;
        aCode.target = '_blank';
        aCode.className = 'hover:underline';
        aCode.textContent = '/' + link.short_code;
        tdCode.appendChild(aCode);

        if (link.is_protected) {
            const pwdBadge = document.createElement('span');
            pwdBadge.className = 'password-protected-badge inline-flex items-center gap-1 text-[10px] font-bold px-2 py-0.5 rounded-full bg-amber-500/10 text-amber-600 dark:text-amber-400 shadow-border-subtle ml-2 align-middle';
            pwdBadge.textContent = '🔒 Protected';
            pwdBadge.title = 'Password Protected Link';
            tdCode.appendChild(pwdBadge);
        }

        const devStripInline = document.createElement('div');
        devStripInline.className = 'developer-strip flex items-center gap-1.5 text-[10px] font-mono mt-0.5';
        devStripInline.style.color = 'var(--color-text-secondary, rgba(20, 20, 19, 0.64))';
        const clicksText = document.createElement('span');
        clicksText.textContent = `${Number(link.click_count || 0)} clicks`;
        const dotText = document.createElement('span');
        dotText.textContent = '•';
        dotText.style.opacity = '0.5';
        const dateText = document.createElement('span');
        const linkDate = link.created_at ? parseUTCDate(link.created_at) : null;
        dateText.textContent = linkDate ? linkDate.toLocaleDateString() : 'Permanent';
        devStripInline.appendChild(clicksText);
        devStripInline.appendChild(dotText);
        devStripInline.appendChild(dateText);
        tdCode.appendChild(devStripInline);

        const tdOriginal = document.createElement('td');
        tdOriginal.className = 'py-3.5 px-4 text-slate-600 dark:text-slate-300 max-w-[180px] truncate';
        tdOriginal.title = link.original_url;
        tdOriginal.textContent = link.original_url;

        const tdClicks = document.createElement('td');
        tdClicks.className = 'py-3.5 px-4 text-center text-slate-500 font-bold';
        tdClicks.textContent = link.click_count;

        const tdAction = document.createElement('td');
        tdAction.className = 'py-3.5 px-4 text-right whitespace-nowrap';

        const editBtn = document.createElement('button');
        editBtn.type = 'button';
        editBtn.className = 'btn-edit-destination text-brand-600 dark:text-brand-400 hover:underline font-semibold cursor-pointer mr-3';
        editBtn.textContent = 'Edit';
        editBtn.title = 'Edit destination URL';
        editBtn.addEventListener('click', () => {
            openEditModal(link.short_code, link.original_url);
        });

        const delBtn = document.createElement('button');
        delBtn.type = 'button';
        delBtn.className = 'text-rose-600 dark:text-rose-400 hover:underline font-semibold cursor-pointer';
        delBtn.textContent = 'Delete';
        delBtn.addEventListener('click', () => {
            deleteLink(link.short_code);
        });
        tdAction.appendChild(editBtn);
        tdAction.appendChild(delBtn);

        row.appendChild(tdCode);
        row.appendChild(tdOriginal);
        row.appendChild(tdClicks);
        row.appendChild(tdAction);
        body.appendChild(row);
    });
}

function updateProfileView() {
    const apiKey = getApiKey();
    const email = getUserEmail();
    const guestPrompt = document.getElementById('profileGuestPrompt');
    const authContent = document.getElementById('profileAuthenticatedContent');

    if (!guestPrompt || !authContent) return;

    if (!apiKey || !email) {
        guestPrompt.classList.remove('hidden');
        authContent.classList.add('hidden');
        return;
    }

    guestPrompt.classList.add('hidden');
    authContent.classList.remove('hidden');

    const username = email.split('@')[0];
    const greeting = document.getElementById('profGreeting');
    if (greeting) {
        greeting.textContent = 'Hey, ';
        const span = document.createElement('span');
        span.className = 'text-brand-600 dark:text-brand-400';
        span.textContent = username;
        greeting.appendChild(span);
    }

    const emailEl = document.getElementById('profEmail');
    if (emailEl) emailEl.textContent = email;

    const totalLinksEl = document.getElementById('profTotalLinks');
    if (totalLinksEl) totalLinksEl.textContent = userUrlsCache.length.toLocaleString();

    const totalClicks = userUrlsCache.reduce((acc, curr) => acc + (curr.click_count || 0), 0);
    const totalClicksEl = document.getElementById('profTotalClicks');
    if (totalClicksEl) totalClicksEl.textContent = totalClicks.toLocaleString();

    renderProfileTable(userUrlsCache);
}

function renderProfileTable(urls) {
    const body = document.getElementById('profileLinksTableBody');
    const emptyMsg = document.getElementById('profileEmptyMessage');
    if (!body) return;
    body.textContent = '';

    if (urls.length === 0) {
        if (emptyMsg) emptyMsg.classList.remove('hidden');
        return;
    }
    if (emptyMsg) emptyMsg.classList.add('hidden');

    urls.forEach(link => {
        const row = document.createElement('tr');
        row.className = 'hover:bg-slate-100/60 dark:hover:bg-white/[0.02] transition';
        const formattedExpiry = link.expires_at 
            ? parseUTCDate(link.expires_at).toLocaleDateString()
            : 'Permanent';

        const tdCode = document.createElement('td');
        tdCode.className = 'py-3.5 px-3 font-mono text-brand-600 dark:text-brand-400 font-semibold';
        const aCode = document.createElement('a');
        aCode.href = '/' + link.short_code;
        aCode.target = '_blank';
        aCode.className = 'hover:underline';
        aCode.textContent = '/' + link.short_code;
        tdCode.appendChild(aCode);

        if (link.is_protected) {
            const pwdBadge = document.createElement('span');
            pwdBadge.className = 'password-protected-badge inline-flex items-center gap-1 text-[10px] font-bold px-2 py-0.5 rounded-full bg-amber-500/10 text-amber-600 dark:text-amber-400 shadow-border-subtle ml-2 align-middle';
            pwdBadge.textContent = '🔒 Password Protected';
            pwdBadge.title = 'Password Protected Link';
            tdCode.appendChild(pwdBadge);
        }

        const tdOriginal = document.createElement('td');
        tdOriginal.className = 'py-3.5 px-3 text-slate-600 dark:text-slate-300 max-w-[200px] truncate';
        tdOriginal.title = link.original_url;
        tdOriginal.textContent = link.original_url;

        const tdClicks = document.createElement('td');
        tdClicks.className = 'py-3.5 px-3 text-center text-slate-500 font-bold';
        tdClicks.textContent = link.click_count;

        const tdExpiry = document.createElement('td');
        tdExpiry.className = 'py-3.5 px-3 text-slate-400 whitespace-nowrap';
        tdExpiry.textContent = formattedExpiry;

        const tdAction = document.createElement('td');
        tdAction.className = 'py-3.5 px-3 text-right whitespace-nowrap';

        const editBtn = document.createElement('button');
        editBtn.type = 'button';
        editBtn.className = 'btn-edit-destination text-brand-600 dark:text-brand-400 hover:underline font-semibold cursor-pointer mr-3';
        editBtn.textContent = 'Edit Destination';
        editBtn.title = 'Edit link destination';
        editBtn.addEventListener('click', () => {
            openEditModal(link.short_code, link.original_url);
        });

        const delBtn = document.createElement('button');
        delBtn.type = 'button';
        delBtn.className = 'text-rose-600 dark:text-rose-400 hover:underline font-semibold cursor-pointer';
        delBtn.textContent = 'Delete';
        delBtn.addEventListener('click', () => {
            deleteLink(link.short_code);
        });
        tdAction.appendChild(editBtn);
        tdAction.appendChild(delBtn);

        row.appendChild(tdCode);
        row.appendChild(tdOriginal);
        row.appendChild(tdClicks);
        row.appendChild(tdExpiry);
        row.appendChild(tdAction);
        body.appendChild(row);
    });
}

const profileSearchInput = document.getElementById('profileSearchInput');
if (profileSearchInput) {
    profileSearchInput.addEventListener('input', (e) => {
        const q = e.target.value.toLowerCase().trim();
        const filtered = userUrlsCache.filter(u => 
            u.short_code.toLowerCase().includes(q) || u.original_url.toLowerCase().includes(q)
        );
        renderProfileTable(filtered);
    });
}

const exportCsvBtn = document.getElementById('exportCsvBtn');
if (exportCsvBtn) {
    exportCsvBtn.addEventListener('click', () => {
        if (!userUrlsCache || userUrlsCache.length === 0) {
            alert('No links to export.');
            return;
        }

        let csvContent = 'data:text/csv;charset=utf-8,Short Code,Original URL,Clicks,Created At,Expires At\n';
        userUrlsCache.forEach(u => {
            const orig = `"${u.original_url.replace(/"/g, '""')}"`;
            const ca = u.created_at ? parseUTCDate(u.created_at).toISOString() : '';
            const ea = u.expires_at ? parseUTCDate(u.expires_at).toISOString() : '';
            csvContent += `${u.short_code},${orig},${u.click_count},${ca},${ea}\n`;
        });

        const encodedUri = encodeURI(csvContent);
        const link = document.createElement('a');
        link.setAttribute('href', encodedUri);
        link.setAttribute('download', `my_urls_${Date.now()}.csv`);
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
    });
}

window.deleteLink = async function(shortCode) {
    const apiKey = getApiKey();
    if (!apiKey) return;

    if (!confirm(`Are you sure you want to delete /${shortCode}?`)) return;

    try {
        const response = await fetch(`/${shortCode}`, {
            method: 'DELETE',
            headers: { 'X-API-Key': apiKey }
        });

        if (response.ok) {
            loadUserLinks();
            loadPlatformAnalytics();
        } else {
            const data = await response.json();
            alert(data.error || 'Failed to delete short URL.');
        }
    } catch (err) {
        alert('Network error while deleting short link.');
    }
};

window.openEditModal = function(shortCode, currentUrl) {
    const modal = document.getElementById('editModal');
    const codeInput = document.getElementById('editShortCodeInput');
    const codeDisplay = document.getElementById('editModalShortCode');
    const urlInput = document.getElementById('editDestinationUrl');
    const errBanner = document.getElementById('editModalError');

    if (codeInput) codeInput.value = shortCode;
    if (codeDisplay) codeDisplay.textContent = '/' + shortCode;
    if (urlInput) {
        urlInput.value = currentUrl || '';
        setTimeout(() => urlInput.focus(), 60);
    }
    if (errBanner) {
        errBanner.textContent = '';
        errBanner.classList.add('hidden');
    }
    if (modal) modal.classList.remove('hidden');
};

window.closeEditModal = function() {
    const modal = document.getElementById('editModal');
    if (modal) modal.classList.add('hidden');
    const errBanner = document.getElementById('editModalError');
    if (errBanner) errBanner.classList.add('hidden');
};

function initEditModal() {
    const editForm = document.getElementById('editDestinationForm');
    if (!editForm) return;

    editForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        const codeInput = document.getElementById('editShortCodeInput');
        const urlInput = document.getElementById('editDestinationUrl');
        const errBanner = document.getElementById('editModalError');
        const submitBtn = document.getElementById('editSubmitBtn');
        const submitText = document.getElementById('editSubmitText');

        const shortCode = codeInput ? codeInput.value.trim() : '';
        let newUrl = urlInput ? urlInput.value.trim() : '';
        if (!shortCode || !newUrl) return;

        if (!newUrl.startsWith('http://') && !newUrl.startsWith('https://')) {
            newUrl = 'https://' + newUrl;
        }

        const apiKey = getApiKey();
        if (!apiKey) {
            if (errBanner) {
                errBanner.textContent = 'Sign-in required to edit short link destinations.';
                errBanner.classList.remove('hidden');
            }
            return;
        }

        if (submitBtn) submitBtn.disabled = true;
        if (submitText) submitText.textContent = 'Saving...';
        if (errBanner) errBanner.classList.add('hidden');

        try {
            const response = await fetch(`/${shortCode}`, {
                method: 'PATCH',
                headers: {
                    'Content-Type': 'application/json',
                    'X-API-Key': apiKey
                },
                body: JSON.stringify({ original_url: newUrl, url: newUrl })
            });
            const data = await response.json();

            if (!response.ok) {
                if (errBanner) {
                    errBanner.textContent = data.error || 'Failed to update destination.';
                    errBanner.classList.remove('hidden');
                }
                return;
            }

            closeEditModal();
            loadUserLinks();
            loadPlatformAnalytics();
        } catch (err) {
            if (errBanner) {
                errBanner.textContent = 'Network error while updating destination.';
                errBanner.classList.remove('hidden');
            }
        } finally {
            if (submitBtn) submitBtn.disabled = false;
            if (submitText) submitText.textContent = 'Save Destination';
        }
    });
}

window.openPasswordModal = function(shortCode, onUnlockedCallback) {
    const modal = document.getElementById('passwordModal');
    const codeInput = document.getElementById('passwordModalShortCode');
    const subtitle = document.getElementById('passwordModalSubtitle');
    const pwdInput = document.getElementById('linkPasswordInput');
    const errBanner = document.getElementById('passwordModalError');

    if (codeInput) codeInput.value = shortCode || '';
    if (subtitle) {
        subtitle.textContent = shortCode 
            ? `Short link /${shortCode} is password-protected. Enter the passphrase to unlock its destination.`
            : 'This short link requires an access password to proceed.';
    }
    if (pwdInput) {
        pwdInput.value = '';
        setTimeout(() => pwdInput.focus(), 60);
    }
    if (errBanner) {
        errBanner.textContent = '';
        errBanner.classList.add('hidden');
    }
    window._passwordModalCallback = onUnlockedCallback || null;
    if (modal) modal.classList.remove('hidden');
};

window.closePasswordModal = function() {
    const modal = document.getElementById('passwordModal');
    if (modal) modal.classList.add('hidden');
    const errBanner = document.getElementById('passwordModalError');
    if (errBanner) errBanner.classList.add('hidden');
    window._passwordModalCallback = null;
};

function initPasswordModal() {
    const pwdForm = document.getElementById('passwordPromptForm');
    if (!pwdForm) return;

    pwdForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        const codeInput = document.getElementById('passwordModalShortCode');
        const pwdInput = document.getElementById('linkPasswordInput');
        const errBanner = document.getElementById('passwordModalError');
        const submitBtn = document.getElementById('passwordSubmitBtn');
        const submitText = document.getElementById('passwordSubmitText');

        const shortCode = codeInput ? codeInput.value.trim() : '';
        const password = pwdInput ? pwdInput.value : '';
        if (!shortCode || !password) return;

        if (submitBtn) submitBtn.disabled = true;
        if (submitText) submitText.textContent = 'Verifying...';
        if (errBanner) errBanner.classList.add('hidden');

        try {
            const response = await fetch(`/${shortCode}`, {
                method: 'GET',
                headers: {
                    'X-Link-Password': password,
                    'Accept': 'application/json'
                }
            });

            if (response.status === 401) {
                if (errBanner) {
                    errBanner.textContent = 'Invalid password. Please try again.';
                    errBanner.classList.remove('hidden');
                }
                if (pwdInput) {
                    pwdInput.value = '';
                    pwdInput.focus();
                }
                return;
            }

            if (response.status === 410) {
                if (errBanner) {
                    errBanner.textContent = 'This short link has expired.';
                    errBanner.classList.remove('hidden');
                }
                return;
            }

            if (response.status === 404) {
                if (errBanner) {
                    errBanner.textContent = 'Short link not found.';
                    errBanner.classList.remove('hidden');
                }
                return;
            }

            closePasswordModal();

            if (typeof window._passwordModalCallback === 'function') {
                window._passwordModalCallback(password);
                return;
            }

            if (response.url && !response.url.endsWith(`/${shortCode}`)) {
                window.location.href = response.url;
            } else {
                window.location.href = `/${shortCode}`;
            }
        } catch (err) {
            closePasswordModal();
            window.location.href = `/${shortCode}`;
        } finally {
            if (submitBtn) submitBtn.disabled = false;
            if (submitText) submitText.textContent = 'Access Destination';
        }
    });
}

function initSettingsTray() {
    const reqToggle = document.getElementById('requirePasswordToggle');
    const pwdContainer = document.getElementById('linkPasswordContainer');
    const pwdInput = document.getElementById('linkPassword');

    if (reqToggle && pwdContainer) {
        reqToggle.addEventListener('change', () => {
            if (reqToggle.checked) {
                pwdContainer.classList.remove('hidden');
                if (pwdInput) pwdInput.focus();
            } else {
                pwdContainer.classList.add('hidden');
                if (pwdInput) pwdInput.value = '';
            }
        });
    }
}

async function loadPlatformAnalytics() {
    try {
        const response = await fetch('/analytics');
        if (!response.ok) return;

        const data = await response.json();
        platformTotalClicks = Number(data.total_clicks || 0);

        const statTotalLinks = document.getElementById('statTotalLinks');
        const statTotalClicks = document.getElementById('statTotalClicks');
        const statTotalUsers = document.getElementById('statTotalUsers');
        const statActiveLinks = document.getElementById('statActiveLinks');

        if (statTotalLinks) statTotalLinks.textContent = Number(data.total_links || 0).toLocaleString();
        if (statTotalClicks) statTotalClicks.textContent = platformTotalClicks.toLocaleString();
        if (statTotalUsers) statTotalUsers.textContent = Number(data.total_users || 0).toLocaleString();
        if (statActiveLinks) statActiveLinks.textContent = Number(data.active_links || 0).toLocaleString();

        renderTopUrls(data.top_5_urls || []);
    } catch (err) {
        console.error(err);
    }
}

function extractHostname(urlStr) {
    try {
        const parsed = new URL(urlStr);
        return parsed.hostname.replace(/^www\./, '');
    } catch (e) {
        return 'web-target';
    }
}

function renderTopUrls(urls) {
    const body = document.getElementById('topUrlsTableBody');
    const emptyMsg = document.getElementById('emptyTopUrlsMessage');
    if (!body) return;
    body.textContent = '';

    if (urls.length === 0) {
        if (emptyMsg) emptyMsg.classList.remove('hidden');
        return;
    }
    if (emptyMsg) emptyMsg.classList.add('hidden');

    urls.forEach((link, idx) => {
        const row = document.createElement('tr');
        row.className = 'hover:bg-slate-100/60 dark:hover:bg-white/[0.02] transition';

        const host = extractHostname(link.original_url);
        const clickCount = Number(link.click_count || 0);
        const sharePercent = platformTotalClicks > 0 
            ? ((clickCount / platformTotalClicks) * 100).toFixed(1) 
            : 0;

        const tdRank = document.createElement('td');
        tdRank.className = 'py-4 px-4 font-bold text-slate-400 text-xs sm:text-sm';
        tdRank.textContent = '#' + (idx + 1);

        const tdDetails = document.createElement('td');
        tdDetails.className = 'py-4 px-4';
        const titleRow = document.createElement('div');
        titleRow.className = 'flex items-center gap-2';
        const codeAnchor = document.createElement('a');
        codeAnchor.href = '/' + link.short_code;
        codeAnchor.target = '_blank';
        codeAnchor.className = 'font-mono text-brand-600 dark:text-brand-400 font-bold text-xs sm:text-sm hover:underline';
        codeAnchor.textContent = '/' + link.short_code;
        const hostBadge = document.createElement('span');
        hostBadge.className = 'text-[10px] font-semibold text-slate-500 dark:text-slate-400 bg-slate-100 dark:bg-white/[0.05] px-2 py-0.5 rounded';
        hostBadge.textContent = host;
        titleRow.appendChild(codeAnchor);
        titleRow.appendChild(hostBadge);

        const origUrlDiv = document.createElement('div');
        origUrlDiv.className = 'text-[11px] text-slate-400 max-w-[220px] truncate';
        origUrlDiv.title = link.original_url;
        origUrlDiv.textContent = link.original_url;

        tdDetails.appendChild(titleRow);
        tdDetails.appendChild(origUrlDiv);

        const tdLifecycle = document.createElement('td');
        tdLifecycle.className = 'py-4 px-4 whitespace-nowrap';
        const badgeSpan = document.createElement('span');
        badgeSpan.className = 'inline-flex items-center text-[10px] font-bold px-2 py-0.5 rounded-md';
        if (!link.expires_at) {
            badgeSpan.classList.add('bg-blue-500/10', 'text-blue-600', 'dark:text-blue-400');
            badgeSpan.textContent = '∞ Permanent';
        } else {
            const isExpired = parseUTCDate(link.expires_at) < new Date();
            if (isExpired) {
                badgeSpan.classList.add('bg-rose-500/10', 'text-rose-600', 'dark:text-rose-400');
                badgeSpan.textContent = '● Concluded';
            } else {
                badgeSpan.classList.add('bg-emerald-500/10', 'text-emerald-600', 'dark:text-emerald-400');
                badgeSpan.textContent = '● Active';
            }
        }
        tdLifecycle.appendChild(badgeSpan);

        const tdVolume = document.createElement('td');
        tdVolume.className = 'py-4 px-4 min-w-[160px]';
        const volContainer = document.createElement('div');
        volContainer.className = 'space-y-1';
        const volTextRow = document.createElement('div');
        volTextRow.className = 'flex items-center justify-between text-[10px] font-bold text-slate-500 dark:text-slate-400';
        const volText = document.createElement('span');
        volText.textContent = sharePercent + '% volume';
        volTextRow.appendChild(volText);

        const barOuter = document.createElement('div');
        barOuter.className = 'w-full h-1.5 bg-slate-100 dark:bg-white/[0.06] rounded-full overflow-hidden';
        const barFill = document.createElement('div');
        barFill.className = 'h-full bg-brand-500 rounded-full';
        barFill.style.width = Math.min(100, Math.max(4, sharePercent)) + '%';
        barOuter.appendChild(barFill);

        volContainer.appendChild(volTextRow);
        volContainer.appendChild(barOuter);
        tdVolume.appendChild(volContainer);

        const tdClicks = document.createElement('td');
        tdClicks.className = 'py-4 px-4 text-right font-black text-emerald-600 dark:text-emerald-400 text-sm sm:text-base';
        tdClicks.textContent = clickCount.toLocaleString();

        const tdAction = document.createElement('td');
        tdAction.className = 'py-4 px-4 text-right whitespace-nowrap';
        const btnGroup = document.createElement('div');
        btnGroup.className = 'inline-flex items-center gap-1.5';

        const copyBtn = document.createElement('button');
        copyBtn.type = 'button';
        copyBtn.className = 'text-[11px] font-bold px-2.5 py-1 rounded-lg bg-slate-100 dark:bg-white/[0.06] hover:bg-slate-200 dark:hover:bg-white/[0.1] text-slate-700 dark:text-slate-200 transition cursor-pointer';
        copyBtn.textContent = 'Copy';
        copyBtn.addEventListener('click', function() {
            copyTableLink(link.short_code, this);
        });

        const qrBtn = document.createElement('button');
        qrBtn.type = 'button';
        qrBtn.className = 'text-[11px] font-bold px-2.5 py-1 rounded-lg bg-brand-500/10 text-brand-600 dark:text-brand-400 hover:bg-brand-500/20 transition cursor-pointer';
        qrBtn.textContent = 'QR';
        qrBtn.addEventListener('click', function() {
            openTableQr(link.short_code);
        });

        btnGroup.appendChild(copyBtn);
        btnGroup.appendChild(qrBtn);
        tdAction.appendChild(btnGroup);

        row.appendChild(tdRank);
        row.appendChild(tdDetails);
        row.appendChild(tdLifecycle);
        row.appendChild(tdVolume);
        row.appendChild(tdClicks);
        row.appendChild(tdAction);
        body.appendChild(row);
    });
}

window.copyTableLink = async function(shortCode, btnElement) {
    const fullUrl = window.location.origin + '/' + shortCode;
    try {
        await navigator.clipboard.writeText(fullUrl);
    } catch (err) {
        const el = document.createElement('textarea');
        el.value = fullUrl;
        document.body.appendChild(el);
        el.select();
        document.execCommand('copy');
        document.body.removeChild(el);
    }

    const originalText = btnElement.textContent;
    btnElement.textContent = 'Copied!';
    btnElement.classList.add('text-emerald-600');
    setTimeout(() => {
        btnElement.textContent = originalText;
        btnElement.classList.remove('text-emerald-600');
    }, 1800);
};

window.openTableQr = function(shortCode) {
    const fullUrl = window.location.origin + '/' + shortCode;
    const title = document.getElementById('qrModalTitle');
    const subtitle = document.getElementById('qrModalSubtitle');
    const container = document.getElementById('modalQrCode');

    if (title) title.textContent = '/' + shortCode;
    if (subtitle) subtitle.textContent = fullUrl;

    if (container) {
        container.textContent = '';
        new QRCode(container, {
            text: fullUrl,
            width: 130,
            height: 130,
            colorDark: '#0a0a0c',
            colorLight: '#ffffff',
            correctLevel: QRCode.CorrectLevel.M
        });
    }

    const modal = document.getElementById('qrModal');
    if (modal) modal.classList.remove('hidden');
};

const shortenForm = document.getElementById('shortenForm');
if (shortenForm) {
    shortenForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        const errorBanner = document.getElementById('errorBanner');
        const errorMessage = document.getElementById('errorMessage');
        const submitBtn = document.getElementById('submitBtn');
        const submitSpinner = document.getElementById('submitSpinner');
        const submitText = document.getElementById('submitText');

        if (errorBanner) errorBanner.classList.add('hidden');
        if (errorMessage) errorMessage.textContent = '';
        if (submitBtn) submitBtn.disabled = true;
        if (submitSpinner) submitSpinner.classList.remove('hidden');
        if (submitText) submitText.textContent = 'Processing Link...';

        let rawUrl = document.getElementById('longUrl').value.trim();
        if (rawUrl && !rawUrl.startsWith('http://') && !rawUrl.startsWith('https://')) {
            rawUrl = 'https://' + rawUrl;
        }

        const payload = { url: rawUrl };

        const customAlias = document.getElementById('customAlias').value.trim();
        if (customAlias) {
            payload.custom_alias = customAlias;
        }

        const ttlVal = document.getElementById('ttlValue').value.trim();
        if (ttlVal) {
            const multiplier = parseInt(document.getElementById('ttlUnit').value, 10);
            payload.ttl_seconds = parseInt(ttlVal, 10) * multiplier;
        }

        const reqPasswordToggle = document.getElementById('requirePasswordToggle');
        const linkPasswordInput = document.getElementById('linkPassword');
        if (linkPasswordInput && ((reqPasswordToggle && reqPasswordToggle.checked) || linkPasswordInput.value.trim())) {
            const pwdVal = linkPasswordInput.value.trim();
            if (pwdVal) {
                payload.link_password = pwdVal;
            }
        }

        const headers = {
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        };

        const apiKey = getApiKey();
        if (apiKey) {
            headers['X-API-Key'] = apiKey;
        }

        try {
            const response = await fetch('/shorten', {
                method: 'POST',
                headers: headers,
                body: JSON.stringify(payload)
            });

            const data = await response.json();

            if (!response.ok) {
                if (response.status === 401) {
                    if (data.requires_password || (data.error && data.error.toLowerCase().includes('password'))) {
                        openPasswordModal(data.short_code || '', () => {
                            // Retry link generation or access
                        });
                        return;
                    }
                }
                if (errorMessage) errorMessage.textContent = data.error || data.message || 'Validation rejected by platform.';
                if (errorBanner) errorBanner.classList.remove('hidden');
                return;
            }

            const shortDisplay = document.getElementById('shortUrlDisplay');
            const shortText = document.getElementById('shortUrlText');
            if (shortDisplay) shortDisplay.href = data.short_url;
            if (shortText) shortText.textContent = data.short_url;

            const expiryBadge = document.getElementById('expiryBadge');
            if (expiryBadge) {
                if (data.expires_at) {
                    const parsedDate = parseUTCDate(data.expires_at);
                    expiryBadge.textContent = 'Expires: ' + parsedDate.toLocaleDateString() + ' ' + parsedDate.toLocaleTimeString();
                } else {
                    expiryBadge.textContent = 'Permanent Link';
                }
            }

            // Inline "Developer Strip" analytics beneath generated short links in UI feed
            let devStrip = document.getElementById('developerStrip');
            if (!devStrip) {
                devStrip = document.createElement('div');
                devStrip.id = 'developerStrip';
                devStrip.className = 'developer-strip flex flex-wrap items-center gap-2 text-[11px] font-mono px-1';
                devStrip.style.color = 'var(--color-text-secondary, rgba(20, 20, 19, 0.64))';
                const linkRow = shortDisplay ? shortDisplay.parentElement : null;
                if (linkRow && linkRow.parentElement) {
                    linkRow.parentElement.insertBefore(devStrip, linkRow.nextSibling);
                }
            }
            devStrip.textContent = '';

            const clicksSpan = document.createElement('span');
            clicksSpan.className = 'font-semibold';
            clicksSpan.textContent = `${Number(data.clicks || data.click_count || 0)} clicks`;

            const dot1 = document.createElement('span');
            dot1.textContent = '•';
            dot1.style.opacity = '0.5';

            const createdSpan = document.createElement('span');
            const createdDate = data.created_at ? parseUTCDate(data.created_at) : new Date();
            createdSpan.textContent = `Created: ${createdDate.toLocaleDateString()} ${createdDate.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}`;

            devStrip.appendChild(clicksSpan);
            devStrip.appendChild(dot1);
            devStrip.appendChild(createdSpan);

            if (data.expires_at) {
                const dot2 = document.createElement('span');
                dot2.textContent = '•';
                dot2.style.opacity = '0.5';
                const expirySpan = document.createElement('span');
                const expDate = parseUTCDate(data.expires_at);
                expirySpan.textContent = `Expires: ${expDate.toLocaleDateString()} ${expDate.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}`;
                devStrip.appendChild(dot2);
                devStrip.appendChild(expirySpan);
            }

            // Terracotta pulse animation on newly generated link element (0ms delay for DOM insertion)
            if (shortDisplay) {
                shortDisplay.classList.remove('snap-pulse');
                void shortDisplay.offsetWidth;
                shortDisplay.classList.add('snap-pulse');
            }

            const qrcodeContainer = document.getElementById('qrcode');
            if (qrcodeContainer) {
                qrcodeContainer.textContent = '';
                qrcodeInstance = new QRCode(qrcodeContainer, {
                    text: data.short_url,
                    width: 120,
                    height: 120,
                    colorDark: '#0a0a0c',
                    colorLight: '#ffffff',
                    correctLevel: QRCode.CorrectLevel.M
                });
            }

            const resultContainer = document.getElementById('resultContainer');
            if (resultContainer) {
                resultContainer.classList.remove('hidden');
                resultContainer.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
            }

            loadPlatformAnalytics();
            if (apiKey) {
                loadUserLinks();
            }

        } catch (err) {
            if (errorMessage) errorMessage.textContent = 'Gateway offline. Verify local service execution.';
            if (errorBanner) errorBanner.classList.remove('hidden');
        } finally {
            if (submitBtn) submitBtn.disabled = false;
            if (submitSpinner) submitSpinner.classList.add('hidden');
            if (submitText) submitText.textContent = 'Generate Short URL';
        }
    });
}

const copyBtn = document.getElementById('copyBtn');
if (copyBtn) {
    copyBtn.addEventListener('click', async () => {
        const shortLink = document.getElementById('shortUrlDisplay').href;
        if (!shortLink || shortLink === '#' || shortLink.endsWith('/#')) return;

        try {
            await navigator.clipboard.writeText(shortLink);
        } catch (err) {
            const el = document.createElement('textarea');
            el.value = shortLink;
            document.body.appendChild(el);
            el.select();
            document.execCommand('copy');
            document.body.removeChild(el);
        }

        const copyText = document.getElementById('copyText');
        if (copyText) {
            copyText.textContent = 'Copied!';
            setTimeout(() => { copyText.textContent = 'Copy'; }, 2000);
        }
    });
}

const downloadQrBtn = document.getElementById('downloadQrBtn');
if (downloadQrBtn) {
    downloadQrBtn.addEventListener('click', () => {
        const canvas = document.querySelector('#qrcode canvas');
        const img = document.querySelector('#qrcode img');
        let dataUrl = null;

        if (canvas) {
            dataUrl = canvas.toDataURL('image/png');
        } else if (img && img.src) {
            dataUrl = img.src;
        }

        if (!dataUrl) {
            alert('QR Code not generated yet.');
            return;
        }

        const a = document.createElement('a');
        a.href = dataUrl;
        a.download = `qrcode_${Date.now()}.png`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
    });
}

const resetBtn = document.getElementById('resetBtn');
if (resetBtn) {
    resetBtn.addEventListener('click', () => {
        const form = document.getElementById('shortenForm');
        const resultContainer = document.getElementById('resultContainer');
        const errorBanner = document.getElementById('errorBanner');
        const shortUrlDisplay = document.getElementById('shortUrlDisplay');
        const shortUrlText = document.getElementById('shortUrlText');
        const longUrl = document.getElementById('longUrl');

        if (form) form.reset();

        const reqToggle = document.getElementById('requirePasswordToggle');
        if (reqToggle) reqToggle.checked = false;
        const pwdContainer = document.getElementById('linkPasswordContainer');
        if (pwdContainer) pwdContainer.classList.add('hidden');
        const pwdInput = document.getElementById('linkPassword');
        if (pwdInput) pwdInput.value = '';

        if (resultContainer) resultContainer.classList.add('hidden');
        if (errorBanner) errorBanner.classList.add('hidden');
        const devStrip = document.getElementById('developerStrip');
        if (devStrip) devStrip.remove();
        if (shortUrlDisplay) {
            shortUrlDisplay.classList.remove('snap-pulse');
            shortUrlDisplay.href = '#';
        }
        if (shortUrlText) shortUrlText.textContent = '';
        if (longUrl) longUrl.focus();
    });
}

document.addEventListener('DOMContentLoaded', () => {
    const currentPath = window.location.pathname;
    if (['/shortener', '/my-links', '/top-links', '/about', '/profile', '/admin'].includes(currentPath)) {
        navigateTo(currentPath, false);
    } else {
        navigateTo('/', false);
    }
    updateAuthState();
    initSettingsTray();
    initEditModal();
    initPasswordModal();
    loadPlatformAnalytics();
    setInterval(loadPlatformAnalytics, 30000);
});