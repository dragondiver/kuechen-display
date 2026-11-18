"""Kein Netz (#50): Hat der Pi eine Standardroute?

Der Dienst kann nicht wissen, ob WLAN da ist, wohl aber, ob das System noch einen Weg ins Netz
kennt: Fällt das WLAN aus, nimmt der Netzwerkdienst die Standardroute aus /proc/net/route. Home
Assistant und die Bridge liegen beide auf raspi-agent, ihr gemeinsamer Ausfall würde auch einen
abgeschalteten raspi-agent als „Kein Netz“ zeigen. Die Route sagt das genauer und braucht keinen Abruf.
"""

RTF_UP = 0x1
RTF_GATEWAY = 0x2


def hat_route(inhalt: str) -> bool:
    """Steht in /proc/net/route eine Standardroute (Ziel 0.0.0.0) über ein Gateway?"""
    for zeile in inhalt.splitlines()[1:]:
        felder = zeile.split()
        if len(felder) < 4:
            continue
        try:
            ziel, flags = int(felder[1], 16), int(felder[3], 16)
        except ValueError:
            continue
        if ziel == 0 and flags & RTF_UP and flags & RTF_GATEWAY:
            return True
    return False


class Netz:
    """Meldet nur Änderungen. Erst der zweite Befund in Folge kippt den Zustand, damit ein
    kurzes Neuverbinden des WLAN (Roaming) keine Zeile aufblitzen lässt."""

    def __init__(self) -> None:
        self.da = True
        self.gemeldet = False  # ob die Seite schon einmal einen Stand bekam
        self._abweichung = 0

    def pruefen(self, route: bool | None) -> bool | None:
        """route: Befund dieser Runde, None wenn die Datei nicht lesbar war (dann gilt: Netz da,
        lieber keine falsche Zeile). Gibt den neuen Zustand zurück, wenn er gemeldet werden soll."""
        befund = True if route is None else route
        if befund == self.da:
            self._abweichung = 0
        else:
            self._abweichung += 1
            if self._abweichung >= 2:
                self.da, self._abweichung = befund, 0
                self.gemeldet = True
                return self.da
        return None
