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
    body.innerHTML = '';

    if (urls.length === 0) {
        body.innerHTML = '<tr><td colspan="4" class="py-5 text-center text-slate-400 font-normal">No links created yet.</td></tr>';
        return;
    }

    urls.forEach(link => {
        const row = document.createElement('tr');
        row.className = 'hover:bg-slate-100/60 dark:hover:bg-white/[0.02] transition';
        row.innerHTML = `
            <td class="py-3.5 px-4 font-mono text-brand-600 dark:text-brand-400 font-semibold">
                <a href="/${link.short_code}" target="_blank" class="hover:underline">${link.short_code}</a>
            </td>
            <td class="py-3.5 px-4 text-slate-600 dark:text-slate-300 max-w-[180px] truncate" title="${link.original_url}">
                ${link.original_url}
            </td>
            <td class="py-3.5 px-4 text-center text-slate-500 font-bold">
                ${link.click_count}
            </td>
            <td class="py-3.5 px-4 text-right">
                <button onclick="deleteLink('${link.short_code}')" class="text-rose-600 dark:text-rose-400 hover:underline font-semibold cursor-pointer">
                    Delete
                </button>
            </td>
        `;
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
        greeting.innerHTML = `Hey, <span class="text-brand-600 dark:text-brand-400">${username}</span>`;
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
    body.innerHTML = '';

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

        row.innerHTML = `
            <td class="py-3.5 px-3 font-mono text-brand-600 dark:text-brand-400 font-semibold">
                <a href="/${link.short_code}" target="_blank" class="hover:underline">${link.short_code}</a>
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
                <button onclick="deleteLink('${link.short_code}')" class="text-rose-600 dark:text-rose-400 hover:underline font-semibold cursor-pointer">
                    Delete
                </button>
            </td>
        `;
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
    body.innerHTML = '';

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

        let lifecycleBadge = '';
        if (!link.expires_at) {
            lifecycleBadge = '<span class="inline-flex items-center text-[10px] font-bold px-2 py-0.5 rounded-md bg-blue-500/10 text-blue-600 dark:text-blue-400">∞ Permanent</span>';
        } else {
            const isExpired = new Date(link.expires_at) < new Date();
            if (isExpired) {
                lifecycleBadge = '<span class="inline-flex items-center text-[10px] font-bold px-2 py-0.5 rounded-md bg-rose-500/10 text-rose-600 dark:text-rose-400">● Concluded</span>';
            } else {
                lifecycleBadge = '<span class="inline-flex items-center text-[10px] font-bold px-2 py-0.5 rounded-md bg-emerald-500/10 text-emerald-600 dark:text-emerald-400">● Active</span>';
            }
        }

        row.innerHTML = `
            <td class="py-4 px-4 font-bold text-slate-400 text-xs sm:text-sm">#${idx + 1}</td>
            <td class="py-4 px-4">
                <div class="flex items-center gap-2">
                    <a href="/${link.short_code}" target="_blank" class="font-mono text-brand-600 dark:text-brand-400 font-bold text-xs sm:text-sm hover:underline">/${link.short_code}</a>
                    <span class="text-[10px] font-semibold text-slate-500 dark:text-slate-400 bg-slate-100 dark:bg-white/[0.05] px-2 py-0.5 rounded">${host}</span>
                </div>
                <div class="text-[11px] text-slate-400 max-w-[220px] truncate" title="${link.original_url}">${link.original_url}</div>
            </td>
            <td class="py-4 px-4 whitespace-nowrap">
                ${lifecycleBadge}
            </td>
            <td class="py-4 px-4 min-w-[160px]">
                <div class="space-y-1">
                    <div class="flex items-center justify-between text-[10px] font-bold text-slate-500 dark:text-slate-400">
                        <span>${sharePercent}% volume</span>
                    </div>
                    <div class="w-full h-1.5 bg-slate-100 dark:bg-white/[0.06] rounded-full overflow-hidden">
                        <div class="h-full bg-brand-500 rounded-full" style="width: ${Math.min(100, Math.max(4, sharePercent))}%"></div>
                    </div>
                </div>
            </td>
            <td class="py-4 px-4 text-right font-black text-emerald-600 dark:text-emerald-400 text-sm sm:text-base">
                ${clickCount.toLocaleString()}
            </td>
            <td class="py-4 px-4 text-right whitespace-nowrap">
                <div class="inline-flex items-center gap-1.5">
                    <button onclick="copyTableLink('${link.short_code}', this)" class="text-[11px] font-bold px-2.5 py-1 rounded-lg bg-slate-100 dark:bg-white/[0.06] hover:bg-slate-200 dark:hover:bg-white/[0.1] text-slate-700 dark:text-slate-200 transition cursor-pointer">
                        Copy
                    </button>
                    <button onclick="openTableQr('${link.short_code}')" class="text-[11px] font-bold px-2.5 py-1 rounded-lg bg-brand-500/10 text-brand-600 dark:text-brand-400 hover:bg-brand-500/20 transition cursor-pointer">
                        QR
                    </button>
                </div>
            </td>
        `;
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
        container.innerHTML = '';
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
                qrcodeContainer.innerHTML = '';
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