"""Draws app.ico: a small title bar with a hanging ribbon. Drawn from shapes, no game art.

    python make_icon.py
"""
from PIL import Image, ImageDraw, ImageFilter

S = 1024


def lerp(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(len(a)))


def vgrad(w, h, top, bottom):
    g = Image.new("RGBA", (w, h))
    d = ImageDraw.Draw(g)
    for y in range(h):
        d.line([(0, y), (w, y)], fill=lerp(top, bottom, y / max(1, h - 1)))
    return g


def main():
    img = Image.new("RGBA", (S, S), (0, 0, 0, 0))

    # ribbon: a sagging band under the bar, white with a red disc
    rib = Image.new("L", (S, S), 0)
    rd = ImageDraw.Draw(rib)
    rd.polygon([(170, 520), (854, 520), (800, 700), (640, 790), (384, 790), (224, 700)], fill=255)
    rib = rib.filter(ImageFilter.GaussianBlur(3))
    cloth = vgrad(S, S, (250, 250, 245, 255), (175, 178, 185, 255))
    disc = ImageDraw.Draw(cloth)
    disc.ellipse((432, 560, 592, 720), fill=(196, 30, 46, 255))
    shade = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    sd = ImageDraw.Draw(shade)
    for i, x in enumerate(range(170, 854, 76)):
        sd.line([(x, 520), (x + 40, 790)], fill=(0, 0, 0, 38 if i % 2 else 0), width=34)
    cloth.alpha_composite(shade.filter(ImageFilter.GaussianBlur(14)))
    img.paste(cloth, (0, 0), rib)

    # bar: dark field inside a steel rim
    bar = Image.new("L", (S, S), 0)
    ImageDraw.Draw(bar).rounded_rectangle((60, 300, 964, 560), radius=110, fill=255)
    rim = vgrad(S, S, (215, 222, 235, 255), (95, 104, 125, 255))
    img.paste(rim, (0, 0), bar)
    inner = Image.new("L", (S, S), 0)
    ImageDraw.Draw(inner).rounded_rectangle((100, 334, 924, 526), radius=84, fill=255)
    field = vgrad(S, S, (70, 82, 70, 255), (24, 28, 26, 255))
    img.paste(field, (0, 0), inner)

    # boss on top of the bar
    d = ImageDraw.Draw(img)
    d.ellipse((432, 236, 592, 364), fill=(120, 130, 152, 255), outline=(225, 230, 240, 255), width=14)

    img = img.resize((256, 256), Image.LANCZOS)
    img.save("app.ico", sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    img.save("docs/icon.png")


if __name__ == "__main__":
    import os
    os.makedirs("docs", exist_ok=True)
    main()
