import struct
from array import array

from diktat import (
    MAX_S,
    OHNE_SPRACHE_S,
    STILLE_S,
    Aufnahme,
    antwort_text,
    braucht_modell,
    formular,
    pegel_db,
    suchbegriff,
    suchbegriff_pruefen,
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


def test_neuer_start_weckt_altes_ergebnis_und_zaehlt_weiter():
    # verifier zu #72: Ein zweites Diktat (Seite neu geladen) darf den Ton nicht an ein
    # veraltetes „ergebnis“ verlieren. Die Nummer zeigt dem alten, dass es leer ausgeht.
    a = Aufnahme(RATE)
    erste = a.start()
    assert not a.fertig.is_set()
    zweite = a.start()
    assert zweite == erste + 1
    assert a.aktiv and not a.fertig.is_set()


# Suchbegriff: das Modell urteilt, der Code prüft (suchbegriff_pruefen)


def test_kurzer_text_braucht_kein_modell():
    assert not braucht_modell("Queen")
    assert not braucht_modell("Bohemian Rhapsody Queen")
    assert braucht_modell("spiel mir was von Queen")


def test_kurzer_text_geht_ohne_anfrage_durch():
    # Ohne Netz und mit falschem Schlüssel: kommt keine Anfrage, kommt auch kein Fehler.
    assert suchbegriff("Die Ärzte", "kein-schluessel") == "Die Ärzte"


def test_begriff_aus_dem_satz_gilt():
    assert suchbegriff_pruefen("Spiel mir was von Queen.", "Queen") == "Queen"


def test_anfuehrungszeichen_und_punkt_fallen_weg():
    assert suchbegriff_pruefen("such mal nach Queen", "„Queen“.") == "Queen"


def test_leere_antwort_laesst_das_gesagte_stehen():
    assert (
        suchbegriff_pruefen("spiel mir was von Queen", "  ")
        == "spiel mir was von Queen"
    )


def test_erfundener_begriff_laesst_das_gesagte_stehen():
    gesagt = "spiel mir was von Queen"
    assert suchbegriff_pruefen(gesagt, "ABBA") == gesagt


def test_zu_lange_oder_mehrzeilige_antwort_laesst_das_gesagte_stehen():
    gesagt = "spiel mir was von Queen"
    assert suchbegriff_pruefen(gesagt, "Queen " * 20) == gesagt
    assert suchbegriff_pruefen(gesagt, "Queen\nDas ist eine Band.") == gesagt


def test_gross_und_kleinschreibung_zaehlt_beim_vergleich_nicht():
    assert suchbegriff_pruefen("spiel was von queen", "Queen") == "Queen"


def test_antwort_text_liest_die_nachricht():
    antwort = {
        "output": [
            {"type": "reasoning", "summary": []},
            {
                "type": "message",
                "content": [{"type": "output_text", "text": "Queen"}],
            },
        ]
    }
    assert antwort_text(antwort) == "Queen"


def test_antwort_ohne_nachricht_ist_leer():
    assert antwort_text({"output": []}) == ""
    assert antwort_text({}) == ""
