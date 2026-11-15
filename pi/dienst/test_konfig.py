from konfig import geheimnis


def test_umgebung_geht_vor_der_datei(tmp_path):
    datei = tmp_path / "token"
    datei.write_text("aus-der-datei\n")
    assert (
        geheimnis("HA_TOKEN", datei, {"HA_TOKEN": " aus-der-umgebung "})
        == "aus-der-umgebung"
    )


def test_ohne_variable_gilt_die_datei(tmp_path):
    datei = tmp_path / "token"
    datei.write_text("aus-der-datei\n")
    assert geheimnis("HA_TOKEN", datei, {}) == "aus-der-datei"


def test_leere_variable_zaehlt_nicht(tmp_path):
    datei = tmp_path / "token"
    datei.write_text("aus-der-datei")
    assert geheimnis("HA_TOKEN", datei, {"HA_TOKEN": "  "}) == "aus-der-datei"


def test_nichts_da_gibt_none(tmp_path):
    assert geheimnis("HA_TOKEN", tmp_path / "fehlt", {}) is None
    leer = tmp_path / "leer"
    leer.write_text("\n")
    assert geheimnis("HA_TOKEN", leer, {}) is None
