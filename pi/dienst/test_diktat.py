import struct

from diktat import MAX_S, Aufnahme, formular, wav


def test_aufnahme_nimmt_nur_auf_wenn_aktiv():
    a = Aufnahme(16000)
    a.rahmen(b"\x01\x00" * 10)
    a.start()
    a.rahmen(b"\x02\x00" * 10)
    assert a.stopp() == b"\x02\x00" * 10
    a.rahmen(b"\x03\x00" * 10)
    assert a.stopp() == b""


def test_aufnahme_endet_nach_max_s():
    a = Aufnahme(1000)
    a.start()
    for _ in range(int(MAX_S) + 3):
        a.rahmen(b"\x00\x00" * 1000)  # eine Sekunde
    assert not a.aktiv
    assert a.sekunden(a.stopp()) == MAX_S


def test_neuer_start_verwirft_alten_ton():
    a = Aufnahme(16000)
    a.start()
    a.rahmen(b"\x01\x00" * 5)
    a.start()
    assert a.stopp() == b""


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
