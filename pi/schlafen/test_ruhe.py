import struct
from pathlib import Path

import pytest
from ruhe import (
    ABS_MT_SLOT,
    ABS_MT_TRACKING_ID,
    BTN_TOUCH,
    EV_ABS,
    EV_KEY,
    IDLE_SCHRITT_S,
    NEUER_VERSUCH_S,
    NICHTS,
    SCHLAFEN,
    STANDARD_AUS_WEG,
    STANDARD_RUHE_S,
    WECKEN,
    Konfig,
    Ruhe,
    WeckTipp,
    ereignisse_zerlegen,
    konfig_lesen,
    touch_geraet_finden,
)

HIER = Path(__file__).parent


# --- Konfiguration ---------------------------------------------------------------------
def test_konfig_im_repo_ist_fehlerfrei_und_gibt_fuenf_minuten():
    konfig, probleme = konfig_lesen((HIER / "schlafen.conf").read_text())
    assert probleme == []
    assert konfig == Konfig(300, "beides")


def test_konfig_leer_gibt_standard_ohne_meldung():
    assert konfig_lesen("") == (Konfig(STANDARD_RUHE_S, STANDARD_AUS_WEG), [])


def test_konfig_liest_werte_und_kommentare():
    konfig, probleme = konfig_lesen(
        "# x\nRUHE_S = 120  # zwei Minuten\nAUS_WEG=backlight\n"
    )
    assert konfig == Konfig(120, "backlight")
    assert probleme == []


@pytest.mark.parametrize("wert", ["abc", "5", "0", "-300", "99999999", "1.5", ""])
def test_konfig_unbrauchbare_ruhezeit_gibt_standard_und_meldung(wert):
    konfig, probleme = konfig_lesen(f"RUHE_S={wert}\n")
    assert konfig.ruhe_s == STANDARD_RUHE_S
    assert len(probleme) == 1 and "RUHE_S" in probleme[0]


def test_konfig_unbekannter_aus_weg_gibt_standard_und_meldung():
    konfig, probleme = konfig_lesen("AUS_WEG=strom\n")
    assert konfig.aus_weg == STANDARD_AUS_WEG
    assert len(probleme) == 1


def test_konfig_unbekannter_schluessel_und_unsinn_werden_gemeldet():
    konfig, probleme = konfig_lesen("RUHE_SEKUNDEN=60\nirgendwas\n")
    assert konfig == Konfig()
    assert len(probleme) == 2


# --- Ruhe erreicht? --------------------------------------------------------------------
def ruhig_seit(ruhe: Ruhe, t: float) -> None:
    """swayidle meldet „ruhig“ zum Zeitpunkt t."""
    ruhe.ruhig(t)


def test_nach_ruhezeit_ohne_eingabe_wird_geschlafen():
    r = Ruhe(300, 0.0)
    ruhig_seit(r, 1.0)
    assert r.tick(299.0) == NICHTS
    assert r.tick(300.0) == SCHLAFEN  # letzte Eingabe bei 0,0 s (1,0 − Schritt)


def test_solange_swayidle_nicht_ruhig_sagt_wird_nicht_geschlafen():
    r = Ruhe(300, 0.0)
    assert r.tick(10_000.0) == NICHTS  # Eingabe gilt als laufend


def test_eingabe_setzt_die_zeit_neu():
    r = Ruhe(300, 0.0)
    ruhig_seit(r, 1.0)
    r.aktiv(200.0)
    ruhig_seit(r, 201.0)
    assert r.tick(300.0) == NICHTS
    assert r.tick(499.0) == NICHTS
    assert r.tick(500.0) == SCHLAFEN


def test_haltende_dinge_verhindern_schlafen():
    r = Ruhe(300, 0.0)
    ruhig_seit(r, 1.0)
    r.halt(250.0, True)
    assert r.tick(400.0) == NICHTS


def test_nach_ende_des_halts_laeuft_die_ruhezeit_neu():
    r = Ruhe(300, 0.0)
    ruhig_seit(r, 1.0)
    r.halt(1000.0, True)
    r.halt(1005.0, False)
    assert r.tick(1304.0) == NICHTS
    assert r.tick(1305.0) == SCHLAFEN  # ab letztem Halt bei 1005


def test_wach_halten_gilt_auch_fuer_das_erste_halbe_jahr_der_ruhe():
    """Halt vor langer Zeit zählt nicht mehr: Nur der letzte Halt verschiebt die Frist."""
    r = Ruhe(300, 0.0)
    ruhig_seit(r, 1.0)
    r.halt(5.0, True)
    r.halt(6.0, False)
    assert r.tick(306.0) == SCHLAFEN


def test_schlafen_misslungen_sperrt_den_nächsten_versuch():
    r = Ruhe(300, 0.0)
    ruhig_seit(r, 1.0)
    assert r.tick(400.0) == SCHLAFEN
    r.schlafen_misslungen(400.0)
    assert r.tick(400.0 + NEUER_VERSUCH_S - 1) == NICHTS
    assert r.tick(400.0 + NEUER_VERSUCH_S) == SCHLAFEN


def test_swayidle_fehlt_verhindert_schlafen():
    r = Ruhe(300, 0.0)
    ruhig_seit(r, 1.0)
    r.eingabe_unbekannt()
    assert r.tick(10_000.0) == NICHTS


# --- Aufwachen -------------------------------------------------------------------------
def eingeschlafene_ruhe() -> Ruhe:
    r = Ruhe(300, 0.0)
    ruhig_seit(r, 1.0)
    assert r.tick(300.0) == SCHLAFEN
    r.eingeschlafen()
    return r


def test_schlafend_und_ruhig_passiert_nichts():
    r = eingeschlafene_ruhe()
    assert r.tick(301.0) == NICHTS
    assert r.tick(9999.0) == NICHTS


def test_eingabe_von_swayidle_weckt():
    r = eingeschlafene_ruhe()
    assert r.aktiv(400.0) == WECKEN
    assert r.tick(401.0) == WECKEN  # bleibt Anlass, bis der Wächter aufgewacht() meldet


def test_elektra_weckt_das_schlafende_display_nicht():
    """Festlegung 16.11.2026: Elektra, auch mit Erinnerung, lässt ein schlafendes Display dunkel."""
    r = eingeschlafene_ruhe()
    r.halt(400.0, True)
    assert r.tick(400.0) == NICHTS
    assert r.tick(9999.0) == NICHTS


def test_halt_waehrend_des_schlafs_zaehlt_nach_dem_wecken_per_tipp_weiter():
    """Läuft der Halt beim Aufwachen noch, beginnen die 5 Minuten erst nach seinem Ende."""
    r = eingeschlafene_ruhe()
    r.halt(400.0, True)
    r.beruehrt(500.0)
    r.aufgewacht(500.0)
    r.halt(505.0, True)
    assert r.tick(5000.0) == NICHTS
    r.halt(5000.0, False)
    assert r.tick(5299.0) == NICHTS
    assert r.tick(5300.0) == SCHLAFEN


def test_halt_der_vor_dem_wecken_endete_laesst_die_zeit_ab_dem_tipp_laufen():
    r = eingeschlafene_ruhe()
    r.halt(400.0, True)
    r.halt(410.0, False)
    r.beruehrt(1000.0)
    r.aufgewacht(1000.0)
    assert r.tick(1299.0) == NICHTS
    assert r.tick(1300.0) == SCHLAFEN


def test_kein_halt_weckt_nicht():
    r = eingeschlafene_ruhe()
    r.halt(400.0, False)
    assert r.tick(401.0) == NICHTS


def test_swayidle_weg_weckt():
    r = eingeschlafene_ruhe()
    assert r.eingabe_unbekannt() == WECKEN


def test_nach_wecken_per_beruehrung_laeuft_die_ruhezeit_ab_der_beruehrung():
    r = eingeschlafene_ruhe()
    r.beruehrt(1000.0)  # nur der Wächter sah sie, swayidle bleibt „ruhig“
    r.aufgewacht(1000.0)
    assert r.tick(1299.0) == NICHTS
    assert r.tick(1300.0) == SCHLAFEN


def test_spaeteres_ruhig_von_swayidle_macht_die_zeit_nicht_kuerzer():
    r = eingeschlafene_ruhe()
    r.beruehrt(1000.0)
    r.aufgewacht(1000.0)
    r.ruhig(1000.5)  # swayidle meldet „ruhig“, ohne die Berührung gesehen zu haben
    assert r.letzte_eingabe == 1000.0


def test_ruhig_setzt_die_letzte_eingabe_einen_schritt_zurueck():
    r = Ruhe(300, 0.0)
    r.aktiv(50.0)
    r.ruhig(50.0 + IDLE_SCHRITT_S)
    assert r.letzte_eingabe == 50.0


# --- Weck-Tipp -------------------------------------------------------------------------
def tippen(w: WeckTipp, ereignisse, t=0.0):
    return [w.ereignis(a, c, v, t) for a, c, v in ereignisse]


def test_erste_beruehrung_weckt_und_loslassen_gibt_frei():
    w = WeckTipp()
    runter = tippen(
        w,
        [
            (EV_ABS, ABS_MT_SLOT, 0),
            (EV_ABS, ABS_MT_TRACKING_ID, 7),
            (EV_KEY, BTN_TOUCH, 1),
        ],
    )
    assert [t.weck for t in runter] == [False, True, False]
    assert not any(t.frei for t in runter)
    hoch = tippen(w, [(EV_ABS, ABS_MT_TRACKING_ID, -1), (EV_KEY, BTN_TOUCH, 0)])
    assert [t.frei for t in hoch] == [True, False] or any(t.frei for t in hoch)
    assert not any(t.weck for t in hoch)


def test_nur_btn_touch_reicht_zum_wecken_und_freigeben():
    w = WeckTipp()
    assert w.ereignis(EV_KEY, BTN_TOUCH, 1, 0.0).weck
    assert w.ereignis(EV_KEY, BTN_TOUCH, 0, 0.1).frei


def test_zweiter_finger_haelt_den_touch_gesperrt():
    w = WeckTipp()
    w.ereignis(EV_ABS, ABS_MT_SLOT, 0, 0.0)
    assert w.ereignis(EV_ABS, ABS_MT_TRACKING_ID, 1, 0.0).weck
    w.ereignis(EV_ABS, ABS_MT_SLOT, 1, 0.1)
    assert not w.ereignis(EV_ABS, ABS_MT_TRACKING_ID, 2, 0.1).weck
    w.ereignis(EV_ABS, ABS_MT_SLOT, 0, 0.2)
    assert not w.ereignis(
        EV_ABS, ABS_MT_TRACKING_ID, -1, 0.2
    ).frei  # Slot 1 ist noch unten
    w.ereignis(EV_ABS, ABS_MT_SLOT, 1, 0.3)
    assert w.ereignis(EV_ABS, ABS_MT_TRACKING_ID, -1, 0.3).frei


def test_positionsereignisse_machen_nichts():
    w = WeckTipp()
    assert not any(
        t.weck or t.frei
        for t in tippen(w, [(EV_ABS, 0x35, 100), (EV_ABS, 0x36, 200), (0, 0, 0)])
    )
    assert w.beginn is None


def test_loslassen_ohne_aufsetzen_gibt_nicht_frei():
    w = WeckTipp()
    assert not w.ereignis(EV_KEY, BTN_TOUCH, 0, 0.0).frei


def test_haengende_beruehrung_wird_nach_max_s_freigegeben():
    w = WeckTipp()
    w.ereignis(EV_KEY, BTN_TOUCH, 1, 10.0)
    assert not w.tick(10.0 + WeckTipp.MAX_S - 0.1).frei
    assert w.tick(10.0 + WeckTipp.MAX_S).frei


def test_ohne_beruehrung_gibt_tick_nie_frei():
    assert not WeckTipp().tick(1e9).frei


# --- Rohdaten --------------------------------------------------------------------------
def roh(art, code, wert):
    return struct.pack("llHHi", 1, 2, art, code, wert)


def test_ereignisse_werden_zerlegt_und_der_rest_bleibt():
    daten = roh(EV_KEY, BTN_TOUCH, 1) + roh(EV_ABS, 0x35, 640) + roh(0, 0, 0)
    ereignisse, rest = ereignisse_zerlegen(daten + b"\x01\x02")
    assert ereignisse == [(EV_KEY, BTN_TOUCH, 1), (EV_ABS, 0x35, 640), (0, 0, 0)]
    assert rest == b"\x01\x02"


def test_halb_gelesenes_ereignis_wird_beim_naechsten_mal_ergaenzt():
    ganz = roh(EV_KEY, BTN_TOUCH, 0)
    erste, rest = ereignisse_zerlegen(ganz[:10])
    assert erste == [] and rest == ganz[:10]
    zweite, rest = ereignisse_zerlegen(rest + ganz[10:])
    assert zweite == [(EV_KEY, BTN_TOUCH, 0)] and rest == b""


GERAETE = """\
I: Bus=0018 Vendor=0416 Product=038f Version=0100
N: Name="10-0014 Goodix Capacitive TouchScreen"
P: Phys=i2c-10/10-0014/input0
H: Handlers=mouse0 event4 
B: PROP=2

I: Bus=0003 Vendor=2886 Product=001a Version=0100
N: Name="reSpeaker XVF3800"
H: Handlers=kbd event5
"""


def test_touch_geraet_wird_nach_namen_gefunden():
    assert (
        touch_geraet_finden(GERAETE, "10-0014 Goodix Capacitive TouchScreen")
        == "/dev/input/event4"
    )


def test_touch_geraet_fehlt_gibt_none():
    assert touch_geraet_finden(GERAETE, "Gibt es nicht") is None
    assert touch_geraet_finden("", "x") is None


def test_touch_name_stimmt_mit_der_labwc_regel_ueberein():
    """Der Wächter sperrt dasselbe Gerät, das labwc als Touch auf DSI-1 abbildet."""
    from schlafwaechter import AUSGANG, TOUCH_NAME

    labwc = (HIER.parent / "kiosk" / "labwc-rc.xml").read_text()
    assert f'deviceName="{TOUCH_NAME}"' in labwc
    assert f'mapToOutput="{AUSGANG}"' in labwc
