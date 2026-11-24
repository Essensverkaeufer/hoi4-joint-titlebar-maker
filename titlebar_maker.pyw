"""Joint Title Bar Maker: a simple window for joint_titlebars.py.

Add the countries, tick what you want, press Preview, then Save zip. The zip holds the textures, the .gfx and the
styles file in mod folder layout (unzip into your mod), a big preview picture and a how-to with the text_icon lines.

Double-click this file (or Start.bat). Needs Python 3.9+ with Pillow: pip install pillow
"""
import json
import os
import re
import sys
import tempfile
import tkinter as tk
import zipfile
from pathlib import Path
from tkinter import colorchooser, filedialog, messagebox, ttk

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
# as a one-file .exe the code runs from a temp folder; keep the settings next to the .exe instead
HOME = Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else HERE

try:
    from PIL import Image, ImageDraw, ImageFont, ImageTk
except ImportError:
    root = tk.Tk()
    root.withdraw()
    messagebox.showerror("Pillow missing", "This tool needs Pillow.\n\nOpen a command prompt and run:\n\npip install pillow")
    sys.exit(1)

import joint_titlebars as JT  # noqa: E402

SETTINGS = HOME / "titlebar_maker_settings.json"
STEAM_GUESSES = [
    r"C:\Program Files (x86)\Steam\steamapps\common\Hearts of Iron IV",
    r"C:\Program Files\Steam\steamapps\common\Hearts of Iron IV",
    r"D:\SteamLibrary\steamapps\common\Hearts of Iron IV",
    r"E:\SteamLibrary\steamapps\common\Hearts of Iron IV",
    r"D:\Steam\steamapps\common\Hearts of Iron IV",
]
STATE_NAMES = {"can_start": "can start", "completed": "completed", "unavailable": "unavailable"}


# ---------------------------------------------------------------- helpers
def find_game():
    """the HoI4 install: Steam's library list first, then the usual places"""
    vdf = Path(r"C:\Program Files (x86)\Steam\steamapps\libraryfolders.vdf")
    guesses = []
    if vdf.is_file():
        for p in re.findall(r'"path"\s+"([^"]+)"', vdf.read_text(encoding="utf-8", errors="ignore")):
            guesses.append(str(Path(p.replace("\\\\", "\\")) / "steamapps/common/Hearts of Iron IV"))
    for g in guesses + STEAM_GUESSES:
        if (Path(g) / "gfx/interface/focusview/titlebar/focus_can_start_joint_TUR_bg.dds").is_file():
            return g
    return ""


def load_settings():
    try:
        return json.loads(SETTINGS.read_text(encoding="utf-8"))
    except Exception:
        return {}


def save_settings(data):
    try:
        SETTINGS.write_text(json.dumps(data, indent=1), encoding="utf-8")
    except Exception:
        pass


def flag_names(game, mod):
    names = set()
    for root in (mod, game):
        d = Path(root) / "gfx/flags" if root else None
        if d and d.is_dir():
            names.update(p.stem for p in d.iterdir() if p.suffix.lower() in JT.FLAG_EXT)
    return sorted(names)


def clean_name(text):
    return re.sub(r"[^A-Za-z0-9_]", "", text.strip().upper().replace(" ", "_"))


def rgb_hex(c):
    return "#%02x%02x%02x" % tuple(c)


class Run(Exception):
    pass


def safe(fn, *a, **k):
    """the script stops with sys.exit on bad input; turn that into a message"""
    try:
        return fn(*a, **k)
    except SystemExit as e:
        raise Run(str(e))


# ---------------------------------------------------------------- one country row
class CountryRow:
    def __init__(self, app, parent, tag="", flag=""):
        self.app = app
        self.frame = ttk.Frame(parent)
        self.tag = tk.StringVar(value=tag)
        self.flag = tk.StringVar(value=flag)
        self.thumb = None
        ttk.Label(self.frame, text="Tag").pack(side="left")
        ttk.Entry(self.frame, textvariable=self.tag, width=6).pack(side="left", padx=(4, 10))
        ttk.Label(self.frame, text="Flag").pack(side="left")
        self.box = ttk.Combobox(self.frame, textvariable=self.flag, width=48, values=app.flags, postcommand=self.fill)
        self.box.pack(side="left", padx=4)
        self.box.bind("<KeyRelease>", self.filter)
        self.box.bind("<<ComboboxSelected>>", lambda e: self.show_thumb())
        self.box.bind("<FocusOut>", lambda e: self.show_thumb())
        ttk.Button(self.frame, text="File...", width=6, command=self.browse).pack(side="left", padx=2)
        self.pic = ttk.Label(self.frame)
        self.pic.pack(side="left", padx=6)
        ttk.Button(self.frame, text="Remove", width=8, command=self.remove).pack(side="left", padx=4)
        self.frame.pack(fill="x", pady=2)
        self.show_thumb()

    def matches(self):
        """typed text first (names starting with it, then containing it), else the tag's flags, else all of them"""
        flags = self.app.flags
        t = self.flag.get().strip().lower()
        if t and not Path(t).is_file():
            starts = [f for f in flags if f.lower().startswith(t)]
            return starts + [f for f in flags if t in f.lower() and not f.lower().startswith(t)]
        tag = self.tag.get().strip().lower()
        if tag:
            own = [f for f in flags if f.lower() == tag or f.lower().startswith(tag + "_")]
            if own:
                return own
        return flags

    def fill(self):
        """runs as the list opens: the right names, scrolled to their start"""
        self.box["values"] = self.matches()
        self.box.after(1, self.unscroll)

    def unscroll(self):
        try:
            pop = self.box.tk.call("ttk::combobox::PopdownWindow", self.box)
            self.box.tk.call("%s.f.l" % pop, "xview", "moveto", 0)
        except tk.TclError:
            pass

    def filter(self, event=None):
        if event is not None and event.keysym in ("Down", "Up", "Return", "Escape", "Tab"):
            return
        self.box["values"] = self.matches()
        t = self.flag.get().lower()
        if not self.tag.get() and len(t) >= 3:
            self.tag.set(t[:3].upper())

    def browse(self):
        p = filedialog.askopenfilename(title="Pick a flag image", filetypes=[("Flags", "*.tga *.png *.dds"), ("All files", "*.*")])
        if p:
            self.flag.set(p)
            self.show_thumb()

    def show_thumb(self):
        self.thumb = None
        spec = self.flag.get().strip()
        if spec:
            try:
                img = self.app.tool_for_flags().flag(spec).resize((41, 26), Image.LANCZOS)
                self.thumb = ImageTk.PhotoImage(img)
                if not self.tag.get() and not Path(spec).is_file():
                    self.tag.set(spec.split("_")[0][:3].upper())
            except (SystemExit, Exception):
                self.thumb = None
        self.pic.configure(image=self.thumb or "", text="" if self.thumb else "(not found)" if spec else "")

    def remove(self):
        self.frame.destroy()
        self.app.rows.remove(self)

    def value(self):
        return clean_name(self.tag.get()), self.flag.get().strip()


# ---------------------------------------------------------------- the window
class App:
    def __init__(self, root):
        self.root = root
        root.title("Joint Title Bar Maker - HoI4")
        root.minsize(860, 640)
        s = load_settings()
        self.game = tk.StringVar(value=s.get("game") or find_game())
        self.mod = tk.StringVar(value=s.get("mod", ""))
        self.prefix = tk.StringVar(value=s.get("prefix", ""))
        self.want_wide = tk.BooleanVar(value=s.get("wide", True))
        self.wide_kind = tk.StringVar(value=s.get("wide_kind", "flag"))
        self.want_small = tk.BooleanVar(value=s.get("small", True))
        self.want_all = tk.BooleanVar(value=s.get("all", True))
        self.want_stars = tk.BooleanVar(value=s.get("stars", False))
        self.star_field = tuple(s.get("star_field", (0, 51, 153)))
        self.star_gold = tuple(s.get("star_gold", (255, 204, 0)))
        self.star_count = tk.IntVar(value=s.get("star_count", 12))
        self.flags = []
        self.rows = []
        self.preview_img = None
        self.last = None
        self.build()
        self.refresh_flags()
        for tag, flag in s.get("countries", []) or [("", ""), ("", "")]:
            self.add_row(tag, flag)

    # ---- layout
    def build(self):
        pad = {"padx": 8, "pady": 4}
        top = ttk.LabelFrame(self.root, text="1. Folders")
        top.pack(fill="x", **pad)
        for i, (label, var, cmd) in enumerate((("Hearts of Iron IV folder", self.game, self.pick_game),
                                                ("Mod folder (optional)", self.mod, self.pick_mod))):
            ttk.Label(top, text=label).grid(row=i, column=0, sticky="w", padx=6, pady=3)
            ttk.Entry(top, textvariable=var, width=80).grid(row=i, column=1, sticky="we", padx=4)
            ttk.Button(top, text="Browse...", command=cmd).grid(row=i, column=2, padx=6)
        ttk.Label(top, text="only needed to use your mod's own flags", foreground="#777").grid(row=2, column=1, sticky="w", padx=6)
        ttk.Label(top, text="Short name (e.g. AXIS)").grid(row=3, column=0, sticky="w", padx=6, pady=3)
        ttk.Entry(top, textvariable=self.prefix, width=14).grid(row=3, column=1, sticky="w", padx=4)
        top.columnconfigure(1, weight=1)

        mid = ttk.LabelFrame(self.root, text="2. Countries (the order here is the order on the ribbon)")
        mid.pack(fill="x", **pad)
        self.rows_box = ttk.Frame(mid)
        self.rows_box.pack(fill="x", padx=6, pady=4)
        ttk.Button(mid, text="+ Add country", command=lambda: self.add_row()).pack(anchor="w", padx=6, pady=(0, 6))

        opt = ttk.LabelFrame(self.root, text="3. What to make")
        opt.pack(fill="x", **pad)
        r1 = ttk.Frame(opt)
        r1.pack(fill="x", padx=6, pady=2)
        ttk.Checkbutton(r1, text="Wide ribbon for each country:", variable=self.want_wide).pack(side="left")
        ttk.Radiobutton(r1, text="whole flag", value="flag", variable=self.wide_kind).pack(side="left", padx=6)
        ttk.Radiobutton(r1, text="emblem only (for flags with one plain colour)", value="emblem", variable=self.wide_kind).pack(side="left")
        ttk.Checkbutton(opt, text="Small ribbon for each country", variable=self.want_small).pack(anchor="w", padx=6, pady=2)
        ttk.Checkbutton(opt, text="All flags together on one ribbon", variable=self.want_all).pack(anchor="w", padx=6, pady=2)
        r4 = ttk.Frame(opt)
        r4.pack(fill="x", padx=6, pady=2)
        ttk.Checkbutton(r4, text="Wide ribbon with stars", variable=self.want_stars).pack(side="left")
        self.field_btn = tk.Button(r4, text="ribbon colour", width=12, command=lambda: self.pick_colour("field"))
        self.field_btn.pack(side="left", padx=6)
        self.gold_btn = tk.Button(r4, text="star colour", width=12, command=lambda: self.pick_colour("gold"))
        self.gold_btn.pack(side="left", padx=2)
        ttk.Label(r4, text="stars").pack(side="left", padx=(8, 2))
        ttk.Spinbox(r4, from_=1, to=24, textvariable=self.star_count, width=4).pack(side="left")
        self.paint_colour_buttons()

        btns = ttk.Frame(self.root)
        btns.pack(fill="x", **pad)
        ttk.Button(btns, text="Preview", command=self.do_preview).pack(side="left")
        self.make_btn = ttk.Button(btns, text="Save zip...", command=self.do_zip)
        self.make_btn.pack(side="left", padx=8)
        self.status = ttk.Label(btns, text="", foreground="#a33")
        self.status.pack(side="left", padx=8)

        view = ttk.LabelFrame(self.root, text="Preview (can start / completed / unavailable)")
        view.pack(fill="both", expand=True, **pad)
        self.canvas = tk.Canvas(view, background="#28282c", highlightthickness=0)
        sb = ttk.Scrollbar(view, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self.canvas.pack(fill="both", expand=True)
        self.canvas.bind_all("<MouseWheel>", lambda e: self.canvas.yview_scroll(int(-e.delta / 120), "units"))

    def add_row(self, tag="", flag=""):
        self.rows.append(CountryRow(self, self.rows_box, tag, flag))

    def pick_game(self):
        p = filedialog.askdirectory(title="Your Hearts of Iron IV folder")
        if p:
            self.game.set(p)
            self.refresh_flags()

    def pick_mod(self):
        p = filedialog.askdirectory(title="Your mod folder")
        if p:
            self.mod.set(p)
            self.refresh_flags()

    def pick_colour(self, which):
        cur = self.star_field if which == "field" else self.star_gold
        c = colorchooser.askcolor(color=rgb_hex(cur), title="Pick a colour")
        if c and c[0]:
            if which == "field":
                self.star_field = tuple(int(x) for x in c[0])
            else:
                self.star_gold = tuple(int(x) for x in c[0])
            self.paint_colour_buttons()

    def paint_colour_buttons(self):
        for btn, c in ((self.field_btn, self.star_field), (self.gold_btn, self.star_gold)):
            dark = sum(c) < 380
            btn.configure(background=rgb_hex(c), activebackground=rgb_hex(c), foreground="white" if dark else "black")

    def refresh_flags(self):
        self.flags = flag_names(self.game.get(), self.mod.get())
        for r in self.rows:
            r.box["values"] = self.flags
            r.show_thumb()

    def tool_for_flags(self):
        """a Tool for reading flags only (works before the game folder is checked)"""
        t = JT.Tool.__new__(JT.Tool)
        t.game, t.mod = Path(self.game.get() or "."), Path(self.mod.get() or ".")
        return t

    # ---- work
    def say(self, text, ok=False):
        self.status.configure(text=text, foreground="#2a7" if ok else "#a33")

    def styles(self):
        """[(style suffix or None, description, builder(state))] from the window's choices"""
        game, mod, prefix = self.game.get().strip(), self.mod.get().strip(), clean_name(self.prefix.get())
        if not prefix:
            raise Run("Give the set a short name, like AXIS or MJA.")
        tool = safe(JT.Tool, game, mod or ".", prefix)
        countries = [r.value() for r in self.rows if r.value()[1]]
        if not countries:
            raise Run("Add at least one country with a flag.")
        tags = [t for t, _ in countries]
        if any(not t for t in tags):
            raise Run("Every country needs a tag (like GER or JAP).")
        if len(set(tags)) != len(tags):
            raise Run("Two countries have the same tag.")
        flags = {t: safe(tool.flag, f) for t, f in countries}
        out = []
        if self.want_stars.get():
            field, gold, n = self.star_field, self.star_gold, max(1, int(self.star_count.get() or 12))
            out.append((None, "wide ribbon with stars", lambda s: tool.shared_stars(s, field, gold, n)))
        if self.want_wide.get():
            for t, f in countries:
                if self.wide_kind.get() == "emblem":
                    out.append(("%s_WIDE" % t, "wide %s emblem" % t, lambda s, f=f: safe(tool.shared_emblem, s, f)))
                else:
                    out.append(("%s_WIDE" % t, "wide %s flag" % t, lambda s, f=f: safe(tool.shared_flag, s, f)))
        if self.want_small.get():
            for t in tags:
                out.append((t, "small %s flag" % t, lambda s, t=t: tool.nation(s, flags[t])))
        if self.want_all.get() and len(tags) > 1:
            out.append(("ALL", "all flags together (%s)" % ", ".join(tags), lambda s: tool.group(s, [flags[t] for t in tags])))
        if not out:
            raise Run("Tick at least one thing to make.")
        return tool, out

    def render(self):
        tool, styles = self.styles()
        images, rows = {}, []
        for suffix, desc, make in styles:
            for state in JT.STATES:
                images[(suffix, state)] = make(state)
            rows.append((suffix, desc, tool.style(suffix)))
        return tool, images, rows

    def sheet(self, images, rows, scale):
        """every style in its three states, with its text_icon line above it"""
        w, h = int(164 * scale), int(69 * scale)
        try:
            font = ImageFont.truetype("arial.ttf", int(7 * scale))
        except OSError:
            font = ImageFont.load_default()
        label_h = int(11 * scale)
        sheet = Image.new("RGB", (3 * (w + 10) + 10, len(rows) * (h + label_h + 12) + 10), (40, 40, 44))
        d = ImageDraw.Draw(sheet)
        for j, (suffix, desc, style) in enumerate(rows):
            y = 10 + j * (h + label_h + 12)
            d.text((10, y), "%s   ->   text_icon = %s" % (desc, style), fill=(240, 220, 150), font=font)
            for i, state in enumerate(JT.STATES):
                img = images[(suffix, state)].resize((w, h), Image.NEAREST)
                sheet.paste(img, (10 + i * (w + 10), y + label_h), img)
        return sheet

    def draw(self, images, rows):
        self.canvas.update_idletasks()
        sheet = self.sheet(images, rows, max(1.0, min(2.0, (self.canvas.winfo_width() - 40) / (3 * 164))))
        self.preview_img = ImageTk.PhotoImage(sheet)
        self.canvas.delete("all")
        self.canvas.create_image(0, 0, anchor="nw", image=self.preview_img)
        self.canvas.configure(scrollregion=(0, 0, sheet.width, sheet.height))

    def remember(self):
        save_settings(dict(game=self.game.get(), mod=self.mod.get(), prefix=self.prefix.get(), wide=self.want_wide.get(),
                           wide_kind=self.wide_kind.get(), small=self.want_small.get(), all=self.want_all.get(),
                           stars=self.want_stars.get(), star_field=self.star_field, star_gold=self.star_gold,
                           star_count=int(self.star_count.get() or 12), countries=[r.value() for r in self.rows]))

    def do_preview(self):
        self.root.config(cursor="watch")
        self.root.update()
        try:
            tool, images, rows = self.render()
            self.draw(images, rows)
            self.last = (tool, images, rows)
            self.say("Preview ready. Happy? Press 'Save zip...'.", ok=True)
            self.remember()
        except Run as e:
            self.say(str(e))
        except Exception as e:  # noqa: BLE001
            self.say("Something went wrong: %s" % e)
        finally:
            self.root.config(cursor="")

    def do_zip(self):
        self.root.config(cursor="watch")
        self.root.update()
        try:
            tool, images, rows = self.render()
            self.draw(images, rows)
            self.remember()
        except Run as e:
            self.say(str(e))
            self.root.config(cursor="")
            return
        except Exception as e:  # noqa: BLE001
            self.say("Something went wrong: %s" % e)
            self.root.config(cursor="")
            return
        self.root.config(cursor="")
        low = tool.prefix.lower()
        s = load_settings()
        out = filedialog.asksaveasfilename(title="Save the zip", defaultextension=".zip", filetypes=[("Zip", "*.zip")],
                                           initialfile="%s_joint_titlebars.zip" % tool.prefix,
                                           initialdir=s.get("zip_dir") or str(Path.home() / "Downloads"))
        if not out:
            return
        lines = "\n".join("text_icon = %s      # %s" % (style, desc) for _, desc, style in rows)
        try:
            with tempfile.TemporaryDirectory() as tmp:
                tool.mod = Path(tmp) / "mod"
                tool.write(images, [r[0] for r in rows])
                self.sheet(images, rows, 3).save(Path(tmp) / "preview.png")
                (Path(tmp) / "HOW_TO_USE.txt").write_text(how_to(low, lines), encoding="utf-8")
                with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
                    for f in sorted((Path(tmp) / "mod").rglob("*")):
                        if f.is_file():
                            z.write(f, f.relative_to(Path(tmp) / "mod").as_posix())
                    z.write(Path(tmp) / "preview.png", "%s_preview.png" % tool.prefix)
                    z.write(Path(tmp) / "HOW_TO_USE.txt", "HOW_TO_USE.txt")
        except Exception as e:  # noqa: BLE001
            self.say("Couldn't save the zip: %s" % e)
            return
        s = load_settings()
        s["zip_dir"] = str(Path(out).parent)
        save_settings(s)
        self.say("Saved %s" % Path(out).name, ok=True)
        self.result(lines, out)

    def result(self, lines, out):
        win = tk.Toplevel(self.root)
        win.title("Done")
        msg = ("Saved: %s\n\n"
               "Unzip it into your mod's main folder (the folders inside match the mod's).\n"
               "It also has a big preview picture and HOW_TO_USE.txt.\n\n"
               "Put one of these lines in a joint focus, then restart the game\n"
               "(new pictures don't load from a save reload):" % out)
        ttk.Label(win, text=msg, justify="left").pack(anchor="w", padx=12, pady=(12, 4))
        txt = tk.Text(win, height=min(12, lines.count("\n") + 2), width=90)
        txt.insert("1.0", lines)
        txt.pack(padx=12, pady=4)

        def copy():
            self.root.clipboard_clear()
            self.root.clipboard_append(lines)
            copy_btn.configure(text="Copied!")

        copy_btn = ttk.Button(win, text="Copy lines", command=copy)
        copy_btn.pack(side="left", padx=12, pady=12)
        ttk.Button(win, text="Show the zip", command=lambda: os.startfile(str(Path(out).parent))).pack(side="left", pady=12)
        ttk.Button(win, text="Close", command=win.destroy).pack(side="right", padx=12, pady=12)


def how_to(low, lines):
    return ("JOINT TITLE BARS\n\n"
            "Unzip into your mod's main folder. It adds:\n"
            "  gfx/interface/focusview/titlebar/   the pictures (.dds)\n"
            "  interface/%s_titlebars.gfx         the sprites\n"
            "  common/national_focus/%s_titlebar_styles.txt   the styles\n\n"
            "Put one of these in a joint focus, then restart the game (a save reload won't load new pictures):\n\n"
            "%s\n" % (low, low, lines))


def main():
    root = tk.Tk()
    try:
        ttk.Style().theme_use("vista" if sys.platform == "win32" else "clam")
    except tk.TclError:
        pass
    for base in (Path(getattr(sys, "_MEIPASS", HERE)), HERE):   # the .exe carries app.ico inside it
        if (base / "app.ico").is_file():
            try:
                root.iconbitmap(default=str(base / "app.ico"))
            except tk.TclError:
                pass
            break
    App(root)
    root.mainloop()


if __name__ == "__main__":
    main()
