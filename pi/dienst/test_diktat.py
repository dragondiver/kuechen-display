import struct
from array import array

from diktat import (
    MAX_S,
    OHNE_SPRACHE_S,
    STILLE_S,
    Aufnahme,
    formular,
    pegel_db,
    wav,
)

RATE = 16000
RAHMEN = 960  # 60 ms


def rahmen(amplitude: int) -> bytes:
    """Ein 60-ms-Rahmen Rechteck mit dieser Amplitude (Pegel = 20*log10(a/32768))."""
    return array("h", [amplitude, -amplitude] * (RAHMEN // 2)).tobytes()


def fuettern(a: Aufnahme, amplitude: int, sekunden: float) -> None:
    for _ in range(round(sekunden / 0.06)):
        a.rahmen(rahmen(amplitude))


LEISE, LAUT = 30, 3000  # etwa -61 dB und -21 dB, also 40 dB Abstand


def test_pegel_db():
    assert pegel_db(rahmen(32767)) > -0.01
    assert abs(pegel_db(rahmen(3277)) + 20) < 0.1
    assert pegel_db(rahmen(0)) == -100.0


def test_aufnahme_nimmt_nur_auf_wenn_aktiv():
    a = Aufnahme(RATE)
    a.rahmen(rahmen(LEISE))
    a.start()
    a.rahmen(rahmen(LEISE))
    assert a.nehmen() == rahmen(LEISE)
    a.rahmen(rahmen(LEISE))
    assert a.nehmen() == b""


def test_endet_nach_sprache_und_der_pause():
    a = Aufnahme(RATE)
    a.start()
    fuettern(a, LEISE, 0.5)
    fuettern(a, LAUT, 1.2)
    assert a.aktiv and a.sprache
    fuettern(a, LEISE, STILLE_S - 0.12)
    assert a.aktiv
    fuettern(a, LEISE, 0.24)
    assert not a.aktiv and a.grund == "Ruhe" and a.fertig.is_set()


def test_kurze_pause_mitten_im_satz_beendet_nicht():
    a = Aufnahme(RATE)
    a.start()
    fuettern(a, LEISE, 0.5)
    fuettern(a, LAUT, 0.6)
    fuettern(a, LEISE, STILLE_S - 0.5)  # Stocken mitten im Satz
    fuettern(a, LAUT, 0.6)
    assert a.aktiv


def test_klappern_zaehlt_nicht_als_sprache():
    a = Aufnahme(RATE)
    a.start()
    fuettern(a, LEISE, 0.5)
    for _ in range(10):
        a.rahmen(rahmen(LAUT))  # ein Rahmen laut, dann wieder leise
        fuettern(a, LEISE, 0.3)
    assert not a.sprache


def test_ohne_sprache_ende_nach_frist():
    a = Aufnahme(RATE)
    a.start()
    fuettern(a, LEISE, OHNE_SPRACHE_S + 0.1)
    assert not a.aktiv and a.grund == "keine Sprache"


def test_dauerton_endet_nach_max_s():
    a = Aufnahme(RATE)
    a.start()
    fuettern(a, LEISE, 0.3)
    fuettern(a, LAUT, MAX_S + 1)
    assert not a.aktiv and a.grund == "max"
    assert a.sekunden(a.nehmen()) == MAX_S


def test_tipp_beendet_und_weckt_den_wartenden():
    a = Aufnahme(RATE)
    a.start()
    assert not a.fertig.is_set()
    a.beenden("Tipp")
    assert a.fertig.is_set() and a.grund == "Tipp"


def test_neuer_start_verwirft_alten_ton():
    a = Aufnahme(RATE)
    a.start()
    a.rahmen(rahmen(LEISE))
    a.start()
    assert a.nehmen() == b""


def test_wav_kopf():
    w = wav(b"\x00\x00" * 160, 16000)
    assert w[:4] == b"RIFF" and w[8:16] == b"WAVEfmt "
    kanaele, rate = struct.unpack("<HI", w[22:28])
    assert (kanaele, rate) == (1, 16000)
    assert struct.unpack("<I", w[40:44])[0] == 320
    assert len(w) == 44 + 320


def test_formular_hat_felder_und_datei():
    rumpf, art = formular(
        [("model", "gpt-transcribe"), ("languages[]", "de")], b"WAVDATEN"
    )
    grenze = art.split("boundary=")[1]
    assert rumpf.startswith(f"--{grenze}\r\n".encode())
    assert rumpf.endswith(f"--{grenze}--\r\n".encode())
    assert b'name="model"\r\n\r\ngpt-transcribe\r\n' in rumpf
    assert b'name="languages[]"\r\n\r\nde\r\n' in rumpf
    assert (
        b'name="file"; filename="diktat.wav"\r\nContent-Type: audio/wav\r\n\r\nWAVDATEN\r\n'
        in rumpf
    )
