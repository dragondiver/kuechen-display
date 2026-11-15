// Rückweg aus einer App (kuechen-display#10). Der Kiosk hat keine Tabs und keinen Zurück-Knopf.
// Diese Leiste sitzt oben links über jeder https-Seite, die man von der Apps-Seite aus öffnet.
// Bei Spotify liegt sie über dem Logo; daneben ist die Kopfzeile bis zur Suche frei.
// Die Musik läuft auf dem Evoke weiter, wenn man zurückgeht, weil Spotify Connect sie dort hält.
(function () {
  if (window.top !== window || document.getElementById('kuechen-rueckweg')) return;
  const RUHE = 'http://localhost:8080/';
  const wirt = document.createElement('div');
  wirt.id = 'kuechen-rueckweg';
  const schatten = wirt.attachShadow({ mode: 'closed' });
  // Gleiche Strichstärke und Ecken wie die Symbole auf der Apps-Seite (pi/kiosk/index.html).
  const linie = 'fill="none" stroke="#fff" stroke-width="4" stroke-linecap="round" stroke-linejoin="round"';
  schatten.innerHTML = `
    <style>
      :host { all: initial; position: fixed; top: 8px; left: 8px; z-index: 2147483647; }
      .leiste { display: flex; gap: 4px; padding: 0 4px; height: 48px; align-items: center; border-radius: 24px;
                background: rgba(36,40,48,.78); backdrop-filter: blur(20px) saturate(1.3);
                border: 1px solid rgba(255,255,255,.16); box-shadow: 0 4px 18px rgba(0,0,0,.35); }
      a { width: 44px; height: 44px; border-radius: 22px; display: grid; place-items: center;
          -webkit-tap-highlight-color: transparent; transition: background .15s; }
      a:active { background: rgba(255,255,255,.18); }
      svg { width: 26px; height: 26px; }
      .trenner { width: 1px; height: 22px; background: rgba(255,255,255,.18); }
    </style>
    <div class="leiste">
      <a href="${RUHE}?seite=apps" aria-label="Apps">
        <svg viewBox="0 0 64 64" ${linie}><rect x="12" y="12" width="16" height="16" rx="4"/><rect x="36" y="12" width="16" height="16" rx="4"/><rect x="12" y="36" width="16" height="16" rx="4"/><rect x="36" y="36" width="16" height="16" rx="4"/></svg>
      </a>
      <i class="trenner"></i>
      <a href="${RUHE}" aria-label="Heute">
        <svg viewBox="0 0 64 64" ${linie}><circle cx="32" cy="32" r="20"/><path d="M32 20v12l8 6"/></svg>
      </a>
    </div>`;
  document.documentElement.append(wirt);
})();
