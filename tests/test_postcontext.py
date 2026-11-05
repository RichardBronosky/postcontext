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


def test_reuses_own_tab_when_label_switch_fails(monkeypatch):
    from postcontext.browser import Browser, BrowserError

    b = Browser(session="t")
    b.scripts = None
    calls = []

    def fake_ab(*args, timeout=60):
        calls.append(args)
        if args[0] == "tab":
            raise BrowserError("agent-browser tab: No tab with label `postcontext`")
        return ""

    monkeypatch.setattr(b, "_ab", fake_ab)
    monkeypatch.setattr(b, "_pages", lambda: [])
    monkeypatch.setattr(b, "_own_tab_alive", lambda: True)
    b.start("https://www.instagram.com/p/x/")
    assert calls[-1] == ("open", "https://www.instagram.com/p/x/") and b.started


def test_points_to_bio():
    from postcontext.biolink import points_to_bio
    assert points_to_bio("It's at 7 p.m. Monday. Tap the link in our bio for details. 🔗")
    assert points_to_bio("Tickets available now — link in bio")
    assert points_to_bio("RSVP in bio!")
    assert not points_to_bio("Proof of life")
    assert not points_to_bio("My bio is a lie")


def test_best_entry_matches_headline():
    from postcontext.biolink import best_entry
    entries = [{"title": "Celebrating America 250 in Hancock County | Sponsored", "url": "a"},
               {"title": "Niki Davis-Fainbloom releases ‘Fetish’ book | Events | nola.com", "url": "b"},
               {"title": "Gambit's Thumbs Up for Nov. 2 | Thumbs Up Down | nola.com", "url": "c"}]
    post = ("Niki Davis-Fainbloom isn’t your average sex educator ... releasing her first book, “Fetish” "
            "Niki Davis-Fainbloom releases ‘Fetish’ book and offers Kissing workshops in New Orleans")
    match, score = best_entry(entries, post)
    assert match["url"] == "b" and score >= 0.5
    assert best_entry(entries, "Unrelated post about pizza")[0] is None


def test_link_lists_and_clean_urls():
    from postcontext.biolink import clean_url, is_link_list
    assert is_link_list("http://linktr.ee/gambitneworleans?utm_source=ig") and not is_link_list("https://nola.com/x")
    assert clean_url("http://linktr.ee/x?utm_source=ig&fbclid=abc&id=3") == "http://linktr.ee/x?id=3"
