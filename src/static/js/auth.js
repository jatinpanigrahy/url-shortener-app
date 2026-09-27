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

function updateAuthState() {
    const apiKey = getApiKey();
    const email = getUserEmail();
    const isAdmin = getIsAdmin();

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

    if (apiKey && email) {
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