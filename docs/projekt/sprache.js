/* Sprachwahl Deutsch/Englisch für die Projektseiten.
   Texte stehen doppelt im HTML (lang="de" / lang="en"), das CSS blendet die andere Sprache aus.
   Attribute (alt, aria-label) stehen als data-alt-de/-en bzw. data-aria-de/-en. */
(function () {
  "use strict";
  var root = document.documentElement, hoerer = [];
  function gemerkt() { try { var s = localStorage.getItem("kd-sprache"); return s === "de" || s === "en" ? s : null; } catch (e) { return null; } }
  function anfang() {
    var q = /[?&]lang=(de|en)\b/.exec(location.search);
    if (q) return q[1];
    var g = gemerkt(); if (g) return g;
    var l = (navigator.languages && navigator.languages[0]) || navigator.language || "en";
    return /^de\b/i.test(l) ? "de" : "en";
  }
  function anwenden(s) {
    root.setAttribute("data-sprache", s); root.lang = s;
    var t = root.getAttribute("data-titel-" + s); if (t) document.title = t;
    [].forEach.call(document.querySelectorAll("[data-alt-" + s + "]"), function (e) { e.alt = e.getAttribute("data-alt-" + s); });
    [].forEach.call(document.querySelectorAll("[data-aria-" + s + "]"), function (e) { e.setAttribute("aria-label", e.getAttribute("data-aria-" + s)); });
    [].forEach.call(document.querySelectorAll(".sprachwahl"), function (b) { b.setAttribute("aria-label", s === "de" ? "Switch to English" : "Auf Deutsch umschalten"); });
  }
  var jetzt = anfang();
  root.setAttribute("data-sprache", jetzt); root.lang = jetzt;
  window.kdSprache = {
    get: function () { return jetzt; },
    L: function (o) { return o == null ? "" : typeof o === "object" ? (o[jetzt] != null ? o[jetzt] : o.de) : o; },
    bei: function (f) { hoerer.push(f); },
    setze: function (s) {
      jetzt = s; anwenden(s);
      try { localStorage.setItem("kd-sprache", s); } catch (e) { /* ohne Speicher gilt die Wahl nur auf dieser Seite */ }
      hoerer.forEach(function (f) { f(s); });
    }
  };
  document.addEventListener("DOMContentLoaded", function () {
    anwenden(jetzt);
    [].forEach.call(document.querySelectorAll(".sprachwahl"), function (b) {
      b.addEventListener("click", function () { window.kdSprache.setze(jetzt === "de" ? "en" : "de"); });
    });
  });
})();
