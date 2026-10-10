"""Loading backgrounds cannot satisfy main-menu preparation acceptance."""

import pytest
from PIL import Image, ImageDraw

from gamecua.games.art_of_rally.ui import menu_match, title_match


def reference():
    image = Image.new("RGB", (1280, 720), (255, 241, 220))
    draw = ImageDraw.Draw(image)
    draw.rectangle((100, 100, 200, 110), fill="black")
    draw.rectangle((100, 245, 180, 250), fill="black")
    return image


def test_title_and_menu_both_required():
    expected = reference()
    assert menu_match(expected, expected)[0]
    blank = Image.new("RGB", expected.size, (255, 241, 220))
    assert not menu_match(blank, expected)[0]
    assert not menu_match(Image.new("RGB", expected.size, "black"), expected)[0]
    title_only = expected.copy()
    ImageDraw.Draw(title_only).rectangle((90, 235, 350, 325), fill=(255, 241, 220))
    assert not menu_match(title_only, expected)[0]


def test_antialiased_menu_text_requires_visible_contrast():
    expected = reference()
    ImageDraw.Draw(expected).rectangle((100, 245, 180, 250), fill=(140, 140, 140))
    assert menu_match(expected, expected)[0]
    missing = expected.copy()
    ImageDraw.Draw(missing).rectangle((90, 235, 350, 325), fill=(255, 241, 220))
    assert not menu_match(missing, expected)[0]


@pytest.mark.parametrize("background", [(30, 60, 40), (245, 110, 75)])
def test_title_recognition_rejects_blank_and_black_frames(background):
    image = Image.new("RGB", (1280, 720), background)
    draw = ImageDraw.Draw(image)
    draw.rectangle((80, 580, 320, 590), fill="white")
    draw.rectangle((80, 640, 320, 650), fill="white")
    assert title_match(image, image)
    for color in ("black", (255, 241, 220)):
        assert not title_match(Image.new("RGB", image.size, color), image)
