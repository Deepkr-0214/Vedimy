import { AppState } from '../core/state.js';

const root = document.getElementById('navbar-root');

// Apply saved theme immediately
const savedTheme = localStorage.getItem('theme') || 'dark';
document.documentElement.setAttribute('data-theme', savedTheme);

if (root) {
  const user = AppState.getUser();
  const isLandingPage = window.location.pathname === '/' || window.location.pathname.endsWith('index.html');
  
  let centerLinks = '';
  if (isLandingPage) {
    centerLinks = `
      <a href="#features">Features</a>
      <a href="#how">How It Works</a>
      <a href="#roles">For You</a>
    `;
  }

  let rightContent = '';
  if (user) {
    rightContent = `
      <a href="/pages/dashboard.html"><button class="btn-ghost" style="padding:0.4rem 1rem;">Dashboard</button></a>
      <button id="logout-btn" class="btn-primary" style="padding:0.4rem 1rem;background:var(--accent-danger);">Logout</button>
    `;
  } else {
    rightContent = `
      <a href="/pages/login.html"><button class="btn-ghost" style="padding:0.4rem 1rem;">Sign In</button></a>
      <a href="/pages/register.html"><button class="btn-primary" style="padding:0.4rem 1rem;">Sign Up</button></a>
    `;
  }

  const themeIcon = savedTheme === 'dark' ? '☀️' : '🌙';

  root.innerHTML = `
    <nav id="navbar" style="position:fixed;top:0;width:100%;z-index:999;display:flex;align-items:center;justify-content:space-between;padding:1rem 6%;background:var(--nav-bg);backdrop-filter:blur(14px);border-bottom:1px solid var(--border);transition:background 0.3s;">
      <a href="/pages/index.html" style="font-family:'Syne',sans-serif;font-size:1.4rem;font-weight:800;color:var(--text-primary);text-decoration:none;">Vedi<span style="color:var(--accent-primary);">my</span></a>
      
      <div class="nav-links" style="display:flex;gap:2rem;align-items:center;">
        ${centerLinks}
      </div>

      <div class="nav-cta" style="display:flex;gap:0.75rem;align-items:center;">
        <button id="theme-toggle" style="background:transparent;border:none;cursor:pointer;font-size:1.2rem;color:var(--text-primary);padding:0.4rem;border-radius:50%;">${themeIcon}</button>
        ${rightContent}
      </div>

      <div class="hamburger" id="hamburger" style="display:none;flex-direction:column;gap:5px;cursor:pointer;">
        <span style="width:24px;height:2px;background:var(--text-primary);border-radius:2px;transition:all 0.3s;"></span>
        <span style="width:24px;height:2px;background:var(--text-primary);border-radius:2px;transition:all 0.3s;"></span>
        <span style="width:24px;height:2px;background:var(--text-primary);border-radius:2px;transition:all 0.3s;"></span>
      </div>

      <div class="mobile-menu" id="mobile-menu" style="display:none;width:100%;flex-direction:column;gap:0.75rem;padding:1rem 0;position:absolute;top:100%;left:0;background:var(--bg-primary);border-bottom:1px solid var(--border);padding:1rem 6%;">
        ${centerLinks}
        <hr style="border-color:var(--border);">
        ${user ? `
          <a href="/pages/dashboard.html" style="color:var(--accent-primary);">Dashboard</a>
          <a href="#" id="mobile-logout-btn" style="color:var(--accent-danger);">Logout</a>
        ` : `
          <a href="/pages/login.html" style="color:var(--text-secondary);">Sign In</a>
          <a href="/pages/register.html" style="color:var(--accent-primary);">Sign Up</a>
        `}
      </div>
    </nav>
  `;

  // Hamburger menu logic
  const hamburger = document.getElementById('hamburger');
  if (window.innerWidth <= 768) {
    hamburger.style.display = 'flex';
    document.querySelector('.nav-links').style.display = 'none';
    document.querySelector('.nav-cta').style.display = 'none';
  }
  
  window.addEventListener('resize', () => {
    if (window.innerWidth <= 768) {
      hamburger.style.display = 'flex';
      document.querySelector('.nav-links').style.display = 'none';
      document.querySelector('.nav-cta').style.display = 'none';
    } else {
      hamburger.style.display = 'none';
      document.querySelector('.nav-links').style.display = 'flex';
      document.querySelector('.nav-cta').style.display = 'flex';
      document.getElementById('mobile-menu').style.display = 'none';
    }
  });

  hamburger.addEventListener('click', () => {
    const menu = document.getElementById('mobile-menu');
    menu.style.display = menu.style.display === 'flex' ? 'none' : 'flex';
  });

  // Logout logic
  const handleLogout = (e) => {
    e.preventDefault();
    AppState.clearAuth();
    window.location.href = '/pages/login.html';
  };
  document.getElementById('logout-btn')?.addEventListener('click', handleLogout);
  document.getElementById('mobile-logout-btn')?.addEventListener('click', handleLogout);

  // Theme toggle logic
  document.getElementById('theme-toggle')?.addEventListener('click', () => {
    const currentTheme = document.documentElement.getAttribute('data-theme') || 'dark';
    const newTheme = currentTheme === 'dark' ? 'light' : 'dark';
    document.documentElement.setAttribute('data-theme', newTheme);
    localStorage.setItem('theme', newTheme);
    document.getElementById('theme-toggle').textContent = newTheme === 'dark' ? '☀️' : '🌙';
  });
}
