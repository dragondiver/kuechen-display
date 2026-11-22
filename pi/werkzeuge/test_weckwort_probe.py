"""Zähllogik der Weckwort-Probe (kuechen-display#111). Ohne Ton, Modell und Pi."""

import wave
from array import array

import pytest
from weckwort_probe import (
    RAHMEN,
    RAHMEN_S,
    RATE,
    SPERRE_S,
    Abbruch,
    abend_tabelle,
    ausloeser,
    kanal0,
    main,
    pegel_db,
    rahmen,
    rufe_tabelle,
    treffer,
    wav_dateien,
    wav_lesen,
    wav_schreiben,
    zeit_text,
)


# --- Kanal 0 aus sechs Kanälen ---------------------------------------------------------
def test_kanal0_nimmt_jede_sechste_probe():
    roh = array("h", [10, 1, 2, 3, 4, 5, 20, 1, 2, 3, 4, 5]).tobytes()
    assert list(kanal0(roh)) == [10, 20]


def test_kanal0_laesst_angebrochenen_rahmen_weg():
    roh = array("h", [10, 1, 2, 3, 4, 5, 20, 1, 2]).tobytes() + b"\x07"
    assert list(kanal0(roh)) == [10]


def test_kanal0_anderer_kanal_und_andere_breite():
    roh = array("h", [1, 2, 3, 4]).tobytes()
    assert list(kanal0(roh, kanaele=2, kanal=1)) == [2, 4]


# --- Pegel -----------------------------------------------------------------------------
def test_pegel_volle_aussteuerung_ist_null_db():
    assert pegel_db(array("h", [0, -32768, 5])) == pytest.approx(0.0)


def test_pegel_halbe_aussteuerung_sind_minus_sechs_db():
    assert pegel_db(array("h", [16384])) == pytest.approx(-6.02, abs=0.01)


def test_pegel_stille_und_leer_sind_minus_unendlich():
    assert pegel_db(array("h", [0, 0])) == float("-inf")
    assert pegel_db(array("h")) == float("-inf")


# --- Rahmen ----------------------------------------------------------------------------
def test_rahmen_fuellt_den_letzten_mit_stille():
    stuecke = list(rahmen(array("h", [1, 2, 3, 4, 5]), groesse=2))
    assert [list(s) for s in stuecke] == [[1, 2], [3, 4], [5, 0]]


def test_rahmen_veraendert_die_eingabe_nicht():
    proben = array("h", [1, 2, 3])
    list(rahmen(proben, groesse=2))
    assert list(proben) == [1, 2, 3]


def test_rahmen_ohne_proben_ergibt_nichts():
    assert list(rahmen(array("h"))) == []


# --- Treffer bei einzelnen Rufen -------------------------------------------------------
def test_treffer_zaehlt_ab_der_schwelle():
    werte = [0.9, 0.5, 0.49, 0.0]
    assert treffer(werte, 0.5) == 2
    assert treffer(werte, 0.3) == 3
    assert treffer([], 0.5) == 0


# --- Auslöser in einer langen Aufnahme -------------------------------------------------
def test_ein_ruf_ueber_mehrere_rahmen_zaehlt_einmal():
    werte = [0.0, 0.6, 0.9, 0.7, 0.0, 0.0]
    assert ausloeser(werte, 0.5, sperre=5) == [(1, 0.9)]


def test_nach_der_sperre_zaehlt_ein_neuer_ausloeser():
    werte = [0.8, 0.8, 0.0, 0.8]
    assert ausloeser(werte, 0.5, sperre=2) == [(0, 0.8), (3, 0.8)]


def test_dauerhaft_ueber_der_schwelle_zaehlt_je_sperre_einmal():
    assert len(ausloeser([0.9] * 10, 0.5, sperre=5)) == 2


def test_unter_der_schwelle_und_leer_ergibt_nichts():
    assert ausloeser([0.1, 0.49], 0.5, sperre=5) == []
    assert ausloeser([], 0.5, sperre=5) == []


def test_sperre_null_haengt_nicht():
    assert ausloeser([0.9, 0.9], 0.5, sperre=0) == [(0, 0.9), (1, 0.9)]


# --- Ausgabe ---------------------------------------------------------------------------
def test_zeit_text():
    assert zeit_text(0) == "00:00"
    assert zeit_text(252.9) == "04:12"


def test_rufe_tabelle_zeigt_treffer_von_aufnahmen_je_schwelle():
    zeilen = rufe_tabelle(
        {"herd-ruhe": [0.9, 0.45, 0.2], "tisch": [0.65]}, schwellen=(0.3, 0.5, 0.7)
    )
    assert zeilen[0].split() == ["Rufe", "0,3", "0,5", "0,7"]
    assert zeilen[1].split() == ["herd-ruhe", "2/3", "1/3", "1/3"]
    assert zeilen[2].split() == ["tisch", "1/1", "1/1", "0/1"]


def test_abend_tabelle_rechnet_auf_die_stunde_um():
    # Eine halbe Stunde Stille mit zwei Ausschlägen, weit genug auseinander.
    werte = [0.0] * round(1800 / RAHMEN_S)
    werte[100] = 0.6
    werte[5000] = 0.9
    zeilen = abend_tabelle([werte], schwellen=(0.5, 0.7))
    assert zeilen[1].split() == ["0,5", "2", "4,0"]
    assert zeilen[2].split() == ["0,7", "1", "2,0"]


def test_abend_tabelle_zaehlt_je_datei_und_summiert():
    sperre = round(SPERRE_S / RAHMEN_S)
    eins = [0.9] + [0.0] * (sperre * 2)
    zeilen = abend_tabelle([eins, eins], schwellen=(0.5,))
    assert zeilen[1].split()[1] == "2"


def test_abend_tabelle_ohne_ton_teilt_nicht_durch_null():
    assert abend_tabelle([], schwellen=(0.5,))[1].split() == ["0,5", "0", "–"]


# --- Dateien ---------------------------------------------------------------------------
def test_wav_hin_und_zurueck(tmp_path):
    proben = array("h", [0, 1000, -1000, 32767])
    wav_schreiben(tmp_path / "a.wav", proben)
    assert wav_lesen(tmp_path / "a.wav") == proben


def test_wav_lesen_lehnt_fremdes_format_ab(tmp_path):
    pfad = tmp_path / "stereo.wav"
    with wave.open(str(pfad), "wb") as datei:
        datei.setnchannels(2)
        datei.setsampwidth(2)
        datei.setframerate(RATE)
        datei.writeframes(b"\x00" * 8)
    with pytest.raises(Abbruch, match="2 Kanäle"):
        wav_lesen(pfad)


def test_wav_dateien_sortiert_und_meldet_leere_ordner(tmp_path):
    with pytest.raises(Abbruch, match="Ordner fehlt"):
        wav_dateien(tmp_path / "gibt-es-nicht")
    with pytest.raises(Abbruch, match="Keine .wav"):
        wav_dateien(tmp_path)
    for name in ("ruf-02.wav", "ruf-01.wav"):
        wav_schreiben(tmp_path / name, array("h", [0] * RAHMEN))
    assert [p.name for p in wav_dateien(tmp_path)] == ["ruf-01.wav", "ruf-02.wav"]


# --- Aufruf: Fehler enden mit einem Satz und Code 1, nicht still ------------------------
def test_zaehlen_ohne_aufnahmen_ist_ein_fehler(tmp_path, capsys):
    assert main(["zaehlen", str(tmp_path / "elektra.onnx")]) == 1
    assert "Nichts zu zählen" in capsys.readouterr().err


def test_zaehlen_mit_fehlendem_modell_ist_ein_fehler(tmp_path, capsys):
    assert (
        main(["zaehlen", str(tmp_path / "elektra.onnx"), "--abend", str(tmp_path)]) == 1
    )
    assert "Modell fehlt" in capsys.readouterr().err


def test_zaehlen_lehnt_tflite_ab(tmp_path, capsys):
    modell = tmp_path / "elektra.tflite"
    modell.write_bytes(b"")
    assert main(["zaehlen", str(modell), "--abend", str(tmp_path)]) == 1
    assert ".onnx" in capsys.readouterr().err
