import logging
from types import SimpleNamespace

from ruhe import BTN_TOUCH, EV_KEY, Konfig, WeckTipp
from schlafwaechter import Anzeige, Touch, Waechter, wach_fragen


# --- Anzeige ---------------------------------------------------------------------------
class Lauf:
    """Ersetzt subprocess.run für wlopm."""

    def __init__(self, code=0, fehler=None):
        self.aufrufe = []
        self.code = code
        self.fehler = fehler

    def __call__(self, befehl, **kw):
        self.aufrufe.append(befehl)
        if self.fehler:
            raise self.fehler
        return SimpleNamespace(
            returncode=self.code, stderr="kaputt" if self.code else ""
        )


def sysfs(tmp_path, hell=180, maximal=255):
    d = tmp_path / "backlight"
    d.mkdir()
    (d / "brightness").write_text(f"{hell}\n")
    (d / "max_brightness").write_text(f"{maximal}\n")
    return d


def anzeige(tmp_path, aus_weg="beides", lauf=None, hell=180):
    d = sysfs(tmp_path, hell)
    lauf = lauf or Lauf()
    return (
        Anzeige(
            aus_weg, backlight=d, zustand=tmp_path / "lauf" / "helligkeit", lauf=lauf
        ),
        d,
        lauf,
    )


def helligkeit(d):
    return int((d / "brightness").read_text())


def test_aus_merkt_helligkeit_dunkelt_und_schaltet_den_ausgang_ab(tmp_path):
    a, d, lauf = anzeige(tmp_path, hell=180)
    assert a.aus() is True
    assert helligkeit(d) == 0
    assert a.zustand.read_text().strip() == "180"
    assert lauf.aufrufe == [["wlopm", "--off", "DSI-1"]]


def test_an_gibt_den_vorigen_wert_zurueck_nicht_fest_255(tmp_path):
    a, d, lauf = anzeige(tmp_path, hell=90)
    a.aus()
    assert a.an() is True
    assert helligkeit(d) == 90
    assert not a.zustand.exists()
    assert lauf.aufrufe[-1] == ["wlopm", "--on", "DSI-1"]


def test_neu_gestarteter_waechter_gibt_die_gemerkte_helligkeit_zurueck(tmp_path):
    a, d, _ = anzeige(tmp_path, hell=120)
    a.aus()
    neu = Anzeige(
        "beides", backlight=d, zustand=a.zustand, lauf=Lauf()
    )  # Absturz, Neustart
    assert neu.an() is True
    assert helligkeit(d) == 120


def test_zweimal_aus_ueberschreibt_den_gemerkten_wert_nicht_mit_null(tmp_path):
    a, d, _ = anzeige(tmp_path, hell=150)
    a.aus()
    a.aus()
    assert a.zustand.read_text().strip() == "150"
    a.an()
    assert helligkeit(d) == 150


def test_dunkel_und_nichts_gemerkt_schaltet_auf_den_hoechstwert_und_warnt(
    tmp_path, caplog
):
    a, d, _ = anzeige(tmp_path, hell=0)
    with caplog.at_level(logging.WARNING):
        assert a.an() is True
    assert helligkeit(d) == 255
    assert "nichts gemerkt" in caplog.text


def test_an_laesst_eine_helle_beleuchtung_in_ruhe(tmp_path):
    a, d, _ = anzeige(tmp_path, hell=77)
    assert a.an() is True
    assert helligkeit(d) == 77


def test_nur_backlight_ruft_wlopm_nicht_auf(tmp_path):
    a, _, lauf = anzeige(tmp_path, aus_weg="backlight")
    a.aus()
    a.an()
    assert lauf.aufrufe == []


def test_nur_ausgang_laesst_die_beleuchtung_stehen(tmp_path):
    a, d, lauf = anzeige(tmp_path, aus_weg="ausgang", hell=200)
    a.aus()
    assert helligkeit(d) == 200
    assert lauf.aufrufe == [["wlopm", "--off", "DSI-1"]]


def test_wlopm_fehlschlag_ist_laut_und_backlight_reicht_dann_aus(tmp_path, caplog):
    a, d, _ = anzeige(tmp_path, lauf=Lauf(code=1))
    with caplog.at_level(logging.WARNING):
        assert a.aus() is True
    assert helligkeit(d) == 0
    assert "wlopm" in caplog.text and "teilweise" in caplog.text


def test_klappt_kein_weg_ist_aus_false(tmp_path, caplog):
    a, _, _ = anzeige(
        tmp_path, aus_weg="ausgang", lauf=Lauf(fehler=FileNotFoundError("wlopm"))
    )
    with caplog.at_level(logging.ERROR):
        assert a.aus() is False
    assert "wlopm" in caplog.text


def test_beleuchtung_nicht_beschreibbar_ist_laut(tmp_path, caplog):
    a, d, _ = anzeige(tmp_path, aus_weg="backlight")
    (d / "brightness").unlink()
    (d / "brightness").mkdir()  # Lesen und Schreiben scheitern
    with caplog.at_level(logging.ERROR):
        assert a.aus() is False
    assert "Beleuchtung" in caplog.text


def test_kann_helligkeit_nicht_gemerkt_werden_wird_nicht_abgedunkelt(tmp_path, caplog):
    a, d, _ = anzeige(tmp_path, aus_weg="backlight", hell=200)
    (tmp_path / "lauf").write_text("ist eine Datei")  # mkdir darunter scheitert
    with caplog.at_level(logging.ERROR):
        assert a.aus() is False
    assert helligkeit(d) == 200


def test_an_meldet_fehlschlag_von_wlopm(tmp_path):
    a, _, _ = anzeige(tmp_path, lauf=Lauf(code=2))
    assert a.an() is False


# --- Touch -----------------------------------------------------------------------------
def test_touch_ohne_passendes_geraet_laesst_sich_nicht_sperren(caplog):
    t = Touch(geraete_text='N: Name="Etwas anderes"\nH: Handlers=event0\n')
    with caplog.at_level(logging.ERROR):
        assert t.sperren() is False
    assert "Goodix" in caplog.text


def test_touch_geraetedatei_nicht_zu_oeffnen_ist_laut(caplog):
    t = Touch(
        geraete_text='N: Name="10-0014 Goodix Capacitive TouchScreen"\nH: Handlers=event99999\n'
    )
    with caplog.at_level(logging.ERROR):
        assert t.sperren() is False
    assert "input" in caplog.text


# --- Küchen-Dienst fragen --------------------------------------------------------------
def test_wach_fragen_ohne_dienst_heisst_wach_halten(caplog):
    haelt, gruende = wach_fragen("http://127.0.0.1:9/wach")
    assert haelt is True
    assert gruende[0].startswith("dienst:")


# --- Zusammenspiel ---------------------------------------------------------------------
class FalscherTouch:
    def __init__(self, sperrbar=True, ereignisse=()):
        self.sperrbar = sperrbar
        self.ereignisse = list(ereignisse)
        self.gesperrt = False
        self.fd = 42

    def sperren(self):
        self.gesperrt = self.sperrbar
        return self.sperrbar

    def lesen(self):
        e, self.ereignisse = self.ereignisse, []
        return e

    def freigeben(self):
        self.gesperrt = False


class FalscheAnzeige:
    def __init__(self, aus=True, an=True):
        self.aus_ok, self.an_ok = aus, an
        self.aufrufe = []

    def aus(self):
        self.aufrufe.append("aus")
        return self.aus_ok

    def an(self):
        self.aufrufe.append("an")
        return self.an_ok


def waechter(touch=None, anz=None):
    touch = touch or FalscherTouch()
    anz = anz or FalscheAnzeige()
    w = Waechter(Konfig(300, "beides"), anz, lambda: touch, 0.0)
    w.swayidle_zeile("IDLE", 1.0)
    return w, touch, anz


def test_ruhe_erreicht_display_aus_und_touch_gesperrt():
    w, touch, anz = waechter()
    w.takt(299.0)
    assert anz.aufrufe == []
    w.takt(300.0)
    assert anz.aufrufe == ["aus"] and touch.gesperrt and w.ruhe.schlaeft


def test_touch_nicht_sperrbar_display_bleibt_an_und_ist_laut(caplog):
    w, _, anz = waechter(touch=FalscherTouch(sperrbar=False))
    with caplog.at_level(logging.ERROR):
        w.takt(300.0)
    assert anz.aufrufe == [] and not w.ruhe.schlaeft
    assert "Display bleibt an" in caplog.text
    w.takt(301.0)  # nicht sofort wieder versuchen
    assert anz.aufrufe == []


def test_ausschalten_klappt_nicht_gibt_den_touch_zurueck(caplog):
    w, touch, _ = waechter(anz=FalscheAnzeige(aus=False))
    with caplog.at_level(logging.ERROR):
        w.takt(300.0)
    assert not w.ruhe.schlaeft and not touch.gesperrt
    assert "Display bleibt an" in caplog.text


def test_erster_tipp_weckt_und_der_touch_bleibt_bis_loslassen_gesperrt():
    touch = FalscherTouch()
    w, _, anz = waechter(touch=touch)
    w.takt(300.0)
    touch.ereignisse = [(EV_KEY, BTN_TOUCH, 1)]
    w.touch_lesen(400.0)
    assert anz.aufrufe == ["aus", "an"]
    assert not w.ruhe.schlaeft
    assert touch.gesperrt  # der Finger ist noch unten: Fenster bekommen nichts
    touch.ereignisse = [(EV_KEY, BTN_TOUCH, 0)]
    w.touch_lesen(400.2)
    assert not touch.gesperrt and w.touch is None


def test_nach_dem_wecken_laeuft_die_ruhezeit_ab_dem_tipp():
    touch = FalscherTouch()
    w, _, anz = waechter(touch=touch)
    w.takt(300.0)
    touch.ereignisse = [(EV_KEY, BTN_TOUCH, 1), (EV_KEY, BTN_TOUCH, 0)]
    w.touch_lesen(1000.0)
    w.takt(1299.0)
    assert anz.aufrufe == ["aus", "an"]
    w.takt(1300.0)
    assert anz.aufrufe == ["aus", "an", "aus"]


def test_haengender_finger_gibt_den_touch_nach_max_s_frei(caplog):
    touch = FalscherTouch()
    w, _, _ = waechter(touch=touch)
    w.takt(300.0)
    touch.ereignisse = [(EV_KEY, BTN_TOUCH, 1)]
    w.touch_lesen(400.0)
    with caplog.at_level(logging.WARNING):
        w.takt(400.0 + WeckTipp.MAX_S)
    assert not touch.gesperrt
    assert "hängt" in caplog.text


def test_eingabe_ohne_touch_weckt_und_gibt_den_touch_sofort_frei():
    w, touch, anz = waechter()
    w.takt(300.0)
    w.swayidle_zeile("AKTIV", 500.0)
    w.takt(500.5)
    assert anz.aufrufe == ["aus", "an"] and not touch.gesperrt


def test_elektra_weckt_das_schlafende_display_und_gibt_den_touch_frei():
    w, touch, anz = waechter()
    w.takt(300.0)
    w.wach_antwort(True, 600.0, ["elektra (zuhoeren)"])
    assert anz.aufrufe == ["aus", "an"] and not touch.gesperrt


def test_haelt_etwas_wach_wird_nicht_geschlafen():
    w, _, anz = waechter()
    w.wach_antwort(True, 250.0, ["video"])
    w.takt(400.0)
    assert anz.aufrufe == []
    w.wach_antwort(False, 405.0, [])
    w.takt(704.0)
    assert anz.aufrufe == []
    w.takt(705.0)
    assert anz.aufrufe == ["aus"]


def test_swayidle_faellt_aus_schlafendes_display_geht_an():
    w, _, anz = waechter()
    w.takt(300.0)
    w.swayidle_fehlt(310.0)
    w.takt(311.0)
    assert anz.aufrufe == ["aus", "an"]
    w.takt(10_000.0)
    assert anz.aufrufe == ["aus", "an"]  # ohne swayidle wird nicht mehr geschlafen


def test_einschalten_das_nicht_klappt_wird_wiederholt(caplog):
    anz = FalscheAnzeige(an=False)
    w, _, _ = waechter(anz=anz)
    w.takt(300.0)
    with caplog.at_level(logging.ERROR):
        w.swayidle_zeile("AKTIV", 400.0)
        w.takt(400.0)
    assert anz.aufrufe == ["aus", "an"] and w.an_offen
    w.takt(401.0)
    assert anz.aufrufe == ["aus", "an"]
    anz.an_ok = True
    w.takt(404.0)
    assert anz.aufrufe == ["aus", "an", "an"] and not w.an_offen
    assert "nicht gelungen" in caplog.text


def test_unbekannte_zeile_von_swayidle_ist_laut(caplog):
    w, _, _ = waechter()
    with caplog.at_level(logging.WARNING):
        w.swayidle_zeile("quatsch", 5.0)
    assert "Unerwartete Zeile" in caplog.text
