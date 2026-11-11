// Captures the browser's install prompt as early as possible (before any page mounts),
// so the "Install App" button works no matter which page the user was on when it fired.
let deferred: any = null;
const listeners = new Set<() => void>();
const notify = () => listeners.forEach(f => f());

export function initPwa() {
  window.addEventListener('beforeinstallprompt', (e: any) => { e.preventDefault(); deferred = e; notify(); });
  window.addEventListener('appinstalled', () => { deferred = null; notify(); });
  if ('serviceWorker' in navigator) {
    window.addEventListener('load', () => navigator.serviceWorker.register('/sw.js').catch(err => console.warn('SW registration failed', err)));
  }
}

export const isStandalone = () =>
  window.matchMedia?.('(display-mode: standalone)').matches || (navigator as any).standalone === true;

export const isIOS = () =>
  /iphone|ipad|ipod/i.test(navigator.userAgent) || (navigator.platform === 'MacIntel' && navigator.maxTouchPoints > 1);

export const canPrompt = () => !!deferred;

export function onInstallChange(f: () => void) { listeners.add(f); return () => { listeners.delete(f); }; }

export async function installApp() {
  if (isStandalone()) { alert('The app is already installed and running as an app.'); return; }
  if (deferred) {
    deferred.prompt();
    await deferred.userChoice.catch(() => null);
    deferred = null; notify();
    return;
  }
  if (!window.isSecureContext) {
    alert('Installing requires a secure (HTTPS) connection. Open the system from its HTTPS address to install it.');
  } else if (isIOS()) {
    alert('To install on iPhone / iPad:\n\n1. Open this page in Safari\n2. Tap the Share button\n3. Choose "Add to Home Screen"');
  } else {
    alert('To install: open your browser menu and choose "Install app" or "Add to Home screen".\n\nIf it is not shown, the app may already be installed on this device.');
  }
}
