from geste import PAUSE_S, Beobachtung, Gestenerkenner


def folge(erkenner, punkte, geste="", sicherheit=0.0, takt=1 / 15, start=0.0):
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
    # 0,4 Bildbreite in 2 s: Hand wird beim Kochen bewegt, nicht gewischt.
    assert folge(Gestenerkenner(), quer(0.3, 0.7, 30)) == []


def test_schraege_bewegung_ist_kein_wischen():
    punkte = [(0.3 + 0.08 * i, 0.2 + 0.1 * i) for i in range(6)]
    assert folge(Gestenerkenner(), punkte) == []


def test_flache_hand_ruhig_ist_stopp():
    punkte = [(0.5, 0.5)] * 12
    assert folge(Gestenerkenner(), punkte, "Open_Palm", 0.9) == [{"art": "stopp"}]


def test_flache_hand_zu_kurz_ist_kein_stopp():
    assert folge(Gestenerkenner(), [(0.5, 0.5)] * 5, "Open_Palm", 0.9) == []


def test_faust_ist_kein_stopp():
    assert folge(Gestenerkenner(), [(0.5, 0.5)] * 12, "Closed_Fist", 0.9) == []


def test_unsichere_flache_hand_ist_kein_stopp():
    assert folge(Gestenerkenner(), [(0.5, 0.5)] * 12, "Open_Palm", 0.4) == []


def test_zurueckfuehren_der_hand_blaettert_nicht_zurueck():
    erkenner = Gestenerkenner()
    hin = folge(erkenner, quer(0.3, 0.7, 6))
    zurueck = folge(erkenner, quer(0.7, 0.3, 6), start=6 / 15)
    assert hin == [{"art": "wischen", "richtung": "links"}]
    assert zurueck == []


def test_nach_der_pause_wieder_bereit():
    erkenner = Gestenerkenner()
    folge(erkenner, quer(0.3, 0.7, 6))
    spaeter = folge(erkenner, quer(0.3, 0.7, 6), start=6 / 15 + PAUSE_S)
    assert spaeter == [{"art": "wischen", "richtung": "links"}]


def test_hand_lange_weg_setzt_zurueck():
    erkenner = Gestenerkenner()
    folge(erkenner, quer(0.3, 0.45, 3))
    erkenner.keine_hand(0.5)
    # Ohne die ersten Punkte reicht der Rest nicht für ein Wischen.
    assert folge(erkenner, quer(0.5, 0.7, 3), start=0.6) == []


def test_kurzer_aussetzer_beim_schnellen_wischen_wird_ueberbrueckt():
    erkenner = Gestenerkenner()
    folge(erkenner, quer(0.25, 0.4, 3))
    erkenner.keine_hand(0.2)  # zwei Bilder verwischt
    assert folge(erkenner, quer(0.55, 0.7, 3), start=0.27) == [
        {"art": "wischen", "richtung": "links"}
    ]
