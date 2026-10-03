function getApiKey() {
    return localStorage.getItem('shortener_api_key');
}

function getUserEmail() {
    return localStorage.getItem('shortener_user_email');
}

function getIsAdmin() {
    return localStorage.getItem('shortener_is_admin') === 'true';
}

function setSession(apiKey, email, isAdmin = false) {
    localStorage.setItem('shortener_api_key', apiKey);
    localStorage.setItem('shortener_user_email', email);
    localStorage.setItem('shortener_is_admin', isAdmin ? 'true' : 'false');
    updateAuthState();
}

function clearSession() {
    localStorage.removeItem('shortener_api_key');
    localStorage.removeItem('shortener_user_email');
    localStorage.removeItem('shortener_is_admin');
    if (typeof resetUserLinksCache === 'function') {
        resetUserLinksCache();
    }
    updateAuthState();
    if (window.location.pathname === '/admin' || window.location.pathname === '/profile') {
        navigateTo('/', true);
    }
}

function toggleSettingsTray() {
    const tray = document.getElementById('settingsTray');
    if (tray) {
        tray.classList.toggle('hidden');
    } else {
        window.dispatchEvent(new CustomEvent('toggle-settings-tray'));
    }
}

function updateSettingsTrayNavigation(isAuthenticated) {
    let tabNavSettings = document.getElementById('tabNavSettings');
    let mobileNavSettings = document.getElementById('mobileNavSettings');
    const settingsTrayHeaderBtn = document.getElementById('settingsTrayHeaderBtn');
    const nav = document.querySelector('header nav');
    const mobileMenu = document.getElementById('mobileMenu');

    if (isAuthenticated) {
        // Safe DOM fallback creation if not present in static HTML
        if (!tabNavSettings && nav) {
            tabNavSettings = document.createElement('button');
            tabNavSettings.type = 'button';
            tabNavSettings.id = 'tabNavSettings';
            tabNavSettings.className = 'text-xs sm:text-sm font-semibold whitespace-nowrap px-3 sm:px-3.5 py-2 rounded-xl text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white cursor-pointer transition inline-flex items-center gap-1.5';
            tabNavSettings.title = 'Settings Tray';

            const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
            svg.setAttribute('class', 'w-4 h-4');
            svg.setAttribute('fill', 'none');
            svg.setAttribute('stroke', 'currentColor');
            svg.setAttribute('viewBox', '0 0 24 24');

            const p1 = document.createElementNS('http://www.w3.org/2000/svg', 'path');
            p1.setAttribute('stroke-linecap', 'round');
            p1.setAttribute('stroke-linejoin', 'round');
            p1.setAttribute('stroke-width', '2');
            p1.setAttribute('d', 'M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z');
            svg.appendChild(p1);

            const p2 = document.createElementNS('http://www.w3.org/2000/svg', 'path');
            p2.setAttribute('stroke-linecap', 'round');
            p2.setAttribute('stroke-linejoin', 'round');
            p2.setAttribute('stroke-width', '2');
            p2.setAttribute('d', 'M15 12a3 3 0 11-6 0 3 3 0 016 0z');
            svg.appendChild(p2);

            const span = document.createElement('span');
            span.textContent = 'Settings';

            tabNavSettings.appendChild(svg);
            tabNavSettings.appendChild(span);
            tabNavSettings.addEventListener('click', toggleSettingsTray);

            const adminBtn = document.getElementById('tabNavAdmin');
            if (adminBtn) {
                nav.insertBefore(tabNavSettings, adminBtn);
            } else {
                nav.appendChild(tabNavSettings);
            }
        }

        if (!mobileNavSettings && mobileMenu) {
            mobileNavSettings = document.createElement('button');
            mobileNavSettings.type = 'button';
            mobileNavSettings.id = 'mobileNavSettings';
            mobileNavSettings.className = 'w-full text-left text-sm font-semibold px-4 py-3 rounded-xl text-slate-700 dark:text-slate-300 hover:bg-slate-200/50 dark:hover:bg-white/[0.06] transition flex items-center gap-2';

            const mSvg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
            mSvg.setAttribute('class', 'w-4 h-4');
            mSvg.setAttribute('fill', 'none');
            mSvg.setAttribute('stroke', 'currentColor');
            mSvg.setAttribute('viewBox', '0 0 24 24');

            const mp1 = document.createElementNS('http://www.w3.org/2000/svg', 'path');
            mp1.setAttribute('stroke-linecap', 'round');
            mp1.setAttribute('stroke-linejoin', 'round');
            mp1.setAttribute('stroke-width', '2');
            mp1.setAttribute('d', 'M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z');
            mSvg.appendChild(mp1);

            const mp2 = document.createElementNS('http://www.w3.org/2000/svg', 'path');
            mp2.setAttribute('stroke-linecap', 'round');
            mp2.setAttribute('stroke-linejoin', 'round');
            mp2.setAttribute('stroke-width', '2');
            mp2.setAttribute('d', 'M15 12a3 3 0 11-6 0 3 3 0 016 0z');
            mSvg.appendChild(mp2);

            const mSpan = document.createElement('span');
            mSpan.textContent = 'Settings';

            mobileNavSettings.appendChild(mSvg);
            mobileNavSettings.appendChild(mSpan);
            mobileNavSettings.addEventListener('click', () => {
                toggleSettingsTray();
                const menu = document.getElementById('mobileMenu');
                if (menu) menu.classList.add('hidden');
            });

            const mAdmin = document.getElementById('mobileNavAdmin');
            if (mAdmin) {
                mobileMenu.insertBefore(mobileNavSettings, mAdmin);
            } else {
                mobileMenu.appendChild(mobileNavSettings);
            }
        }

        if (tabNavSettings) tabNavSettings.classList.remove('hidden');
        if (mobileNavSettings) mobileNavSettings.classList.remove('hidden');
        if (settingsTrayHeaderBtn) settingsTrayHeaderBtn.classList.remove('hidden');
    } else {
        if (tabNavSettings) tabNavSettings.classList.add('hidden');
        if (mobileNavSettings) mobileNavSettings.classList.add('hidden');
        if (settingsTrayHeaderBtn) settingsTrayHeaderBtn.classList.add('hidden');
    }
}

function initHeaderScrollEffect() {
    const header = document.getElementById('mainHeader');
    if (!header) return;

    const handleScroll = () => {
        if (window.scrollY > 10) {
            header.setAttribute('data-scrolled', 'true');
        } else {
            header.removeAttribute('data-scrolled');
        }
    };

    window.addEventListener('scroll', handleScroll, { passive: true });
    handleScroll();
}

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initHeaderScrollEffect);
} else {
    initHeaderScrollEffect();
}

function updateAuthState() {
    const apiKey = getApiKey();
    const email = getUserEmail();
    const isAdmin = getIsAdmin();
    const isAuthenticated = Boolean(apiKey && email);

    const navGuest = document.getElementById('navGuest');
    const navAuth = document.getElementById('navAuth');
    const userEmailBadge = document.getElementById('userEmailBadge');
    const recentPrompt = document.getElementById('recentLinksGuestPrompt');
    const recentTable = document.getElementById('recentLinksTableWrapper');

    const tabNavAdmin = document.getElementById('tabNavAdmin');
    const mobileNavAdmin = document.getElementById('mobileNavAdmin');

    if (tabNavAdmin) {
        if (isAdmin) {
            tabNavAdmin.classList.remove('hidden');
        } else {
            tabNavAdmin.classList.add('hidden');
        }
    }
    if (mobileNavAdmin) {
        if (isAdmin) {
            mobileNavAdmin.classList.remove('hidden');
        } else {
            mobileNavAdmin.classList.add('hidden');
        }
    }

    updateSettingsTrayNavigation(isAuthenticated);

    if (isAuthenticated) {
        if (navGuest) navGuest.classList.add('hidden');
        if (navAuth) navAuth.classList.remove('hidden');
        if (userEmailBadge) userEmailBadge.textContent = email;
        if (recentPrompt) recentPrompt.classList.add('hidden');
        if (recentTable) recentTable.classList.remove('hidden');
        if (typeof loadUserLinks === 'function') {
            loadUserLinks();
        }
    } else {
        if (navGuest) navGuest.classList.remove('hidden');
        if (navAuth) navAuth.classList.add('hidden');
        if (recentPrompt) recentPrompt.classList.remove('hidden');
        if (recentTable) recentTable.classList.add('hidden');
    }

    if (typeof updateProfileView === 'function') {
        updateProfileView();
    }
}

let isRegisterMode = false;
const tabLogin = document.getElementById('tabLogin');
const tabRegister = document.getElementById('tabRegister');
const authSubmitText = document.getElementById('authSubmitText');
const authModal = document.getElementById('authModal');
const authErrorBanner = document.getElementById('authErrorBanner');
const authForm = document.getElementById('authForm');
const openAuthBtn = document.getElementById('openAuthBtn');
const logoutBtn = document.getElementById('logoutBtn');

if (tabLogin && tabRegister) {
    tabLogin.addEventListener('click', () => {
        isRegisterMode = false;
        tabLogin.className = 'flex-1 pb-3 text-sm font-bold text-brand-600 dark:text-brand-400 border-b-2 border-brand-500 cursor-pointer';
        tabRegister.className = 'flex-1 pb-3 text-sm font-bold text-slate-400 hover:text-slate-600 dark:hover:text-white border-b-2 border-transparent cursor-pointer';
        if (authSubmitText) authSubmitText.textContent = 'Sign In';
        if (authErrorBanner) authErrorBanner.classList.add('hidden');
    });

    tabRegister.addEventListener('click', () => {
        isRegisterMode = true;
        tabRegister.className = 'flex-1 pb-3 text-sm font-bold text-brand-600 dark:text-brand-400 border-b-2 border-brand-500 cursor-pointer';
        tabLogin.className = 'flex-1 pb-3 text-sm font-bold text-slate-400 hover:text-slate-600 dark:hover:text-white border-b-2 border-transparent cursor-pointer';
        if (authSubmitText) authSubmitText.textContent = 'Create Account';
        if (authErrorBanner) authErrorBanner.classList.add('hidden');
    });
}

if (openAuthBtn && authModal) {
    openAuthBtn.addEventListener('click', () => {
        authModal.classList.remove('hidden');
        if (authErrorBanner) authErrorBanner.classList.add('hidden');
    });
}

if (logoutBtn) {
    logoutBtn.addEventListener('click', () => {
        clearSession();
    });
}

if (authModal) {
    authModal.addEventListener('click', (e) => {
        if (e.target === authModal) {
            authModal.classList.add('hidden');
        }
    });
}

window.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
        if (authModal) authModal.classList.add('hidden');
        const qrModal = document.getElementById('qrModal');
        if (qrModal) qrModal.classList.add('hidden');
    }
});

if (authForm) {
    authForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        if (authErrorBanner) authErrorBanner.classList.add('hidden');
        const submitBtn = document.getElementById('authSubmitBtn');
        if (submitBtn) submitBtn.disabled = true;

        const endpoint = isRegisterMode ? '/auth/register' : '/auth/login';
        const payload = {
            email: document.getElementById('authEmail').value.trim(),
            password: document.getElementById('authPassword').value
        };

        try {
            const response = await fetch(endpoint, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });
            const data = await response.json();

            if (!response.ok) {
                if (authErrorBanner) {
                    authErrorBanner.textContent = data.error || 'Authentication failed.';
                    authErrorBanner.classList.remove('hidden');
                }
                return;
            }

            setSession(data.api_key, data.email || payload.email, Boolean(data.is_admin));
            if (authModal) authModal.classList.add('hidden');
            authForm.reset();
            if (typeof loadPlatformAnalytics === 'function') {
                loadPlatformAnalytics();
            }
        } catch (err) {
            if (authErrorBanner) {
                authErrorBanner.textContent = 'Service unavailable. Please retry.';
                authErrorBanner.classList.remove('hidden');
            }
        } finally {
            if (submitBtn) submitBtn.disabled = false;
        }
    });
}