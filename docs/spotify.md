# Spotify am Display

Stand 15.11.2026, zu #16 und #10. Auf dem Display läuft der Spotify-Web-Player
(<https://open.spotify.com/>) im Kiosk-Chromium. Die Musik spielt der Evoke, das Display ist nur
die Bedienung. So bleibt es bei der Festlegung vom 13.10.2026: Musik macht der Evoke, die kleinen
Lautsprecher im Gehäuse sind für die Sprache da. raspotify (das Display als eigener
Connect-Lautsprecher) ist zurückgestellt, Begründung in #16.

Eine Spotify-App für Linux auf ARM gibt es nicht, das offizielle Paket ist nur für x86_64.

## Voraussetzungen

- Chromium mit Widevine. Ohne Widevine (Paket `libwidevinecdm0`) spielt der Web-Player nichts ab.
  Auf dem Pi geprüft am 15.11.2026: Pi OS trixie, aarch64, `chromium` 156.0.8078.79,
  `libwidevinecdm0` 4.10.2662.3.
- Ein Spotify-Konto mit Premium, damit der Player andere Geräte steuern kann.
- Für die Anmeldung VNC vom Mac aus (TigerVNC, `kuechen-display.local`, Login florian), weil man
  dort eine Tastatur hat.

Prüfen, ob Widevine da ist:

```bash
ssh kuechen-display.local 'dpkg -l libwidevinecdm0 | tail -1'
```

## Player öffnen

Auf der Apps-Seite (vom Ruhebildschirm nach rechts wischen) auf die Kachel „Spotify“ tippen. Der
Player öffnet sich im selben Kiosk-Fenster. Die Kachel ist in `pi/kiosk/index.html` eine `.app`
mit `data-adresse`; ein Wischer über die Kachel öffnet sie nicht.

Vom Mac aus geht es auch, dann erscheint der Player als zweites Fenster über dem Kiosk:

```bash
ssh kuechen-display.local 'WAYLAND_DISPLAY=wayland-0 XDG_RUNTIME_DIR=/run/user/1000 nohup chromium --ozone-platform=wayland https://open.spotify.com/ >/dev/null 2>&1 &'
```

## Einmal anmelden

1. TigerVNC öffnen, `kuechen-display.local` verbinden.
2. Im Player oben rechts auf „Anmelden“ und mit dem Spotify-Konto anmelden.

Der Kiosk läuft mit dem normalen Chromium-Profil (`~/.config/chromium`), nicht inkognito. Die
Anmeldung bleibt deshalb gespeichert. Angemeldet ist immer genau ein Konto, seit 15.11.2026 das von
Florian.

## Auf dem Evoke spielen

Läuft auf dem Evoke schon Spotify vom selben Konto, zeigt der Player unten einen grünen Balken
„Wiedergabe über Evoke Play“ und steuert ihn direkt. Sonst unten rechts das Geräte-Symbol antippen
und „Evoke Play“ wählen. Wählt man „Dieser Webbrowser“, spielt das Display selbst.

## Zurück zum Ruhebildschirm

Im Kiosk gibt es keine Tabs und keinen Zurück-Knopf. Deshalb liegt oben links eine kleine Leiste
über der Seite, beim Spotify-Player über dem Logo:

| Symbol | Wirkung |
|---|---|
| Raster (vier Quadrate) | zurück auf die Apps-Seite (`http://localhost:8080/?seite=apps`) |
| Uhr | zurück auf Heute |

Die Musik läuft auf dem Evoke weiter, weil Spotify Connect sie dort hält. Kommt man zurück zu
Spotify, lädt der Player neu und zeigt sie wieder an.

Die Leiste ist eine kleine Chromium-Erweiterung in `pi/kiosk-rueckweg/` (`manifest.json`,
`rueckweg.js`). `pi/kiosk-start.sh` lädt sie mit `--load-extension`, `pi/push.sh` spiegelt sie nach
`~/kuechen-display/kiosk-rueckweg/`. Sie setzt sich auf jede `https`-Seite, die Ruhebildschirm-Seite
selbst (`http://localhost`) bleibt frei. YouTube und Browser bekommen sie also gleich mit, wenn ihre
Kacheln eine Adresse haben. Die Leiste steckt in einem Shadow-DOM, damit die CSS der Seite sie nicht
verändert.

Ein Fenster, das vom Mac aus geöffnet wurde, hat die Leiste auch. Dort führt sie aber in diesem
zweiten Fenster zum Ruhebildschirm. Schließen lässt es sich über VNC mit Strg+W oder durch einen
Neustart des Kiosks (`docs/kiosk-und-gesten.md`, „Kiosk sofort neu starten“). Die Anmeldung bleibt
dabei erhalten.

## Prüfen

Ein Bildschirmfoto vom Display, ohne VNC:

```bash
ssh kuechen-display.local 'WAYLAND_DISPLAY=wayland-0 XDG_RUNTIME_DIR=/run/user/1000 grim -o DSI-1 /tmp/kd.png' && scp kuechen-display.local:/tmp/kd.png .
```

Prüfen, ob der Kiosk die Erweiterung geladen hat:

```bash
ssh kuechen-display.local "tr '\\0' ' ' < /proc/\$(pgrep -o -x chromium)/cmdline | grep -o 'load-extension=[^ ]*'"
```

Probe vom 15.11.2026: Der Player lud, die Oberfläche passt ohne Querscrollen auf 1280 × 800.
Nach der Anmeldung zeigte er von selbst „Wiedergabe über Evoke Play“, und ein Tipp auf Play am
Display startete den Evoke. Die Runde Apps → Spotify → Raster bzw. Uhr → zurück hat Florian am
Display getippt, sie klappt. Die Anmeldung hat einen Neustart des Kiosk-Chromiums überstanden.

## Nicht geprüft

- Ob der Player auch auf dem Display selbst abspielt („Dieser Webbrowser“). Widevine ist zwar
  installiert, angehört hat es niemand.
- Ob die Anmeldung einen Neustart des ganzen Pi übersteht (der Neustart des Browsers ging).
- Wie gut sich der Player mit dem Finger bedienen lässt. Er ist für die Maus gebaut, die
  Schaltflächen sind klein.
- Andere Konten im Haushalt. Spielt Karin vom eigenen Konto auf dem Evoke, sieht der Player mit
  Florians Konto das vermutlich nicht.
