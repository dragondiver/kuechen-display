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
