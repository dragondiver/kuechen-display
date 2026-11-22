"""Lautstärke (#99): Umrechnung, Prüfung, Merken und Wiederherstellen."""

from itertools import pairwise

import pytest
from lautstaerke import STANDARD, Lautstaerke, pipewire_anteil, pruefen


def test_null_ist_stumm():
    assert pipewire_anteil(0) == 0.0


def test_eins_ist_die_kleinste_hoerbare_stufe():
    assert pipewire_anteil(1) == pytest.approx(0.35)


def test_hundert_ist_voll():
    assert pipewire_anteil(100) == pytest.approx(1.0)


def test_zwischenwert_liegt_linear_dazwischen():
    # 50 ist 49 von 99 Schritten zwischen 0,35 und 1,0
    assert pipewire_anteil(50) == pytest.approx(0.35 + 0.65 * 49 / 99)


def test_umrechnung_steigt_mit_jeder_stufe():
    werte = [pipewire_anteil(s) for s in range(101)]
    assert all(a < b for a, b in pairwise(werte))


@pytest.mark.parametrize("wert", [0, 1, 60, 100, 55.0])
def test_gueltige_werte(wert):
    assert pruefen(wert) == int(wert)


@pytest.mark.parametrize(
    "wert",
    [
        -1,
        101,
        140,
        55.5,
        "50",
        "",
        None,
        True,
        False,
        [50],
        {"a": 1},
        float("nan"),
        float("inf"),
    ],
)
def test_ungueltige_werte(wert):
    assert pruefen(wert) is None


def test_ohne_datei_gilt_der_standard(tmp_path):
    l = Lautstaerke(tmp_path / "lautstaerke")
    assert l.laden() == STANDARD == 60


@pytest.mark.parametrize("inhalt", ["", "laut", "101", "-3", "55.5", "\x00\xff"])
def test_unlesbare_datei_gilt_als_standard(tmp_path, inhalt):
    datei = tmp_path / "lautstaerke"
    datei.write_text(inhalt)
    assert Lautstaerke(datei).laden() == STANDARD


def test_gemerkt_und_wiedergefunden(tmp_path):
    datei = tmp_path / "unterordner" / "lautstaerke"
    Lautstaerke(datei).setzen(42)
    neu = Lautstaerke(datei)
    assert neu.laden() == 42 and neu.stellung == 42


def test_null_wird_auch_gemerkt(tmp_path):
    datei = tmp_path / "lautstaerke"
    Lautstaerke(datei).setzen(0)
    assert Lautstaerke(datei).laden() == 0


def test_schreibfehler_stoert_nicht(tmp_path):
    (tmp_path / "datei").write_text("x")
    l = Lautstaerke(tmp_path / "datei" / "lautstaerke")  # Elternteil ist eine Datei
    l.setzen(30)
    assert l.stellung == 30
