#!/usr/bin/env python3
"""Flag ribbons under joint / collaborative focuses for Hearts of Iron IV, made like vanilla's joint title bars.

Reads vanilla's Turkish joint bars (focus_<state>_joint_TUR_bg.dds) from your game install and re-dyes their hanging
ribbon, so the folds, shadow and frame stay vanilla's. No vanilla file is shipped with this tool.

  Shared style:  one big ribbon (--shared): stars, a whole flag, or a flag cropped to its emblem.
  Nation styles: the big ribbon removed, a narrow ribbon with the country's flag in the middle of the bar (--nation).

Writes into --mod:
  gfx/interface/focusview/titlebar/focus_<state>_joint_<PREFIX>[_<TAG>]_bg.dds
  interface/<prefix>_titlebars.gfx
  common/national_focus/<prefix>_titlebar_styles.txt

  Group styles:  several flags side by side on one ribbon, with rivets between, like vanilla's BEL_COG (--group).

Then in a focus:   text_icon = <PREFIX>_focus_style   or   text_icon = <PREFIX>_<TAG>_focus_style   (or _<GROUP>_)

Example:
  python joint_titlebars.py --game "D:/SteamLibrary/steamapps/common/Hearts of Iron IV" --mod "path/to/my_mod" --prefix MYA
      --shared stars --nation GER=GER_fascism ITA=ITA_fascism --preview preview.png

Needs Python 3.9+ and Pillow (pip install pillow). See README.md."""
import argparse
import math
from pathlib import Path
import sys

from PIL import Image, ImageDraw

STATES = ('can_start', 'completed', 'unavailable')
TOP = 48          # bars are 164x69: rows 0-47 are the frame, rows 48+ hold the ribbon and its black shadow
FLAG_EXT = ('.tga', '.png', '.dds')


class Tool:
    def __init__(self, game, mod, prefix, narrow=0.42, rivets=True):
        self.game, self.mod, self.prefix, self.narrow, self.rivets = Path(game), Path(mod), prefix, narrow, rivets
        self.title = self.game / 'gfx/interface/focusview/titlebar'
        if not (self.title / 'focus_can_start_joint_TUR_bg.dds').is_file():
            sys.exit(f'Not a Hearts of Iron IV install with the joint title bars: {self.game}')

    # ---------------------------------------------------------------- vanilla parts
    def _bar(self, state):
        return _img(self.title / f'focus_{state}_joint_TUR_bg.dds')

    def _ribbon(self, state):
        """the Turkish bar, its ribbon pixels {(x, y): fold shade} and each ribbon column's (top, bottom)"""
        tur = self._bar(state)
        t = tur.load()
        shade, white = {}, set()
        for x in range(tur.width):
            for y in range(TOP, tur.height):
                r, g, b, a = t[x, y]
                if a and (r or g or b):
                    if g > 110:                  # crescent and star have no red to read the folds from
                        white.add((x, y))
                    else:
                        shade[(x, y)] = r / 175.0
        for (x, y) in white:
            left = next((shade[(xx, y)], x - xx) for xx in range(x - 1, -1, -1) if (xx, y) in shade)
            right = next((shade[(xx, y)], xx - x) for xx in range(x + 1, tur.width) if (xx, y) in shade)
            shade[(x, y)] = (left[0] * right[1] + right[0] * left[1]) / (left[1] + right[1])
        cols = {}
        for (x, y) in shade:
            lo, hi = cols.get(x, (y, y))
            cols[x] = (min(lo, y), max(hi, y))
        return tur, shade, cols

    def _frame(self, state):
        """the bar without anything below the frame"""
        tur = self._bar(state)
        tur.paste((0, 0, 0, 0), (0, TOP, tur.width, tur.height))
        return tur

    def _drape(self, state, canvas):
        """the ribbon rows of the Turkish bar with canvas mapped into the ribbon"""
        tur, shade, cols = self._ribbon(state)
        t = tur.load()
        x0, x1 = min(cols), max(cols)
        canvas = canvas.convert('RGBA').resize((x1 - x0 + 1, _height(cols)), Image.LANCZOS)
        cp = canvas.load()
        out = Image.new('RGBA', tur.size, (0, 0, 0, 0))
        o = out.load()
        for x in range(tur.width):
            for y in range(TOP, tur.height):
                r, g, b, a = t[x, y]
                if not a:
                    continue
                if (x, y) not in shade:          # the shadow
                    o[x, y] = (r, g, b, a)
                    continue
                lo, hi = cols[x]
                v = (y - lo + 0.5) / (hi - lo + 1)
                fr, fg, fb, _ = cp[x - x0, min(canvas.height - 1, int(v * canvas.height))]
                s = max(0.1, min(1.7, shade[(x, y)]))
                o[x, y] = (min(255, int(fr * s)), min(255, int(fg * s)), min(255, int(fb * s)), a)
        return out, x0, x1

    def _rivet(self, state):
        """the round rivet between two flags of vanilla's four-flag bar"""
        src = _img(self.title / f'focus_{state}_joint_AFG_IRQ_PER_TUR_bg.dds').crop((77, 46, 88, 57))
        p = src.load()
        for x in range(src.width):
            for y in range(src.height):
                d = ((x - 5) ** 2 + (y - 5) ** 2) ** 0.5
                if d > 5.5:
                    p[x, y] = (0, 0, 0, 0)
                elif d > 4.5:
                    r, g, b, a = p[x, y]
                    p[x, y] = (r, g, b, int(a * (5.5 - d)))
        return src

    def _size(self, state):
        _, _, cols = self._ribbon(state)
        return max(cols) - min(cols) + 1, _height(cols)

    def _on_big_ribbon(self, state, canvas):
        drape, _, _ = self._drape(state, canvas)
        img = self._frame(state)
        img.alpha_composite(drape)
        return img

    # ---------------------------------------------------------------- ribbons
    def flag(self, spec):
        """a flag by file path, or by stem (GER_fascism) from the mod's gfx/flags, then the game's"""
        path = Path(spec)
        if path.is_file():
            return _img(path)
        for root in (self.mod, self.game):
            for ext in FLAG_EXT:
                if (root / 'gfx/flags' / (spec + ext)).is_file():
                    return _img(root / 'gfx/flags' / (spec + ext))
        sys.exit(f'Flag not found: {spec} (give a file path, or a stem from gfx/flags in the mod or the game)')

    def shared_flag(self, state, spec):
        return self._on_big_ribbon(state, self.flag(spec))

    def shared_emblem(self, state, spec):
        """the flag cropped to its emblem, which becomes as tall as the ribbon; the field colour fills the width.
        The field colour is read from the flag's top-left corner, so this suits a flag with one plain field."""
        flag = self.flag(spec)
        field = flag.getpixel((2, 2))
        p = flag.load()
        em = [(x, y) for x in range(flag.width) for y in range(flag.height) if sum(abs(p[x, y][i] - field[i]) for i in range(3)) > 20]
        if not em:
            sys.exit(f'{spec} has no emblem: it is one plain colour')
        emblem = flag.crop((min(x for x, _ in em), min(y for _, y in em), max(x for x, _ in em) + 1, max(y for _, y in em) + 1))
        w, h = self._size(state)
        k = 8
        ew = round(emblem.width * h * k / emblem.height)
        canvas = Image.new('RGBA', (w * k, h * k), field)
        canvas.alpha_composite(emblem.resize((ew, h * k), Image.LANCZOS), ((w * k - ew) // 2, 0))
        return self._on_big_ribbon(state, canvas)

    def shared_stars(self, state, field=(0, 51, 153), gold=(255, 204, 0), count=12):
        """a ring of stars, as tall as the ribbon; the field colour fills the width"""
        w, h = self._size(state)
        k = 8
        canvas = Image.new('RGBA', (w * k, h * k), tuple(field) + (255,))
        draw = ImageDraw.Draw(canvas)
        cx, cy, ring, outer = w * k / 2, h * k / 2, h * k * 0.36, h * k * 0.13
        for i in range(count):
            a = 2 * math.pi * i / count
            sx, sy = cx + ring * math.sin(a), cy - ring * math.cos(a)
            pts = []
            for j in range(10):
                r = outer if j % 2 == 0 else outer * 0.4
                pts.append((sx + r * math.sin(math.pi * j / 5), sy - r * math.cos(math.pi * j / 5)))
            draw.polygon(pts, fill=tuple(gold) + (255,))
        return self._on_big_ribbon(state, canvas)

    def nation(self, state, flag):
        """the big ribbon removed; a narrow ribbon with the flag hanging from the middle of the frame"""
        drape, x0, x1 = self._drape(state, flag)
        strip = drape.crop((x0, TOP, x1 + 1, drape.height))
        nw = round(strip.width * self.narrow)
        strip = strip.convert('RGBa').resize((nw, strip.height), Image.LANCZOS).convert('RGBA')
        img = self._frame(state)
        left = round((x0 + x1) / 2 - (nw - 1) / 2)
        img.alpha_composite(strip, (left, TOP))
        if self.rivets:
            rivet = self._rivet(state)
            for cx in (left + 3, left + nw - 4):
                img.alpha_composite(rivet, (cx - 5, 51 - 5))
        return img

    def group(self, state, flags):
        """several flags side by side across the big ribbon's width, each draped like vanilla's BEL_COG and
        AFG_IRQ_PER_TUR bars, with a rivet where two meet"""
        _, x0, x1 = self._drape(state, flags[0])
        total = x1 - x0 + 1
        n = len(flags)
        img = self._frame(state)
        joins = []
        for i, flag in enumerate(flags):
            drape, a, b = self._drape(state, flag)
            strip = drape.crop((a, TOP, b + 1, drape.height))
            left, right = x0 + round(i * total / n), x0 + round((i + 1) * total / n)
            strip = strip.convert('RGBa').resize((right - left, strip.height), Image.LANCZOS).convert('RGBA')
            img.alpha_composite(strip, (left, TOP))
            if i:
                joins.append(left)
        if self.rivets:
            rivet = self._rivet(state)
            for cx in joins:
                img.alpha_composite(rivet, (cx - 5, 51 - 5))
        return img

    # ---------------------------------------------------------------- output
    def suffix(self, tag=None):
        return f'joint_{self.prefix}_{tag}' if tag else f'joint_{self.prefix}'

    def style(self, tag=None):
        return f'{self.prefix}_{tag}_focus_style' if tag else f'{self.prefix}_focus_style'

    def sprites(self, tag):
        """vanilla's GFX_focus_*_joint_TUR blocks with our names"""
        text = (self.game / 'interface/nationalfocusview.gfx').read_text(encoding='utf-8-sig', errors='ignore')
        try:
            block = text[text.index('\tspriteType = {\n\t\tname = "GFX_focus_unavailable_joint_TUR"'):text.index('### AFG_IRQ_PER_TUR ###')]
        except ValueError:
            sys.exit('interface/nationalfocusview.gfx has changed: the joint_TUR sprite blocks were not found')
        return block.rstrip().replace('joint_TUR', self.suffix(tag)) + '\n'

    def write(self, images, tags):
        tex = self.mod / 'gfx/interface/focusview/titlebar'
        tex.mkdir(parents=True, exist_ok=True)
        for (tag, state), img in images.items():
            path = tex / f'focus_{state}_{self.suffix(tag)}_bg.dds'
            img.save(path)
            back = Image.open(path)
            if back.size != img.size or back.mode != 'RGBA':
                sys.exit(f'{path.name} reopens as {back.size} {back.mode}')
        low = self.prefix.lower()
        gfx = 'spriteTypes = {\n\n' + '\n\n'.join(f'### {self.suffix(t)} ###\n\n' + self.sprites(t) for t in tags) + '\n}\n'
        styles = '\n\n'.join(f'style = {{\n\tname = {self.style(t)}\n\n\tunavailable = GFX_focus_unavailable_{self.suffix(t)}\n'
                             f'\tcompleted = GFX_focus_completed_{self.suffix(t)}\n\tavailable = GFX_focus_can_start_{self.suffix(t)}\n'
                             f'\tcurrent = GFX_focus_current_{self.suffix(t)}\n}}' for t in tags) + '\n'
        for rel, text in ((f'interface/{low}_titlebars.gfx', gfx), (f'common/national_focus/{low}_titlebar_styles.txt', styles)):
            (self.mod / rel).parent.mkdir(parents=True, exist_ok=True)
            (self.mod / rel).write_text(text, encoding='utf-8', newline='\n')


def _img(path):
    return Image.open(path).convert('RGBA')


def _height(cols):
    return max(hi - lo + 1 for lo, hi in cols.values())


def _rgb(text):
    parts = [int(v) for v in text.split(',')]
    if len(parts) != 3:
        sys.exit(f'Colour must be r,g,b: {text}')
    return parts


def preview(path, images, tags, scale=3):
    w, h = 164 * scale, 69 * scale
    sheet = Image.new('RGBA', (len(STATES) * (w + 10) + 10, len(tags) * (h + 10) + 10), (40, 40, 44, 255))
    for j, tag in enumerate(tags):
        for i, state in enumerate(STATES):
            sheet.alpha_composite(images[(tag, state)].resize((w, h), Image.NEAREST), (10 + i * (w + 10), 10 + j * (h + 10)))
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    sheet.convert('RGB').save(path)


def main():
    ap = argparse.ArgumentParser(description='Flag ribbons under joint focuses for Hearts of Iron IV.')
    ap.add_argument('--game', required=True, help='Hearts of Iron IV install folder')
    ap.add_argument('--mod', required=True, help='mod folder to write into (also searched first for flags)')
    ap.add_argument('--prefix', required=True, help='names the textures, sprites and styles, e.g. MYA gives MYA_focus_style')
    ap.add_argument('--shared', default='stars', help='stars | stars:FIELD:GOLD:COUNT (colours as r,g,b) | flag:FLAG | emblem:FLAG | none')
    ap.add_argument('--nation', nargs='*', default=[], metavar='TAG=FLAG', help='one per country: GER=GER_fascism or GER=path/to/flag.tga')
    ap.add_argument('--wide', nargs='*', default=[], metavar='NAME=KIND:FLAG',
                    help='extra wide-ribbon styles besides --shared: MAN=flag:MAN or JAP=emblem:JAP_neutrality')
    ap.add_argument('--group', nargs='*', default=[], metavar='NAME=FLAG,FLAG',
                    help='flags side by side on one ribbon, like vanilla BEL_COG: JAPMAN=JAP_neutrality,MAN (FLAG may be a --nation TAG)')
    ap.add_argument('--narrow', type=float, default=0.42, help='nation ribbon width as a share of the big ribbon (default 0.42)')
    ap.add_argument('--no-rivets', action='store_true', help='no rivets on the nation ribbons')
    ap.add_argument('--preview', help='also save a PNG sheet of every style')
    ap.add_argument('--dry-run', action='store_true', help='make the preview only; write nothing into the mod')
    args = ap.parse_args()

    tool = Tool(args.game, args.mod, args.prefix, args.narrow, not args.no_rivets)
    kind, _, rest = args.shared.partition(':')
    if kind == 'stars':
        parts = rest.split(':') if rest else []
        kw = {}
        if len(parts) > 0 and parts[0]:
            kw['field'] = _rgb(parts[0])
        if len(parts) > 1 and parts[1]:
            kw['gold'] = _rgb(parts[1])
        if len(parts) > 2 and parts[2]:
            kw['count'] = int(parts[2])
        shared = lambda s: tool.shared_stars(s, **kw)
    elif kind == 'flag' and rest:
        shared = lambda s: tool.shared_flag(s, rest)
    elif kind == 'emblem' and rest:
        shared = lambda s: tool.shared_emblem(s, rest)
    elif kind == 'none':
        shared = None
    else:
        sys.exit(f'Unknown --shared value: {args.shared}')
    nations = {}
    for item in args.nation:
        tag, sep, spec = item.partition('=')
        if not sep or not spec:
            sys.exit(f'--nation needs TAG=FLAG: {item}')
        nations[tag] = tool.flag(spec)
    wides = {}
    for item in args.wide:
        name, sep, spec = item.partition('=')
        kind2, _, flag2 = spec.partition(':')
        if not sep or kind2 not in ('flag', 'emblem') or not flag2:
            sys.exit(f'--wide needs NAME=flag:FLAG or NAME=emblem:FLAG: {item}')
        wides[name] = (tool.shared_flag if kind2 == 'flag' else tool.shared_emblem, flag2)
    groups = {}
    specs = {item.partition('=')[0]: item.partition('=')[2] for item in args.nation}
    for item in args.group:
        name, sep, spec = item.partition('=')
        parts = [x for x in spec.split(',') if x]
        if not sep or len(parts) < 2:
            sys.exit(f'--group needs NAME=FLAG,FLAG with at least two flags: {item}')
        groups[name] = [tool.flag(specs.get(x, x)) for x in parts]
    if shared is None and not nations and not groups and not wides:
        sys.exit('Nothing to make: give --shared, --nation or --group')

    tags = ([None] if shared else []) + list(wides) + list(nations) + list(groups)
    images = {}
    for state in STATES:
        if shared:
            images[(None, state)] = shared(state)
        for tag, flag in nations.items():
            images[(tag, state)] = tool.nation(state, flag)
        for name, (make, flag2) in wides.items():
            images[(name, state)] = make(state, flag2)
        for name, flags in groups.items():
            images[(name, state)] = tool.group(state, flags)
    if args.preview:
        preview(args.preview, images, tags)
        print('preview:', args.preview)
    if not args.dry_run:
        tool.write(images, tags)
        print(f'wrote {len(images)} textures, interface/{args.prefix.lower()}_titlebars.gfx and common/national_focus/{args.prefix.lower()}_titlebar_styles.txt')
    print('styles: ' + ', '.join(tool.style(t) for t in tags))


if __name__ == '__main__':
    main()
