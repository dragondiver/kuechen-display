import logging

import pytest
from weckwort import (
    ANZEIGE_FRIST_S,
    ENTPRELL_S,
    NACHLAUF_S,
    NICHTS,
    REZEPT_FRIST_S,
    VOR,
    WECKEN,
    ZURUECK,
    AnzeigeStand,
    Lauscher,
    Rezept,
    Weckwort,
    entscheide,
    erkenner_laden,
    wort_lesen,
)


# --- Wort aus dem Erkennungstext -------------------------------------------------------
def test_einzelnes_wort_zaehlt():
    assert wort_lesen("weiter") == (VOR, None)
    assert wort_lesen("zurück") == (ZURUECK, None)
    assert wort_lesen("Weiter") == (VOR, None)


def test_wiederholtes_wort_zaehlt_einmal():
    assert wort_lesen("weiter weiter") == (VOR, None)


def test_leer_und_fremdes_ist_kein_treffer_und_kein_grund_fuers_journal():
    for text in ("", "[unk]", "[unk] [unk]"):
        assert wort_lesen(text) == (None, None)


def test_wort_im_satz_wird_verworfen_mit_grund():
    wort, grund = wort_lesen("[unk] [unk] weiter")
    assert wort is None and "nicht allein" in grund


def test_beide_woerter_in_einer_aeusserung_werden_verworfen_mit_grund():
    wort, grund = wort_lesen("weiter zurück")
    assert wort is None and "beide" in grund


# --- Entscheidung ----------------------------------------------------------------------
@pytest.mark.parametrize("wort", [VOR, ZURUECK])
def test_display_an_blaettert(wort):
    assert entscheide(wort, rezept_offen=True, gesperrt=False, dunkel=False) == wort


@pytest.mark.parametrize("wort", [VOR, ZURUECK])
def test_display_dunkel_weckt_nur(wort):
    assert entscheide(wort, rezept_offen=True, gesperrt=False, dunkel=True) == WECKEN


@pytest.mark.parametrize("wort", [VOR, ZURUECK])
def test_zustand_unbekannt_weckt_und_blaettert_nie(wort):
    assert entscheide(wort, rezept_offen=True, gesperrt=False, dunkel=None) == WECKEN


@pytest.mark.parametrize("dunkel", [True, False, None])
def test_kein_rezept_wertet_nichts_aus(dunkel):
    assert entscheide(VOR, rezept_offen=False, gesperrt=False, dunkel=dunkel) == NICHTS


@pytest.mark.parametrize("dunkel", [True, False, None])
def test_elektra_oder_diktat_sperrt(dunkel):
    assert entscheide(VOR, rezept_offen=True, gesperrt=True, dunkel=dunkel) == NICHTS


# --- Rezept offen mit Frist ------------------------------------------------------------
def test_rezept_gilt_bis_zur_frist():
    r = Rezept()
    r.melden(True, 100.0)
    assert r.gilt(100.0 + REZEPT_FRIST_S - 0.1, None)
    assert not r.gilt(100.0 + REZEPT_FRIST_S, None)


def test_rezept_zu_gemeldet_gilt_sofort_nicht_mehr():
    r = Rezept()
    r.melden(True, 100.0)
    r.melden(False, 101.0)
    assert not r.gilt(101.5, None)


def test_rezept_ohne_meldung_gilt_nicht():
    assert not Rezept().gilt(5.0, None)


def test_kiosk_seite_vorn_setzt_zurueck():
    r = Rezept()
    r.melden(True, 100.0)
    r.zuruecksetzen()
    assert not r.gilt(100.5, None)


def test_rezept_bleibt_offen_wenn_das_display_nach_der_letzten_meldung_dunkel_wurde():
    """Die Seite meldet im Dunkeln womöglich nicht mehr; was beim Einschlafen offen war, bleibt offen."""
    r = Rezept()
    r.melden(True, 100.0)
    assert r.gilt(100.0 + 3600, dunkel_seit=102.0)


def test_rezept_das_schon_vor_dem_dunkelwerden_abgelaufen_war_gilt_nicht():
    r = Rezept()
    r.melden(True, 100.0)
    assert not r.gilt(100.0 + 3600, dunkel_seit=100.0 + REZEPT_FRIST_S + 1)


def test_nach_dem_aufwachen_zaehlt_die_frist_wieder():
    r = Rezept()
    r.melden(True, 100.0)
    assert not r.gilt(100.0 + 3600, dunkel_seit=None)


# --- Zustand des Displays --------------------------------------------------------------
def test_anzeige_ohne_meldung_ist_unbekannt():
    assert AnzeigeStand().stand(1.0) is None


def test_anzeige_meldung_gilt_bis_zur_frist_dann_unbekannt():
    a = AnzeigeStand()
    a.melden(False, 10.0)
    assert a.stand(10.0 + ANZEIGE_FRIST_S - 0.1) is False
    assert a.stand(10.0 + ANZEIGE_FRIST_S) is None


def test_dunkel_seit_bleibt_beim_ersten_dunkelwerden_stehen():
    a = AnzeigeStand()
    a.melden(False, 10.0)
    a.melden(True, 20.0)
    a.melden(True, 21.0)
    assert a.seit(21.5) == 20.0
    a.melden(False, 30.0)
    assert a.seit(30.5) is None


def test_dunkel_seit_ist_bei_veralteter_meldung_unbekannt():
    a = AnzeigeStand()
    a.melden(True, 20.0)
    assert a.seit(20.0 + ANZEIGE_FRIST_S) is None


# --- Zusammenspiel in Weckwort ---------------------------------------------------------
def bereit(dunkel, rezept=True):
    w = Weckwort(start=1)
    if rezept:
        w.rezept.melden(True, 100.0)
    if dunkel is not None:
        w.anzeige.melden(dunkel, 100.0)
    return w


def test_dunkel_weckt_und_zaehlt_hoch_ohne_zu_blaettern():
    w = bereit(dunkel=True)
    t = w.wort("weiter", False, 101.0)
    assert t.aktion == WECKEN
    assert w.wecken_zaehler == 1


def test_an_blaettert_und_zaehlt_nicht_hoch():
    w = bereit(dunkel=False)
    t = w.wort("weiter", False, 101.0)
    assert t.aktion == VOR
    assert w.wecken_zaehler == 0
    assert w.wort("zurück", False, 101.1).aktion == ZURUECK


def test_unbekannter_zustand_weckt_statt_zu_blaettern():
    w = bereit(dunkel=None)
    t = w.wort("weiter", False, 101.0)
    assert t.aktion == WECKEN and "unbekannt" in t.grund


def test_kein_rezept_nichts():
    w = bereit(dunkel=False, rezept=False)
    assert w.wort("weiter", False, 101.0) is None
    assert w.wecken_zaehler == 0 and w.gehoert == 0


def test_elektra_oder_diktat_aktiv_nichts():
    w = bereit(dunkel=False)
    assert w.wort("weiter", True, 101.0) is None


def test_nach_elektra_gilt_noch_der_nachlauf():
    w = bereit(dunkel=False)
    assert w.wort("weiter", True, 101.0) is None
    assert w.wort("weiter", False, 101.0 + NACHLAUF_S - 0.1) is None
    assert w.wort("weiter", False, 101.0 + NACHLAUF_S).aktion == VOR


def test_dasselbe_wort_nicht_zweimal_in_kurzer_zeit():
    w = bereit(dunkel=False)
    assert w.wort("weiter", False, 101.0).aktion == VOR
    assert w.wort("weiter", False, 101.0 + ENTPRELL_S - 0.1) is None
    assert w.wort("weiter", False, 101.0 + ENTPRELL_S).aktion == VOR


def test_anderes_wort_wird_nicht_entprellt():
    w = bereit(dunkel=False)
    assert w.wort("weiter", False, 101.0).aktion == VOR
    assert w.wort("zurück", False, 101.2).aktion == ZURUECK


def test_gesperrtes_wort_verbraucht_die_entprellung_nicht():
    w = bereit(dunkel=False)
    w.wort("weiter", True, 101.0)
    w2 = bereit(dunkel=False)
    assert w2.wort("weiter", False, 101.0).aktion == VOR


def test_entprellen_gilt_auch_beim_wecken():
    w = bereit(dunkel=True)
    assert w.wort("weiter", False, 101.0).aktion == WECKEN
    assert w.wort("weiter", False, 101.5) is None
    assert w.wecken_zaehler == 1


def test_hoert_nur_bei_offenem_rezept_und_ohne_elektra():
    w = bereit(dunkel=False)
    assert w.hoert(False, 101.0)
    assert not w.hoert(True, 101.0)
    assert not w.hoert(False, 101.0 + 0.5)  # Nachlauf
    assert not bereit(dunkel=False, rezept=False).hoert(False, 101.0)


def test_im_dunkeln_hoert_es_weiter_mit_dem_beim_einschlafen_offenen_rezept():
    w = Weckwort(start=1)
    w.rezept.melden(True, 100.0)
    w.anzeige.melden(False, 100.0)
    w.anzeige.melden(True, 101.0)
    spaeter = 101.0 + 600
    w.anzeige.melden(True, spaeter - 1)  # der Wächter fragt jede Sekunde
    assert w.hoert(False, spaeter)


# --- Erkennung -------------------------------------------------------------------------
class FalscherErkenner:
    def __init__(self, texte=(), fehler=None):
        self.texte = list(texte)
        self.fehler = fehler
        self.zurueckgesetzt = 0
        self.gesehen = []

    def ton(self, daten):
        self.gesehen.append(daten)
        if self.fehler:
            raise self.fehler
        return self.texte.pop(0) if self.texte else None

    def zuruecksetzen(self):
        self.zurueckgesetzt += 1


def abarbeiten(l):
    while not l.schlange.empty():
        l.schritt()


def test_lauscher_reicht_ergebnisse_weiter_und_ignoriert_leere():
    gehoert = []
    l = Lauscher(FalscherErkenner([None, "", "weiter"]), gehoert.append)
    for _ in range(3):
        l.rahmen(b"x", True)
    abarbeiten(l)
    assert gehoert == ["weiter"]


def test_lauscher_gibt_ohne_hoeren_nichts_an_die_erkennung_und_setzt_einmal_zurueck():
    e = FalscherErkenner()
    l = Lauscher(e, lambda t: None)
    l.rahmen(b"x", True)
    l.rahmen(b"x", False)
    l.rahmen(b"x", False)
    abarbeiten(l)
    assert e.gesehen == [b"x"] and e.zurueckgesetzt == 1


def test_lauscher_faellt_er_aus_ist_das_laut_und_endgueltig(caplog):
    l = Lauscher(FalscherErkenner(fehler=RuntimeError("kaputt")), lambda t: None)
    l.rahmen(b"x", True)
    with caplog.at_level(logging.ERROR):
        assert l.schritt() is False
    assert not l.bereit
    assert "Erkennung ausgefallen" in caplog.text
    l.rahmen(b"x", True)  # nimmt nichts mehr an
    assert l.schlange.empty()


def test_lauscher_blockiert_die_mikro_schleife_nie_und_meldet_ueberlauf(caplog):
    l = Lauscher(FalscherErkenner(), lambda t: None)
    with caplog.at_level(logging.WARNING):
        for _ in range(l.schlange.maxsize + 5):
            l.rahmen(b"x", True)
    assert l.verworfen == 5
    assert "kommt nicht mit" in caplog.text


# --- Laden: Fehlen von Paket oder Modell ----------------------------------------------
def test_fehlendes_paket_gibt_fehlertext_statt_ausnahme(tmp_path):
    def importieren(name):
        raise ImportError("No module named 'vosk'")

    erkenner, fehler = erkenner_laden(tmp_path, 16000, importieren)
    assert erkenner is None and "Paket vosk fehlt" in fehler


def test_fehlendes_modell_gibt_fehlertext(tmp_path):
    erkenner, fehler = erkenner_laden(
        tmp_path / "gibt-es-nicht", 16000, lambda n: object()
    )
    assert erkenner is None and "Modell fehlt" in fehler


def test_kaputtes_modell_gibt_fehlertext(tmp_path):
    class Vosk:
        @staticmethod
        def SetLogLevel(stufe):
            pass

        @staticmethod
        def Model(pfad):
            raise Exception("Failed to create a model")  # noqa: TRY002

    erkenner, fehler = erkenner_laden(tmp_path, 16000, lambda n: Vosk)
    assert erkenner is None and "nicht ladbar" in fehler


def test_laden_mit_attrappe_gibt_erkenner_mit_der_grammatik(tmp_path):
    aufrufe = []

    class Kaldi:
        def __init__(self, modell, rate, grammatik):
            aufrufe.append((modell, rate, grammatik))

    class Vosk:
        KaldiRecognizer = Kaldi

        @staticmethod
        def SetLogLevel(stufe):
            pass

        @staticmethod
        def Model(pfad):
            return "modell"

    erkenner, fehler = erkenner_laden(tmp_path, 16000, lambda n: Vosk)
    assert fehler is None and erkenner is not None
    assert aufrufe == [("modell", 16000, '["weiter", "zurück", "[unk]"]')]
