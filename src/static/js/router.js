const themeToggleBtn = document.getElementById('themeToggleBtn');
const themeIconSun = document.getElementById('themeIconSun');
const themeIconMoon = document.getElementById('themeIconMoon');

function updateThemeIcons() {
    if (document.documentElement.classList.contains('dark')) {
        themeIconSun.classList.remove('hidden');
        themeIconMoon.classList.add('hidden');
    } else {
        themeIconSun.classList.add('hidden');
        themeIconMoon.classList.remove('hidden');
    }
}

if (themeToggleBtn) {
    themeToggleBtn.addEventListener('click', () => {
        if (document.documentElement.classList.contains('dark')) {
            document.documentElement.classList.remove('dark');
            localStorage.setItem('theme', 'light');
        } else {
            document.documentElement.classList.add('dark');
            localStorage.setItem('theme', 'dark');
        }
        updateThemeIcons();
    });
    updateThemeIcons();
}

function toggleMobileMenu() {
    const menu = document.getElementById('mobileMenu');
    if (menu) {
        menu.classList.toggle('hidden');
    }
}

const mobileMenuBtn = document.getElementById('mobileMenuBtn');
if (mobileMenuBtn) {
    mobileMenuBtn.addEventListener('click', toggleMobileMenu);
}

let isProgrammaticScroll = false;

function setNavHighlight(activeId) {
    const tabs = ['tabNavShortener', 'tabNavMyLinks', 'tabNavTopLinks', 'tabNavAbout', 'tabNavProfile', 'tabNavAdmin'];
    const isAdmin = typeof getIsAdmin === 'function' ? getIsAdmin() : false;

    tabs.forEach(id => {
        const btn = document.getElementById(id);
        if (!btn) return;

        const isHidden = (id === 'tabNavAdmin' && !isAdmin);
        const hiddenClass = isHidden ? 'hidden ' : '';

        if (id === activeId) {
            btn.className = `${hiddenClass}text-xs sm:text-sm font-semibold whitespace-nowrap px-3 sm:px-3.5 py-2 rounded-xl bg-white dark:bg-white/[0.08] shadow-sm text-brand-600 dark:text-brand-400 cursor-pointer transition`;
        } else {
            btn.className = `${hiddenClass}text-xs sm:text-sm font-semibold whitespace-nowrap px-3 sm:px-3.5 py-2 rounded-xl text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white cursor-pointer transition`;
        }
    });
}

function switchScreen(viewName) {
    const screens = {
        'shortener': document.getElementById('viewShortener'),
        'top-links': document.getElementById('viewTopLinks'),
        'profile': document.getElementById('viewProfile'),
        'admin': document.getElementById('viewAdmin')
    };

    Object.keys(screens).forEach(key => {
        if (screens[key]) {
            if (key === viewName) {
                screens[key].classList.remove('hidden');
            } else {
                screens[key].classList.add('hidden');
            }
        }
    });

    if (viewName === 'profile' && typeof updateProfileView === 'function') {
        updateProfileView();
    } else if (viewName === 'top-links' && typeof loadPlatformAnalytics === 'function') {
        loadPlatformAnalytics();
    } else if (viewName === 'admin' && typeof initAdminDashboard === 'function') {
        initAdminDashboard();
    }
}

function scrollToSection(targetId) {
    const target = document.getElementById(targetId);
    if (!target) return;

    isProgrammaticScroll = true;

    setTimeout(() => {
        const header = document.querySelector('header');
        const headerHeight = header ? header.offsetHeight : 70;
        const targetTop = target.getBoundingClientRect().top + window.pageYOffset;
        const offsetPosition = targetTop - headerHeight - 16;

        window.scrollTo({
            top: Math.max(0, offsetPosition),
            behavior: 'smooth'
        });

        setTimeout(() => {
            isProgrammaticScroll = false;
        }, 800);
    }, 50);
}

function navigateTo(path, push = true) {
    const mobileMenu = document.getElementById('mobileMenu');
    if (mobileMenu && !mobileMenu.classList.contains('hidden')) {
        mobileMenu.classList.add('hidden');
    }

    if (push && window.location.pathname !== path) {
        window.history.pushState({}, '', path);
    }

    if (path === '/admin') {
        if (typeof getIsAdmin === 'function' && !getIsAdmin()) {
            navigateTo('/', false);
            return;
        }
        switchScreen('admin');
        setNavHighlight('tabNavAdmin');
        window.scrollTo({ top: 0, behavior: 'smooth' });
        return;
    }

    if (path === '/' || path === '') {
        switchScreen('shortener');
        setNavHighlight(null);
        isProgrammaticScroll = true;
        window.scrollTo({ top: 0, behavior: 'smooth' });
        setTimeout(() => { isProgrammaticScroll = false; }, 800);
    } else if (path === '/shortener') {
        switchScreen('shortener');
        setNavHighlight('tabNavShortener');
        scrollToSection('shortener');
    } else if (path === '/my-links') {
        switchScreen('shortener');
        setNavHighlight('tabNavMyLinks');
        scrollToSection('my-links');
    } else if (path === '/about') {
        switchScreen('shortener');
        setNavHighlight('tabNavAbout');
        scrollToSection('about');
    } else if (path === '/top-links') {
        switchScreen('top-links');
        setNavHighlight('tabNavTopLinks');
        window.scrollTo({ top: 0, behavior: 'smooth' });
    } else if (path === '/profile') {
        switchScreen('profile');
        setNavHighlight('tabNavProfile');
        window.scrollTo({ top: 0, behavior: 'smooth' });
    }
}

window.addEventListener('popstate', () => {
    navigateTo(window.location.pathname, false);
});

const observerOptions = {
    root: null,
    rootMargin: '-20% 0px -40% 0px',
    threshold: 0
};

const scrollObserver = new IntersectionObserver((entries) => {
    if (isProgrammaticScroll) return;
    const shortenerScreen = document.getElementById('viewShortener');
    if (!shortenerScreen || shortenerScreen.classList.contains('hidden')) return;

    if (window.scrollY < 300) {
        setNavHighlight(null);
        if (window.location.pathname !== '/') {
            window.history.replaceState({}, '', '/');
        }
        return;
    }

    entries.forEach(entry => {
        if (!entry.isIntersecting) return;
        if (entry.target.id === 'about') {
            setNavHighlight('tabNavAbout');
            if (window.location.pathname !== '/about') {
                window.history.replaceState({}, '', '/about');
            }
        } else if (entry.target.id === 'my-links') {
            setNavHighlight('tabNavMyLinks');
            if (window.location.pathname !== '/my-links') {
                window.history.replaceState({}, '', '/my-links');
            }
        } else if (entry.target.id === 'shortener') {
            setNavHighlight('tabNavShortener');
            if (window.location.pathname !== '/shortener') {
                window.history.replaceState({}, '', '/shortener');
            }
        }
    });
}, observerOptions);

window.addEventListener('scroll', () => {
    if (isProgrammaticScroll) return;
    const shortenerScreen = document.getElementById('viewShortener');
    if (shortenerScreen && !shortenerScreen.classList.contains('hidden')) {
        if (window.scrollY < 200) {
            setNavHighlight(null);
            if (window.location.pathname !== '/') {
                window.history.replaceState({}, '', '/');
            }
        }
    }
});

const elShortener = document.getElementById('shortener');
const elMyLinks = document.getElementById('my-links');
const elAbout = document.getElementById('about');
if (elShortener) scrollObserver.observe(elShortener);
if (elMyLinks) scrollObserver.observe(elMyLinks);
if (elAbout) scrollObserver.observe(elAbout);

function actionConfigureLink() {
    navigateTo('/shortener');
    const aliasInput = document.getElementById('customAlias');
    if (aliasInput) {
        aliasInput.focus();
        aliasInput.classList.add('pulse-highlight');
        setTimeout(() => aliasInput.classList.remove('pulse-highlight'), 1300);
    }
}

function actionGenerateQr() {
    navigateTo('/shortener');
    const urlInput = document.getElementById('longUrl');
    if (urlInput) {
        urlInput.focus();
        urlInput.classList.add('pulse-highlight');
        setTimeout(() => urlInput.classList.remove('pulse-highlight'), 1300);
    }
}

function actionExploreCodes() {
    navigateTo('/top-links');
}

function actionInspectShield() {
    navigateTo('/shortener');
    const urlInput = document.getElementById('longUrl');
    if (urlInput) {
        urlInput.focus();
        urlInput.classList.add('shield-highlight');
        setTimeout(() => urlInput.classList.remove('shield-highlight'), 1300);
    }
}