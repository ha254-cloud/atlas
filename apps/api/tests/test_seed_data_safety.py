import pytest


def test_demo_seed_is_disabled_in_production(monkeypatch):
    import seed
    from app.core.config import settings

    monkeypatch.setattr(settings, "APP_ENV", "production")

    with pytest.raises(RuntimeError, match="disabled in production"):
        seed.seed()


def test_demo_seed_uses_kenya_payers_only():
    import seed

    names = {payer["name"] for payer in seed.PAYERS}
    codes = {payer["payer_code"] for payer in seed.PAYERS}

    assert names == {
        "AAR Insurance Kenya",
        "Britam General Insurance",
        "CIC General Insurance",
        "Jubilee Health Insurance",
        "Social Health Authority",
    }
    assert codes == {"AAR", "BRITAM", "CIC", "JUBILEE", "SHA"}
