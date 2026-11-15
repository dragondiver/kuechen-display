// Rückweg aus einer App (kuechen-display#10). Der Kiosk hat keine Tabs und keinen Zurück-Knopf.
// Diese Leiste sitzt oben links über jeder https-Seite, die man von der Apps-Seite aus öffnet.
// Bei Spotify liegt sie über dem Logo; daneben ist die Kopfzeile bis zur Suche frei.
// Die Musik läuft auf dem Evoke weiter, wenn man zurückgeht, weil Spotify Connect sie dort hält.
// Der Mikro-Knopf rechts startet und beendet das Gespräch mit Elektra wie der Tipp aufs Mikrofon
// der Kiosk-Seite (#70). Befehle, die Elektra währenddessen schickt („zurück zu heute“), holt die
// Leiste jede Sekunde über den Hintergrund (hintergrund.js) beim Küchen-Dienst ab.
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
      a, button { all: unset; width: 44px; height: 44px; border-radius: 22px; display: grid; place-items: center;
          -webkit-tap-highlight-color: transparent; transition: background .15s; }
      a:active, button:active { background: rgba(255,255,255,.18); }
      button { cursor: pointer; transition: background .2s, opacity .3s; }
      /* Wie das Mikrofon der Kiosk-Seite: gedimmt im Ruhezustand, orange, solange Elektra dran ist. */
      .leiste[data-zustand="aus"] button { opacity: .7; }
      .leiste:not([data-zustand="aus"]) button { background: rgba(243,154,43,.28); }
      .leiste:not([data-zustand="aus"]) button svg { filter: drop-shadow(0 0 6px rgba(243,154,43,.9)); }
      .leiste[data-zustand="nachdenken"] button { animation: atmen 1.4s ease-in-out infinite; }
      .leiste[data-verbunden="nein"] button { opacity: .25; }
      @keyframes atmen { 50% { background: rgba(243,154,43,.1); } }
      svg { width: 26px; height: 26px; }
      .trenner { width: 1px; height: 22px; background: rgba(255,255,255,.18); }
    </style>
    <div class="leiste" data-zustand="aus" data-verbunden="nein">
      <a href="${RUHE}?seite=apps" aria-label="Apps">
        <svg viewBox="0 0 64 64" ${linie}><rect x="12" y="12" width="16" height="16" rx="4"/><rect x="36" y="12" width="16" height="16" rx="4"/><rect x="12" y="36" width="16" height="16" rx="4"/><rect x="36" y="36" width="16" height="16" rx="4"/></svg>
      </a>
      <i class="trenner"></i>
      <a href="${RUHE}" aria-label="Heute">
        <svg viewBox="0 0 64 64" ${linie}><circle cx="32" cy="32" r="20"/><path d="M32 20v12l8 6"/></svg>
      </a>
      <i class="trenner"></i>
      <button aria-label="Mit Elektra sprechen">
        <svg viewBox="0 0 64 64" ${linie}><rect x="24" y="10" width="16" height="28" rx="8"/><path d="M16 32a16 16 0 0 0 32 0M32 48v8M24 56h16"/></svg>
      </button>
    </div>`;
  document.documentElement.append(wirt);

  const leiste = schatten.querySelector('.leiste');
  let diktatLage = function () {};  // wird unten vom Diktat gesetzt
  const SEITEN = ['heute', 'morgen', 'apps'];
  const APPS = { spotify: 'https://open.spotify.com/' };  // wie data-app in pi/kiosk/index.html
  function melde(pfad, daten) {
    return new Promise(function (fertig) {
      function nichts(grund) { return { ok: false, daten: { fehler: grund } }; }
      try {
        chrome.runtime.sendMessage({ art: 'melde', pfad: pfad, daten: daten }, function (a) {
          if (chrome.runtime.lastError) fertig(nichts('Erweiterung: ' + chrome.runtime.lastError.message));
          else fertig(a || nichts('Keine Antwort vom Hintergrund'));
        });
      } catch (e) { fertig(nichts('Erweiterung: ' + e.message)); }  // z. B. nach Neuladen der Erweiterung
    });
  }
  function quittiere(id, fehler, danach) {
    melde('/quittung', fehler ? { id: id, ok: false, fehler: fehler } : { id: id, ok: true }).then(danach || function () {});
  }
  function ausfuehren(b) {
    const arg = b.argumente || {};
    if (b.name === 'seite_zeigen' && SEITEN.includes(arg.seite)) {
      quittiere(b.id, null, function () { location.href = RUHE + (arg.seite === 'heute' ? '' : '?seite=' + arg.seite); });
    } else if (b.name === 'app_oeffnen' && APPS[arg.name]) {
      const ziel = APPS[arg.name];
      quittiere(b.id, null, function () { if (new URL(ziel).host !== location.host) location.href = ziel; });
    } else {
      quittiere(b.id, b.name === 'rezeptschritt' ? 'Es ist kein Rezept offen.' : 'Das geht in dieser App nicht: ' + b.name);
    }
  }
  function frage() {
    if (document.hidden) return;
    try {
      chrome.runtime.sendMessage({ art: 'lage' }, function (lage) {
        if (chrome.runtime.lastError || !lage) { leiste.dataset.verbunden = 'nein'; return; }
        leiste.dataset.zustand = lage.zustand;
        leiste.dataset.verbunden = lage.verbunden ? 'ja' : 'nein';
        if (lage.befehl) ausfuehren(lage.befehl);
        diktatLage(!!lage.diktat);
      });
    } catch (e) { leiste.dataset.verbunden = 'nein'; }
  }
  schatten.querySelector('button').addEventListener('click', function () { melde('/tipp').then(frage); });
  frage();
  setInterval(frage, 1000);

  // --- Diktat ins Suchfeld (#70), ohne Elektra ------------------------------------------------
  // Hat ein Textfeld den Fokus (Spotify: „Was möchtest du wiedergeben?“), erscheint darunter ein
  // Knopf „Sprechen“. Der Küchen-Dienst nimmt auf und schickt den Ton an die OpenAI-Transkription;
  // der Text ersetzt den Inhalt des Feldes.
  const diktatWirt = document.createElement('div');
  diktatWirt.id = 'kuechen-diktat';
  const ds = diktatWirt.attachShadow({ mode: 'closed' });
  ds.innerHTML = `
    <style>
      :host { all: initial; position: fixed; z-index: 2147483647; display: none; }
      :host(.an) { display: block; }
      button { all: unset; box-sizing: border-box; min-height: 48px; max-width: 520px; white-space: normal !important; padding: 0 20px 0 14px; display: flex; gap: 10px;
               align-items: center; border-radius: 24px; cursor: pointer; -webkit-tap-highlight-color: transparent;
               font: 700 17px/1 SpotifyMixUI, CircularSp, sans-serif; color: #fff; white-space: nowrap;
               background: rgba(36,40,48,.9); backdrop-filter: blur(20px) saturate(1.3);
               border: 1px solid rgba(255,255,255,.16); box-shadow: 0 6px 22px rgba(0,0,0,.45);
               transition: background .2s, color .2s; }
      svg { width: 24px; height: 24px; flex: none; }
      button[data-stand="hoert"] { background: rgb(243,154,43); color: #1d1206; animation: hoeren 1.2s ease-in-out infinite; }
      button[data-stand="denkt"] { color: rgba(255,255,255,.7); }
      button[data-stand="fehler"] { background: rgba(120,30,30,.92); }
      @keyframes hoeren { 50% { box-shadow: 0 0 0 8px rgba(243,154,43,.25), 0 6px 22px rgba(0,0,0,.45); } }
    </style>
    <button data-stand="bereit" aria-label="Suchbegriff sprechen">
      <svg viewBox="0 0 64 64" fill="none" stroke="currentColor" stroke-width="4.5" stroke-linecap="round" stroke-linejoin="round"><rect x="24" y="10" width="16" height="28" rx="8"/><path d="M16 32a16 16 0 0 0 32 0M32 48v8M24 56h16"/></svg>
      <span>Sprechen</span>
    </button>`;
  document.documentElement.append(diktatWirt);
  const knopf = ds.querySelector('button'), schrift = ds.querySelector('span');
  const BEREIT = 'Sprechen';
  let feld = null, stand = 'bereit';

  function textfeld(el) {
    return !!el && ((el.tagName === 'INPUT' && ['text', 'search', ''].includes(el.type)) || el.tagName === 'TEXTAREA');
  }
  function platzieren() {
    if (!feld) return;
    const r = feld.getBoundingClientRect();
    diktatWirt.style.top = (r.bottom + 10) + 'px';
    diktatWirt.style.right = Math.max(8, innerWidth - r.right) + 'px';
  }
  function setze(s, text) { stand = s; knopf.dataset.stand = s; schrift.textContent = text; }
  document.addEventListener('focusin', function (e) {
    const el = e.composedPath()[0];
    if (!textfeld(el)) return;
    feld = el;
    platzieren();
    diktatWirt.classList.add('an');
  }, true);
  document.addEventListener('focusout', function () {
    setTimeout(function () {
      if (stand === 'bereit' && !textfeld(document.activeElement)) diktatWirt.classList.remove('an');
    }, 200);
  }, true);
  addEventListener('resize', platzieren);
  addEventListener('scroll', platzieren, true);
  // Der Fokus soll im Feld bleiben, sonst klappt Spotify die Suche zu. Touch kommt als Maus an.
  knopf.addEventListener('mousedown', function (e) { e.preventDefault(); });
  knopf.addEventListener('pointerdown', function (e) { e.preventDefault(); });
  knopf.addEventListener('click', function () {
    if (stand === 'bereit') starten();
    else if (stand === 'hoert') stoppen();
  });
  function fehler(text) {
    setze('fehler', text);
    setTimeout(function () { setze('bereit', BEREIT); }, 8000);
  }
  function starten() {
    setze('denkt', 'Moment …');
    melde('/diktat/start').then(function (a) {
      if (!a.ok) return fehler(a.daten.fehler || 'Diktat geht gerade nicht.');
      setze('hoert', 'Hört zu …');
      // Der Dienst beendet die Aufnahme selbst nach einer Pause (oder auf Tipp) und antwortet
      // dann erst mit dem Text.
      melde('/diktat/ergebnis').then(function (e) {
        if (!e.ok) return fehler(e.daten.fehler || 'Die Spracherkennung ging nicht.');
        einsetzen(e.daten.text || '');
        setze('bereit', BEREIT);
      });
    });
  }
  function stoppen() {
    setze('denkt', 'Erkenne …');
    melde('/diktat/stopp');
  }
  // Aus /lage: Hat der Dienst die Aufnahme beendet, läuft die Erkennung.
  diktatLage = function (laeuft) { if (stand === 'hoert' && !laeuft) setze('denkt', 'Erkenne …'); };
  function einsetzen(text) {
    text = text.trim().replace(/[.!?]+$/, '');
    if (!text || !feld) return;
    feld.focus();
    // Über den Setter des Prototyps, damit React (Spotify) die Änderung als Eingabe bemerkt.
    const proto = feld.tagName === 'TEXTAREA' ? HTMLTextAreaElement.prototype : HTMLInputElement.prototype;
    Object.getOwnPropertyDescriptor(proto, 'value').set.call(feld, text);
    feld.dispatchEvent(new Event('input', { bubbles: true }));
  }
})();
