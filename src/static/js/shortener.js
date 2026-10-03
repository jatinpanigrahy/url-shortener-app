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
        aCode.textContent = link.short_code;
        tdCode.appendChild(aCode);

        const tdOriginal = document.createElement('td');
        tdOriginal.className = 'py-3.5 px-4 text-slate-600 dark:text-slate-300 max-w-[180px] truncate';
        tdOriginal.title = link.original_url;
        tdOriginal.textContent = link.original_url;

        const tdClicks = document.createElement('td');
        tdClicks.className = 'py-3.5 px-4 text-center text-slate-500 font-bold';
        tdClicks.textContent = link.click_count;

        const tdAction = document.createElement('td');
        tdAction.className = 'py-3.5 px-4 text-right';
        const delBtn = document.createElement('button');
        delBtn.type = 'button';
        delBtn.className = 'text-rose-600 dark:text-rose-400 hover:underline font-semibold cursor-pointer';
        delBtn.textContent = 'Delete';
        delBtn.addEventListener('click', () => {
            deleteLink(link.short_code);
        });
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
            ? new Date(link.expires_at).toLocaleDateString()
            : 'Permanent';

        const tdCode = document.createElement('td');
        tdCode.className = 'py-3.5 px-3 font-mono text-brand-600 dark:text-brand-400 font-semibold';
        const aCode = document.createElement('a');
        aCode.href = '/' + link.short_code;
        aCode.target = '_blank';
        aCode.className = 'hover:underline';
        aCode.textContent = link.short_code;
        tdCode.appendChild(aCode);

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
        tdAction.className = 'py-3.5 px-3 text-right';
        const delBtn = document.createElement('button');
        delBtn.type = 'button';
        delBtn.className = 'text-rose-600 dark:text-rose-400 hover:underline font-semibold cursor-pointer';
        delBtn.textContent = 'Delete';
        delBtn.addEventListener('click', () => {
            deleteLink(link.short_code);
        });
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
            csvContent += `${u.short_code},${orig},${u.click_count},${u.created_at},${u.expires_at || ''}\n`;
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
            const isExpired = new Date(link.expires_at) < new Date();
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
                    const parsedDate = new Date(data.expires_at);
                    expiryBadge.textContent = 'Expires: ' + parsedDate.toLocaleDateString() + ' ' + parsedDate.toLocaleTimeString();
                } else {
                    expiryBadge.textContent = 'Permanent Link';
                }
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
        if (resultContainer) resultContainer.classList.add('hidden');
        if (errorBanner) errorBanner.classList.add('hidden');
        if (shortUrlDisplay) shortUrlDisplay.href = '#';
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
    loadPlatformAnalytics();
    setInterval(loadPlatformAnalytics, 30000);
});