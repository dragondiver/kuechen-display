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

Solange es die Kachel auf der Apps-Seite (#10) noch nicht gibt, öffnet man den Player vom Mac aus.
Er erscheint als neues Fenster im laufenden Kiosk-Chromium:

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

Im Kiosk gibt es keine Tabs und keinen Zurück-Knopf. Das Player-Fenster schließt man über VNC mit
Strg+W. Oder man startet den Kiosk neu (`docs/kiosk-und-gesten.md`, „Kiosk sofort neu starten“).
Die Anmeldung bleibt dabei erhalten.

## Prüfen

Ein Bildschirmfoto vom Display, ohne VNC:

```bash
ssh kuechen-display.local 'WAYLAND_DISPLAY=wayland-0 XDG_RUNTIME_DIR=/run/user/1000 grim -o DSI-1 /tmp/kd.png' && scp kuechen-display.local:/tmp/kd.png .
```

Probe vom 15.11.2026: Der Player lud, die Oberfläche passt ohne Querscrollen auf 1280 × 800.
Nach der Anmeldung zeigte er von selbst „Wiedergabe über Evoke Play“, und ein Tipp auf Play am
Display startete den Evoke.

## Nicht geprüft

- Ob der Player auch auf dem Display selbst abspielt („Dieser Webbrowser“). Widevine ist zwar
  installiert, angehört hat es niemand.
- Ob die Anmeldung einen Neustart des Pi übersteht.
- Wie gut sich der Player mit dem Finger bedienen lässt. Er ist für die Maus gebaut, die
  Schaltflächen sind klein.
- Andere Konten im Haushalt. Spielt Karin vom eigenen Konto auf dem Evoke, sieht der Player mit
  Florians Konto das vermutlich nicht.
