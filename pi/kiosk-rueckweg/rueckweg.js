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
  const APPS = { spotify: 'https://open.spotify.com/', rezepte: 'https://mise-en-place.fhuber.com/de/kd/recipes' };  // wie data-app in pi/kiosk/index.html
  // Koch-Ansicht von mise-en-place (kuechen-display#75): /<locale>/kd/recipes/<id>, z. B. /de/kd/recipes/42.
  // Sie hört auf keydown an window (ArrowRight = nächster Schritt, ArrowLeft = vorheriger).
  const KOCH_ANSICHT = { host: 'mise-en-place.fhuber.com', pfad: /^\/[a-z]{2}(?:-[A-Za-z]+)?\/kd\/recipes\/[^/]+\/?$/ };
  const SCHRITT_TASTE = { vor: 'ArrowRight', zurueck: 'ArrowLeft' };  // Werte laut rundfunk-Werkzeug rezeptschritt
  // Rezeptauswahl (mise-en-place#223): /<locale>/kd/recipes ohne id. Sie blättert ihre Liste mit ArrowDown/ArrowUp um eine Bildschirmhöhe.
  const AUSWAHL_PFAD = /^\/[a-z]{2}(?:-[A-Za-z]+)?\/kd\/recipes\/?$/;
  const AUSWAHL_TASTE = { vor: 'ArrowDown', zurueck: 'ArrowUp' };
  // Übersicht eines Rezepts: /<locale>/kd/recipes/<id>/overview. „vor“ startet das Kochen (ArrowRight), „zurück“ gibt es dort nicht.
  const UEBERSICHT_PFAD = /^\/[a-z]{2}(?:-[A-Za-z]+)?\/kd\/recipes\/[^/]+\/overview\/?$/;
  const UEBERSICHT_TASTE = { vor: 'ArrowRight' };
  function schrittTasten() {
    if (location.host !== KOCH_ANSICHT.host) return null;
    if (KOCH_ANSICHT.pfad.test(location.pathname)) return SCHRITT_TASTE;
    if (AUSWAHL_PFAD.test(location.pathname)) return AUSWAHL_TASTE;
    if (UEBERSICHT_PFAD.test(location.pathname)) return UEBERSICHT_TASTE;
    return null;
  }
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
      quittiere(b.id, null, function () {
        const u = new URL(ziel);
        if (u.host !== location.host) location.href = ziel;
        // Nur für Rezepte: Ist schon eine Seite von mise-en-place offen (Koch-Ansicht, Übersicht), führt
        // „öffne Rezepte“ zur Auswahl. Bei Spotify bleibt es dabei, nichts zu tun (sonst ginge eine
        // offene Suche verloren).
        else if (arg.name === 'rezepte' && location.pathname.replace(/\/$/, '') !== u.pathname.replace(/\/$/, '')) location.href = ziel;
      });
    } else if (b.name === 'rezeptschritt' && schrittTasten()) {
      const taste = schrittTasten()[arg.richtung];
      if (!taste) quittiere(b.id, SCHRITT_TASTE[arg.richtung] ? 'Hier geht es nur vor.' : 'Unbekannte Richtung: ' + arg.richtung);
      else quittiere(b.id, null, function () { window.dispatchEvent(new KeyboardEvent('keydown', { key: taste, bubbles: true })); });
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

  // --- Läuft ein Video? (#48) -----------------------------------------------------------------
  // Das Display geht nach Ruhe aus, außer ein Video läuft. Die Leiste meldet dem Küchen-Dienst alle
  // 5 s, was die <video>-Elemente der Seite tun; ob es ein „laufendes Video“ ist, entscheidet der
  // Dienst (pi/dienst/wach.py). Gemeldet wird nur, solange eins spielt, und einmal danach, damit der
  // Dienst nicht bis zur Frist wartet. Videos in eingebetteten Frames und in Shadow-DOM sieht das nicht.
  let videoGemeldet = false, videoWarnung = false;
  function videoFakten() {
    const fenster = innerWidth * innerHeight;
    return Array.from(document.querySelectorAll('video')).map(function (v) {
      const r = v.getBoundingClientRect();
      const breite = Math.max(0, Math.min(r.right, innerWidth) - Math.max(r.left, 0));
      const hoehe = Math.max(0, Math.min(r.bottom, innerHeight) - Math.max(r.top, 0));
      return {
        spielt: !v.paused && !v.ended && v.readyState >= 3,
        bild: v.videoWidth > 0 && v.videoHeight > 0,
        schleife: v.loop,
        flaeche: fenster > 0 ? (breite * hoehe) / fenster : 0,
      };
    });
  }
  function meldeVideo() {
    const fakten = videoFakten();
    const spielt = fakten.some(function (f) { return f.spielt; });
    if (!spielt && !videoGemeldet) return;
    videoGemeldet = spielt;
    melde('/video', { videos: fakten }).then(function (a) {
      if (!a.ok && !videoWarnung) {
        videoWarnung = true;
        console.warn('Küchen-Display: Video-Meldung ans Schlafen ging nicht:', a.daten.fehler || a);
      }
    });
  }
  setInterval(meldeVideo, 5000);

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
  // Der eigene Mikrofon-Knopf der Seite für das fokussierte Feld (data-kd-diktat, nur auf mise-en-place).
  function seitenKnopf() {
    if (location.host !== KOCH_ANSICHT.host || !feld || !feld.id) return null;
    return document.querySelector('[data-kd-diktat="' + CSS.escape(feld.id) + '"]');
  }
  function platzieren() {
    if (!feld) return;
    const sk = seitenKnopf();
    if (sk) {
      // In die Suchzeile, links neben den Knopf der Seite und senkrecht mittig zu ihm: kein Treffer wird verdeckt.
      const k = sk.getBoundingClientRect();
      diktatWirt.style.top = (k.top + k.height / 2) + 'px';
      diktatWirt.style.right = (innerWidth - k.left + 12) + 'px';
      diktatWirt.style.transform = 'translateY(-50%)';
      return;
    }
    const r = feld.getBoundingClientRect();
    diktatWirt.style.top = (r.bottom + 10) + 'px';
    diktatWirt.style.right = Math.max(8, innerWidth - r.right) + 'px';
    diktatWirt.style.transform = '';
  }
  // Hat die Seite einen eigenen Knopf, zeigt die Erweiterung ihren nur als Anzeige (Moment, Hört zu,
  // Erkenne, Fehler), im Stand „bereit“ nicht. Sonst (Spotify) bleibt das Einblenden bei focusin/focusout.
  function aktualisieren() {
    if (!seitenKnopf()) return;
    diktatWirt.classList.toggle('an', stand !== 'bereit');
    platzieren();
  }
  function setze(s, text) { stand = s; knopf.dataset.stand = s; schrift.textContent = text; aktualisieren(); }
  document.addEventListener('focusin', function (e) {
    const el = e.composedPath()[0];
    if (!textfeld(el)) return;
    feld = el;
    platzieren();
    diktatWirt.classList.add('an');
    aktualisieren();
  }, true);
  document.addEventListener('focusout', function () {
    setTimeout(function () {
      if (stand === 'bereit' && !textfeld(document.activeElement)) diktatWirt.classList.remove('an');
      aktualisieren();
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
  // Seiten mit eigenem Mikrofon-Knopf markieren ihn mit data-kd-diktat="<id des Textfelds>". Ein Tipp
  // darauf startet das Diktat sofort, ohne dass man den eingeblendeten Knopf „Sprechen“ drücken muss;
  // der zweite Tipp beendet es. Gilt nur auf der eigenen Seite (mise-en-place, KOCH_ANSICHT.host) und
  // nur für echte Tipps: Sonst könnte jede Seite per el.click() das Mikrofon starten und mitlesen.
  function diktatKnopfDerSeite(e) {
    if (!e.isTrusted || location.host !== KOCH_ANSICHT.host) return null;
    return e.composedPath().find(function (el) {
      return el.nodeType === 1 && el.hasAttribute('data-kd-diktat');
    });
  }
  // Der Fokus soll im Feld bleiben (sonst blendet focusout den Knopf „Sprechen“ aus, bevor der Klick ankommt).
  document.addEventListener('mousedown', function (e) { if (diktatKnopfDerSeite(e)) e.preventDefault(); }, true);
  document.addEventListener('click', function (e) {
    const el = diktatKnopfDerSeite(e);
    if (!el) return;
    if (stand !== 'bereit' && stand !== 'hoert') return;  // denkt, fehler: nichts tun
    try {
      const ziel = document.getElementById(el.getAttribute('data-kd-diktat'));
      if (!textfeld(ziel)) return;  // dann fokussiert die Seite selbst
      ziel.focus();
      feld = ziel;
      aktualisieren();
      if (stand === 'bereit') starten();
      else stoppen();
    } catch (err) { console.warn('Küchen-Display: Diktat-Knopf der Seite:', err); }
  }, true);
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
      hoertSeit = Date.now();
      melde('/diktat/ergebnis', { id: a.daten.id }).then(function (e) {
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
  // Eine /lage-Antwort, die vor dem Start abgeschickt wurde, sagt noch „läuft nicht“: erst nach
  // anderthalb Sekunden glauben.
  let hoertSeit = 0;
  diktatLage = function (laeuft) {
    if (stand === 'hoert' && !laeuft && Date.now() - hoertSeit > 1500) setze('denkt', 'Erkenne …');
  };
  function einsetzen(text) {
    text = text.trim().replace(/[.!?]+$/, '');
    if (!text) return;
    if (!feld || !feld.isConnected) {
      // Spotify hat die Suche inzwischen zugemacht: über die Such-Adresse statt ins Leere.
      if (location.host === 'open.spotify.com') location.href = 'https://open.spotify.com/search/' + encodeURIComponent(text);
      return;
    }
    feld.focus();
    // Über den Setter des Prototyps, damit React (Spotify) die Änderung als Eingabe bemerkt.
    const proto = feld.tagName === 'TEXTAREA' ? HTMLTextAreaElement.prototype : HTMLInputElement.prototype;
    Object.getOwnPropertyDescriptor(proto, 'value').set.call(feld, text);
    feld.dispatchEvent(new Event('input', { bubbles: true }));
  }
})();
