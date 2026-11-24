"""Draws `title.png`, the Sound Journal title card: the JMH shield monogram over
"Sound Journal", white on transparent, as title.py lays it over the cockpit.

The monogram is Crepitus-monogram.ttf's discretionary ligature for "1jMh" (Jeff's OBS
overlay drew it so). With that font beside this script it is drawn from the font; without
it, from the outline traced below, which stands in for it. The words are Ubuntu Light
(Ubuntu Font Licence, `UFL.txt`), as in the OBS overlay.

    python3 make_title.py            # writes title.png
"""
import os
import sys

from PIL import Image, ImageChops, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
MONOGRAM_FONT = os.path.join(HERE, "Crepitus-monogram.ttf")
WORDS_FONT = os.path.join(HERE, "Ubuntu-Light.ttf")
WORDS = os.environ.get("WORDS", "Sound Journal")

W, H = 1200, 900            # the card, in pixels: 1.5x what it covers on a 1080p canvas
SHIELD_H = 400              # the monogram's height
WORDS_PX = 118              # the words' size
GAP = 70                    # from the shield's point to the words' cap height
WHITE = (255, 255, 255, 255)


def monogram_from_font(height):
    """The monogram from its font, cropped to its ink, `height` pixels tall."""
    size = height * 2
    font = ImageFont.truetype(MONOGRAM_FONT, size)
    img = Image.new("L", (size * 3, size * 2), 0)
    ImageDraw.Draw(img).text((size // 2, size // 2), "1jMh", font=font, fill=255,
                             features=["dlig"])
    img = img.crop(img.getbbox())
    w = round(img.width * height / img.height)
    return img.resize((w, height), Image.LANCZOS)


# The traced stand-in: a shield 350 x 425 units, its border 18 thick, and the three letters
# filling it, each cut off by the shield's inner edge.
S_W, S_H = 350, 425


def _shield(d, inset, fill):
    """The shield's outline, `inset` units inside the outer edge: straight sides down to
    58% of the height, then bowing out and in to the point."""
    l, r, t = inset, S_W - inset, inset
    knee = S_H * 0.58
    tip = (S_W / 2, S_H - inset * 1.3)
    n = 32
    right = [(r - (r - tip[0]) * (i / n) ** 1.7, knee + (tip[1] - knee) * i / n) for i in range(n + 1)]
    left = [(S_W - x, y) for x, y in reversed(right)]
    d.polygon([(l, t), (r, t)] + right + left, fill=fill)


def _letters(d):
    top = 24
    bot = S_H
    # J: a stem whose foot bends round to the left and up into a short hook.
    d.rectangle((88, top, 123, 268), fill=255)
    d.arc((20, 200, 123, 336), 0, 180, fill=255, width=35)
    d.rectangle((20, 212, 55, 268), fill=255)
    # M: two stems, and a wedge hanging between them, apart from each by a hairline.
    d.rectangle((137, top, 166, bot), fill=255)
    d.rectangle((194, top, 223, bot), fill=255)
    d.polygon([(168, top), (192, top), (180, 176)], fill=255)
    # H: two stems and the bar.
    d.rectangle((239, top, 270, bot), fill=255)
    d.rectangle((296, top, 330, bot), fill=255)
    d.rectangle((270, 128, 296, 156), fill=255)


def monogram_traced(height):
    k = 4                               # drawn at 4x and scaled down, for smooth edges
    big = Image.new("L", (S_W * k, S_H * k), 0)
    outer = Image.new("L", (S_W, S_H), 0)
    _shield(ImageDraw.Draw(outer), 0, 255)
    inner = Image.new("L", (S_W, S_H), 0)
    _shield(ImageDraw.Draw(inner), 18, 255)
    letters = Image.new("L", (S_W, S_H), 0)
    _letters(ImageDraw.Draw(letters))
    inner_gap = Image.new("L", (S_W, S_H), 0)
    _shield(ImageDraw.Draw(inner_gap), 30, 255)
    # The border, then the letters inside a gap from it.
    border = ImageChops.subtract(outer, inner)
    ink = ImageChops.lighter(border, ImageChops.multiply(letters, inner_gap))
    big = ink.resize((S_W * k, S_H * k), Image.LANCZOS)
    w = round(S_W * height / S_H)
    return big.resize((w, height), Image.LANCZOS)


def main():
    have_font = os.path.exists(MONOGRAM_FONT)
    mono = monogram_from_font(SHIELD_H) if have_font else monogram_traced(SHIELD_H)
    words = ImageFont.truetype(WORDS_FONT, WORDS_PX)
    card = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    bb = ImageDraw.Draw(card).textbbox((0, 0), WORDS, font=words)
    block = SHIELD_H + GAP + (bb[3] - bb[1])
    y0 = (H - block) // 2
    white = Image.new("RGBA", mono.size, WHITE)
    card.paste(white, ((W - mono.width) // 2, y0), mono)
    ImageDraw.Draw(card).text(((W - (bb[2] - bb[0])) / 2 - bb[0], y0 + SHIELD_H + GAP - bb[1]),
                              WORDS, font=words, fill=WHITE)
    out = os.path.join(HERE, "title.png")
    card.save(out)
    print("wrote", out, "(monogram from", "Crepitus-monogram.ttf)" if have_font else "the traced stand-in)",
          file=sys.stderr)


if __name__ == "__main__":
    main()
