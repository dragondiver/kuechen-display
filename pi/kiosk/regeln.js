// Regeln der Kiosk-Seite, die ohne Browser prüfbar sein sollen (pi/dienst/test_regeln.py, #50).
(function (aussen) {
  // Daten von Wetter und Terminen gelten eine Stunde als frisch (Festlegung 15.11.2026 in #15).
  const ALT_MS = 60 * 60 * 1000;
  // stand: Unix-Sekunden des letzten Abrufs, 0 oder fehlend = noch keiner. Genau eine Stunde ist
  // noch frisch. Ohne Stand gibt es nichts, was blass werden könnte.
  function istAlt(stand, jetztMs) {
    return !!stand && jetztMs - stand * 1000 > ALT_MS;
  }
  aussen.ALT_MS = ALT_MS;
  aussen.istAlt = istAlt;
})(typeof module !== 'undefined' ? module.exports : (window.Regeln = {}));
