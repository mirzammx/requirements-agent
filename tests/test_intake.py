from bidtriage.intake import alert_name, classify_mail, load_intake_settings
from bidtriage.models import Attachment, Bid

SETTINGS = {"screen_alerts": ["Power supply"], "mahadevan_email": "m@rugrel.com", "signature": "S"}


def bid_with(*names):
    return Bid(subject="s", sender="f", date="d", body="b",
               attachments=[Attachment(n, b"x", "") for n in names])


def test_settings_defaults_when_file_missing(tmp_path):
    s = load_intake_settings(tmp_path / "missing.toml")
    assert s["screen_alerts"] == ["Power supply"]
    assert s["mahadevan_email"] == "mahadevan.velvalli@rugrel.com"
    assert "Mahadevan" in s["signature"]


def test_settings_file_overrides(tmp_path):
    p = tmp_path / "intake.toml"
    p.write_text('screen_alerts = ["Power supply", "Railway"]\n', encoding="utf-8")
    assert load_intake_settings(p)["screen_alerts"] == ["Power supply", "Railway"]


def test_alert_name_from_bidassist_file():
    assert alert_name("Power supply-Tender List_26092026.xlsx") == "Power supply"
    assert alert_name("My Preference-Tender List_26092026.xlsx") == "My Preference"
    assert alert_name("RFQ_TenderDocument.pdf") is None


def test_bidassist_mail_screens_only_configured_alert():
    kind, screen, ignored = classify_mail(bid_with("Power supply-Tender List_26092026.xlsx",
                                                   "My Preference-Tender List_26092026.xlsx"), SETTINGS)
    assert kind == "bidassist"
    assert [a.filename for a in screen] == ["Power supply-Tender List_26092026.xlsx"]
    assert ignored == ["My Preference-Tender List_26092026.xlsx"]


def test_bidassist_mail_without_configured_alert_screens_nothing():
    kind, screen, ignored = classify_mail(bid_with("My Preference-Tender List_26092026.xlsx"), SETTINGS)
    assert kind == "bidassist" and screen == [] and ignored == ["My Preference-Tender List_26092026.xlsx"]


def test_alert_match_ignores_case_and_spacing():
    kind, screen, _ = classify_mail(bid_with("power  SUPPLY-Tender List_01102026.xlsx"), SETTINGS)
    assert kind == "bidassist" and len(screen) == 1


def test_ordinary_bid_mail():
    kind, screen, ignored = classify_mail(bid_with("RFQ_TenderDocument_PSMAHRU.pdf", "PriceBid.pdf"), SETTINGS)
    assert kind == "bid" and screen == [] and ignored == []
