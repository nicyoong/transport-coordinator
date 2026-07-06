import pytest

from main import main, parse_args


@pytest.mark.parametrize("duty", ["pickup", "dropoff", "both"])
def test_parse_args_accepts_duty(duty):
    assert parse_args([duty]).duty == duty


def test_parse_args_defaults_to_both():
    assert parse_args([]).duty == "both"


def test_parse_args_rejects_unknown_duty():
    with pytest.raises(SystemExit):
        parse_args(["delivery"])


def test_main_help_prints_help_without_api_key(monkeypatch, capsys):
    monkeypatch.setattr("sys.argv", ["main.py", "help"])
    monkeypatch.delenv("GOOGLE_MAPS_API_KEY", raising=False)

    main()

    output = capsys.readouterr().out
    assert "duties:" in output
    assert "pickup" in output
    assert "transport_plan_pickup.json" in output
