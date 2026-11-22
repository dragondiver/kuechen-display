// Regeln der Kiosk-Seite, die ohne Browser prüfbar sein sollen (pi/dienst/test_regeln.py, #50).
(function (aussen) {
  // Daten von Wetter und Terminen gelten eine Stunde als frisch (Festlegung 15.11.2026 in #15).
  const ALT_MS = 60 * 60 * 1000;
  // stand: Unix-Sekunden des letzten Abrufs, 0 oder fehlend = noch keiner. Genau eine Stunde ist
  // noch frisch. Ohne Stand gibt es nichts, was blass werden könnte.
  function istAlt(stand, jetztMs) {
    return !!stand && jetztMs - stand * 1000 > ALT_MS;
  }
  // Langes Drücken auf die Terminkarte sperrt die Termine (#82). Etwa 0,8 s, und der Finger bleibt
  // dabei fast still: Ein Wischen, Rollen oder Tippen auf „Morgen ›“ löst nichts aus.
  const LANG_MS = 800;
  const WACKEL_PX = 12;
  // dauerMs: wie lange der Finger liegt; wegPx: wie weit er seit dem Aufsetzen gewandert ist.
  function langerDruck(dauerMs, wegPx) {
    return dauerMs >= LANG_MS && wegPx <= WACKEL_PX;
  }
  // Lautstärke-Schieber (#103): Solange man zieht, etwas senden will und kurz danach gilt der eigene Wert,
  // sonst spränge der Griff mit einem Stand zurück, der vor der letzten Änderung abgeschickt wurde.
  const LAUTSTAERKE_SCHUTZ_MS = 1500;
  function standUebernehmen(eigenAktiv, jetztMs, schutzBisMs) {
    return !eigenAktiv && jetztMs >= schutzBisMs;
  }
  aussen.LAUTSTAERKE_SCHUTZ_MS = LAUTSTAERKE_SCHUTZ_MS;
  aussen.standUebernehmen = standUebernehmen;
  aussen.ALT_MS = ALT_MS;
  aussen.istAlt = istAlt;
  aussen.LANG_MS = LANG_MS;
  aussen.WACKEL_PX = WACKEL_PX;
  aussen.langerDruck = langerDruck;
})(typeof module !== 'undefined' ? module.exports : (window.Regeln = {}));
