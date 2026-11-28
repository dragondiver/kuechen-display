"""Fäden in main() (#122): Eine Ausnahme beendet den Prozess, ein reguläres Ende nicht."""

import logging
import threading

import dienst


def beenden_abfangen(monkeypatch):
    codes: list[int] = []
    monkeypatch.setattr(dienst.os, "_exit", codes.append)
    return codes


def test_ausnahme_beendet_den_prozess_und_nennt_den_faden(monkeypatch, caplog):
    codes = beenden_abfangen(monkeypatch)

    def kaputt():
        raise ValueError("falsch geformt")

    with caplog.at_level(logging.ERROR):
        dienst.faden_starten(kaputt).join(timeout=5)
    assert codes == [1]
    assert "kaputt" in caplog.text
    assert "falsch geformt" in caplog.text  # Traceback steht im Journal


def test_regulaeres_ende_laesst_den_prozess_leben(monkeypatch):
    codes = beenden_abfangen(monkeypatch)
    gelaufen = threading.Event()
    dienst.faden_starten(gelaufen.set).join(timeout=5)
    assert gelaufen.is_set()
    assert codes == []


def test_argumente_und_name_kommen_an(monkeypatch):
    beenden_abfangen(monkeypatch)
    erhalten: list = []
    faden = dienst.faden_starten(lambda a, b: erhalten.append((a, b)), 1, 2, name="x")
    faden.join(timeout=5)
    assert erhalten == [(1, 2)]
    assert faden.name == "x"
    assert faden.daemon
