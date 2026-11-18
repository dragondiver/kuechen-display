from wach import MIN_FLAECHE, VIDEO_FRIST_S, Wach, video_spielt


def film(**aenderung):
    v = {"spielt": True, "bild": True, "schleife": False, "flaeche": 0.9}
    v.update(aenderung)
    return v


def test_grosses_laufendes_video_zaehlt():
    assert video_spielt([film()]) == (True, [])


def test_keine_videos_zaehlen_nicht():
    assert video_spielt([]) == (False, [])


def test_pausiert_zaehlt_nicht():
    assert video_spielt([film(spielt=False)]) == (False, [])


def test_audio_ohne_bild_zaehlt_nicht():
    """Spotify spielt im Browser über ein Element ohne Bild: Musik allein hält nicht wach."""
    assert video_spielt([film(bild=False)]) == (False, [])


def test_schleife_zaehlt_nicht():
    """Spotifys Canvas: kurze stumme Schleife neben dem Titel."""
    assert video_spielt([film(schleife=True)]) == (False, [])


def test_vorschau_in_kachelgroesse_zaehlt_nicht():
    assert video_spielt([film(flaeche=0.05)]) == (False, [])


def test_grenze_der_flaeche_gilt_einschliesslich():
    assert video_spielt([film(flaeche=MIN_FLAECHE)])[0] is True
    assert video_spielt([film(flaeche=MIN_FLAECHE - 0.01)])[0] is False


def test_ein_film_unter_mehreren_genuegt():
    assert video_spielt([film(flaeche=0.02), film(spielt=False), film()])[0] is True


def test_unbrauchbare_eintraege_zaehlen_nicht_und_werden_gemeldet():
    spielt, probleme = video_spielt(
        [{"spielt": "ja"}, "kaputt", film(flaeche=True), film(flaeche=None)]
    )
    assert spielt is False
    assert len(probleme) == 4


def test_ein_guter_eintrag_neben_einem_kaputten_zaehlt():
    spielt, probleme = video_spielt(["kaputt", film()])
    assert spielt is True
    assert len(probleme) == 1


def test_keine_liste_wird_gemeldet():
    spielt, probleme = video_spielt({"spielt": True})
    assert spielt is False
    assert probleme


def test_video_haelt_bis_zur_frist():
    w = Wach()
    w.video_melden([film()], 100.0)
    assert w.video_laeuft(100.0 + VIDEO_FRIST_S - 0.1)
    assert not w.video_laeuft(100.0 + VIDEO_FRIST_S)


def test_meldung_ohne_video_beendet_den_halt_sofort():
    w = Wach()
    w.video_melden([film()], 100.0)
    w.video_melden([film(spielt=False)], 105.0)
    assert not w.video_laeuft(105.0)


def test_kaputte_meldung_verlaengert_den_halt_nicht():
    w = Wach()
    w.video_melden([film()], 100.0)
    assert w.video_melden("quatsch", 105.0)
    assert not w.video_laeuft(105.0)


def test_ohne_meldung_haelt_nichts():
    assert not Wach().video_laeuft(1e9)


def test_elektra_haelt_in_jedem_zustand_ausser_aus():
    w = Wach()
    for zustand in ("zuhoeren", "nachdenken", "sprechen"):
        assert w.gruende(zustand, 0.0) == [f"elektra ({zustand})"]
    assert w.gruende("aus", 0.0) == []


def test_gruende_nennen_beides():
    w = Wach()
    w.video_melden([film()], 0.0)
    assert w.gruende("sprechen", 1.0) == ["elektra (sprechen)", "video"]


def test_nur_musik_haelt_nicht_wach():
    """Spotify allein: Elektra aus, Video-Meldung ohne Bild."""
    w = Wach()
    w.video_melden([film(bild=False)], 0.0)
    assert w.gruende("aus", 1.0) == []


# --- Weckwort (#89) ---------------------------------------------------------------------
def test_weckwort_haelt_wach_bis_der_waechter_gefragt_hat():
    from wach import WORT_HALT_S

    w = Wach()
    w.wort_gehoert(100.0)
    assert w.gruende("aus", 100.0 + WORT_HALT_S - 0.1) == ["weckwort"]
    assert w.gruende("aus", 100.0 + WORT_HALT_S) == []


def test_weckwort_haelt_laenger_als_der_fragetakt_des_waechters():
    from wach import WORT_HALT_S

    assert WORT_HALT_S > 5.0  # WACH_TAKT_S in pi/schlafen/schlafwaechter.py


def test_ohne_weckwort_kein_grund():
    assert Wach().gruende("aus", 10.0) == []
