from geste import PAUSE_S, Beobachtung, Gestenerkenner, flache_hand, gestenhand


def folge(erkenner, punkte, geste="", sicherheit=0.0, takt=1 / 30, start=0.0):
    ereignisse = []
    for i, (x, y) in enumerate(punkte):
        e = erkenner.beobachte(Beobachtung(start + i * takt, x, y, geste, sicherheit))
        if e:
            ereignisse.append(e)
    return ereignisse


def quer(von, bis, schritte, y=0.5):
    return [(von + (bis - von) * i / (schritte - 1), y) for i in range(schritte)]


def test_hand_nach_links_des_menschen_ist_wischen_links():
    # Im Kamerabild läuft sie dabei nach rechts.
    assert folge(Gestenerkenner(), quer(0.3, 0.7, 6)) == [
        {"art": "wischen", "richtung": "links"}
    ]


def test_hand_nach_rechts_ist_wischen_rechts():
    assert folge(Gestenerkenner(), quer(0.7, 0.3, 6)) == [
        {"art": "wischen", "richtung": "rechts"}
    ]


def test_langsames_schieben_ist_kein_wischen():
    # 0,4 Bildbreite in 1 s: Hand wird beim Kochen bewegt, nicht gewischt.
    assert folge(Gestenerkenner(), quer(0.3, 0.7, 30)) == []


def test_schraege_bewegung_ist_kein_wischen():
    punkte = [(0.3 + 0.08 * i, 0.2 + 0.1 * i) for i in range(6)]
    assert folge(Gestenerkenner(), punkte) == []


def test_flache_hand_ruhig_ist_stopp():
    punkte = [(0.5, 0.5)] * 24
    assert folge(Gestenerkenner(), punkte, "Open_Palm", 0.9) == [{"art": "stopp"}]


def test_flache_hand_zu_kurz_ist_kein_stopp():
    assert folge(Gestenerkenner(), [(0.5, 0.5)] * 5, "Open_Palm", 0.9) == []


def test_faust_ist_kein_stopp():
    assert folge(Gestenerkenner(), [(0.5, 0.5)] * 24, "Closed_Fist", 0.9) == []


def test_unsichere_flache_hand_ist_kein_stopp():
    assert folge(Gestenerkenner(), [(0.5, 0.5)] * 24, "Open_Palm", 0.4) == []


def test_zurueckfuehren_der_hand_blaettert_nicht_zurueck():
    erkenner = Gestenerkenner()
    hin = folge(erkenner, quer(0.3, 0.7, 6))
    zurueck = folge(erkenner, quer(0.7, 0.3, 6), start=6 / 30)
    assert hin == [{"art": "wischen", "richtung": "links"}]
    assert zurueck == []


def test_nach_der_pause_wieder_bereit():
    erkenner = Gestenerkenner()
    folge(erkenner, quer(0.3, 0.7, 6))
    spaeter = folge(erkenner, quer(0.3, 0.7, 6), start=6 / 30 + PAUSE_S)
    assert spaeter == [{"art": "wischen", "richtung": "links"}]


def test_hand_lange_weg_setzt_zurueck():
    erkenner = Gestenerkenner()
    folge(erkenner, quer(0.3, 0.45, 3))
    erkenner.keine_hand(0.45)
    # Ohne die ersten Punkte reicht der Rest nicht für ein Wischen.
    assert folge(erkenner, quer(0.5, 0.7, 3), start=0.6) == []


def test_kurzer_aussetzer_beim_schnellen_wischen_wird_ueberbrueckt():
    erkenner = Gestenerkenner()
    folge(erkenner, quer(0.25, 0.4, 3))
    erkenner.keine_hand(0.12)  # zwei Bilder verwischt
    assert folge(erkenner, quer(0.55, 0.7, 3), start=0.15) == [
        {"art": "wischen", "richtung": "links"}
    ]


def test_ausholen_vor_dem_wischen_blaettert_nicht():
    # Tischtest 8.11.2026: Vor dem Wischen nach links führt die Hand gemächlich nach rechts,
    # 0,76 → 0,45 in 0,8 s. Erst danach kommt der eigentliche Wischer, 0,17 → 0,59 in 0,23 s.
    erkenner = Gestenerkenner()
    ausholen = folge(erkenner, quer(0.76, 0.45, 25), takt=1 / 30)
    # Dazwischen ist die Hand am Bildrand kurz weg (im Mitschnitt 0,4–0,9 s).
    wischen = folge(erkenner, quer(0.17, 0.59, 8), takt=1 / 30, start=1.3)
    assert ausholen == []
    assert wischen == [{"art": "wischen", "richtung": "links"}]


def test_flache_hand_mit_messwerten_vom_tischtest_ist_stopp():
    # Tischtest 8.11.2026: Hand oben im Bild, MediaPipe meldet Open_Palm mit 0,50–0,64.
    erkenner = Gestenerkenner()
    werte = [0.51, 0.53, 0.54, 0.6, 0.62, 0.62, 0.6, 0.61, 0.64, 0.6, 0.57, 0.59]
    ereignisse = []
    for i in range(24):
        e = erkenner.beobachte(
            Beobachtung(i / 30, 0.67, 0.11, "Open_Palm", werte[i % len(werte)])
        )
        if e:
            ereignisse.append(e)
    assert ereignisse == [{"art": "stopp"}]


class P:
    def __init__(self, x, y):
        self.x, self.y = x, y


def test_erhobene_hand_zaehlt_nicht_die_auf_dem_tisch():
    tisch = [P(0.73, 0.91)] * 21
    erhoben = [P(0.45, 0.5)] * 21
    assert gestenhand([tisch, erhoben]) == 1
    assert gestenhand([erhoben, tisch]) == 0


def hand(spitze_zu_ansatz):
    """21 Punkte: Handgelenk unten, vier Finger senkrecht nach oben."""
    punkte = [P(0.5, 0.8)] + [P(0.5, 0.8)] * 20
    for n, (ansatz, spitze) in enumerate(((5, 8), (9, 12), (13, 16), (17, 20))):
        x = 0.47 + 0.02 * n
        punkte[ansatz] = P(x, 0.8 - 0.1)
        punkte[spitze] = P(x, 0.8 - 0.1 * spitze_zu_ansatz)
    return punkte


def test_flache_hand_aus_punkten_mit_messwerten():
    # Tischtest 8.11.2026: flache Hand ab 1,57, normal bewegte Hand im Median 1,36,
    # Faust 0,57, halb offen 0,17.
    assert flache_hand(hand(1.57))
    assert flache_hand(hand(1.86))
    assert not flache_hand(hand(1.36))
    assert not flache_hand(hand(0.57))
    assert not flache_hand(hand(0.17))


def test_ein_gekruemmter_finger_reicht_fuer_nicht_flach():
    punkte = hand(1.8)
    punkte[16] = P(punkte[13].x, 0.8 - 0.1 * 0.6)
    assert not flache_hand(punkte)


def test_flache_hand_auf_dem_tisch_ist_kein_stopp():
    # Tischtest 8.11.2026: Die liegende Hand löste alle 1,2 s einen Stopp aus. Ihre Finger
    # zeigen im Bild nach unten (Richtung -0,8), bei der erhobenen Hand nach oben (0,95–1,0).
    punkte = hand(1.8)
    punkte = [
        P(p.x, 1.6 - p.y) for p in punkte
    ]  # an der Waagrechten gespiegelt: Finger nach unten
    assert not flache_hand(punkte)
