"""Threads in main() (#122): Eine Ausnahme beendet den Prozess, ein reguläres Ende nicht."""

import logging
import threading

import dienst


def beenden_abfangen(monkeypatch):
    codes: list[int] = []
    monkeypatch.setattr(dienst.os, "_exit", codes.append)
    return codes


def test_ausnahme_beendet_den_prozess_und_nennt_den_thread(monkeypatch, caplog):
    codes = beenden_abfangen(monkeypatch)

    def kaputt():
        raise ValueError("falsch geformt")

    with caplog.at_level(logging.ERROR):
        dienst.thread_starten(kaputt).join(timeout=5)
    assert codes == [1]
    assert "kaputt" in caplog.text
    assert "falsch geformt" in caplog.text  # Traceback steht im Journal


def test_regulaeres_ende_laesst_den_prozess_leben(monkeypatch):
    codes = beenden_abfangen(monkeypatch)
    gelaufen = threading.Event()
    dienst.thread_starten(gelaufen.set).join(timeout=5)
    assert gelaufen.is_set()
    assert codes == []


def test_argumente_und_name_kommen_an(monkeypatch):
    beenden_abfangen(monkeypatch)
    erhalten: list = []
    thread = dienst.thread_starten(lambda a, b: erhalten.append((a, b)), 1, 2, name="x")
    thread.join(timeout=5)
    assert erhalten == [(1, 2)]
    assert thread.name == "x"
    assert thread.daemon


def popen_fehlt(*args, **kw):
    raise FileNotFoundError(2, "No such file", args[0][0])


def test_fehlende_programme_geben_nur_eine_warnung_und_neue_versuche(
    monkeypatch, caplog
):
    codes = beenden_abfangen(monkeypatch)
    monkeypatch.setattr(dienst.subprocess, "Popen", popen_fehlt)
    for schleife, programm in (
        (dienst.mikro_schleife, "arecord"),
        (dienst.wiedergabe_schleife, "pw-cat"),
    ):
        pausen = []
        caplog.clear()
        with caplog.at_level(logging.WARNING):
            schleife(
                weiter=lambda p=pausen: len(p) < 3, warten=pausen.append
            )  # drei Versuche, dann Schluss
        assert pausen == [2, 2, 2]
        assert caplog.text.count(f"{programm} startet nicht") == 1
    assert codes == []


def test_andere_popen_fehler_gehen_an_den_wrapper(monkeypatch):
    codes = beenden_abfangen(monkeypatch)

    def kaputt(*args, **kw):
        raise RuntimeError("anderes")

    monkeypatch.setattr(dienst.subprocess, "Popen", kaputt)
    dienst.thread_starten(dienst.mikro_schleife, name="mikro").join(timeout=5)
    assert codes == [1]
