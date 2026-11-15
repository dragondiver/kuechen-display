// Fester Zoom pro Seite (kuechen-display#10, Festlegung 15.11.2026: Spotify 125 %).
// Bei 125 % sind Schrift und Knöpfe für den Finger groß genug, der Aufbau des Players bleibt.
// Bei 150 % rutschte die Abspielleiste aus dem 1280 × 800-Bild.
// Chromium speichert den Wert zusätzlich im Profil (per Host); hier steht er, damit er im Repo
// nachvollziehbar ist und nach einem neuen Profil wiederkommt.
const ZOOM = { 'open.spotify.com': 1.25 };

chrome.tabs.onUpdated.addListener(function (tabId, info, tab) {
  if (info.status !== 'complete' || !tab.url) return;
  let host;
  try { host = new URL(tab.url).hostname; } catch (e) { return; }
  if (!(host in ZOOM)) return;
  chrome.tabs.getZoom(tabId, function (jetzt) {
    if (Math.abs(jetzt - ZOOM[host]) > 0.01) chrome.tabs.setZoom(tabId, ZOOM[host]);
  });
});

// Brücke zum Küchen-Dienst für rueckweg.js (#70). Die Leiste läuft in der https-Seite der App und
// darf http://localhost nicht selbst abfragen; der Hintergrund darf es über host_permissions.
const DIENST = 'http://localhost:8080';
const ERLAUBT = ['/tipp', '/quittung'];
chrome.runtime.onMessage.addListener(function (nachricht, absender, antwort) {
  if (absender.id !== chrome.runtime.id) return;
  if (nachricht.art === 'lage') {
    fetch(DIENST + '/lage', { cache: 'no-store' })
      .then(function (r) { return r.ok ? r.json() : null; })
      .then(antwort, function () { antwort(null); });
    return true;
  }
  if (nachricht.art === 'melde' && ERLAUBT.includes(nachricht.pfad)) {
    fetch(DIENST + nachricht.pfad, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(nachricht.daten || {}),
    }).then(function (r) { antwort(r.ok); }, function () { antwort(false); });
    return true;
  }
});
