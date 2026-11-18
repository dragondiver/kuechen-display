"""„Kein Netz“ (#50): Standardroute aus /proc/net/route und das Entprellen."""

from netz import Netz, hat_route

KOPF = "Iface\tDestination\tGateway \tFlags\tRefCnt\tUse\tMetric\tMask\t\tMTU\tWindow\tIRTT\n"
MIT_ROUTE = (
    KOPF
    + "wlan0\t00000000\t0100A8C0\t0003\t0\t0\t600\t00000000\t0\t0\t0\n"
    + "wlan0\t0000A8C0\t00000000\t0001\t0\t0\t600\t00FFFFFF\t0\t0\t0\n"
)
OHNE_ROUTE = KOPF + "wlan0\t0000A8C0\t00000000\t0001\t0\t0\t600\t00FFFFFF\t0\t0\t0\n"


def test_standardroute_ueber_gateway_zaehlt():
    assert hat_route(MIT_ROUTE) is True


def test_nur_das_lokale_netz_ist_keine_route():
    assert hat_route(OHNE_ROUTE) is False


def test_leere_oder_kaputte_tabelle_ist_keine_route():
    assert hat_route("") is False
    assert hat_route(KOPF) is False
    assert hat_route(KOPF + "muell\n") is False


def test_route_ohne_up_flag_zaehlt_nicht():
    assert hat_route(KOPF + "wlan0\t00000000\t0100A8C0\t0002\t0\t0\t600\n") is False


def test_erst_der_zweite_befund_meldet_kein_netz():
    n = Netz()
    assert n.pruefen(False) is None
    assert n.pruefen(False) is False


def test_kurzes_wackeln_meldet_nichts():
    n = Netz()
    assert n.pruefen(False) is None
    assert n.pruefen(True) is None
    assert n.pruefen(False) is None


def test_netz_kommt_zurueck_und_wird_gemeldet():
    n = Netz()
    n.pruefen(False)
    n.pruefen(False)
    assert n.pruefen(True) is None
    assert n.pruefen(True) is True


def test_gleicher_zustand_meldet_nichts_mehr():
    n = Netz()
    assert [n.pruefen(True) for _ in range(3)] == [None, None, None]
    n.pruefen(False)
    n.pruefen(False)
    assert n.pruefen(False) is None


def test_nicht_lesbare_datei_gilt_als_netz_da():
    n = Netz()
    assert n.pruefen(None) is None
    assert n.pruefen(None) is None
