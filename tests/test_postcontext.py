from postcontext import social
from postcontext.media import _clean_ocr, dedupe_texts


def test_parse_instagram_description():
    d = social.parse_ig_description('235 likes, 39 comments - ella_ruth_ on October 11, 2026: "Proof of life". ')
    assert d == {"stats": "235 likes, 39 comments", "author": "ella_ruth_", "date": "October 11, 2026",
                 "caption": "Proof of life"}
    assert social.parse_ig_description("580 likes, 6 comments - abohren14 on October 23, 2026")["author"] == "abohren14"


def test_url_routing():
    assert social.handles("https://www.instagram.com/p/x/") and social.handles("https://fb.watch/abc")
    assert not social.handles("https://example.com/instagram.com")
    assert social.IG_POST.search("https://www.instagram.com/reels/DePtR8jgPFE/").group(1) == "reels"
    assert social.IG_PROFILE.search("https://www.instagram.com/teddy_lamson").group(1) == "teddy_lamson"


def test_browser_disabled_returns_none():
    assert social.fetch("https://www.instagram.com/p/x/") is None


def test_dedupe_frame_texts():
    assert dedupe_texts(["STEP 1 Audit", "STEP 1 Audit.", "", "STEP 2 Plan"]) == ["STEP 1 Audit", "STEP 2 Plan"]


def test_clean_ocr_drops_noise():
    assert _clean_ocr("‘4 How | keep up\n~~ .. ~\nwd\nSTEP 1") == "‘4 How | keep up\nSTEP 1"
