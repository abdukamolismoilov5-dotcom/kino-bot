# -*- coding: utf-8 -*-
"""
Kinolar Olami bot uchun Instagram Reels reklama videosi generatori (1080x1920, 30fps).
Ishga tushirish:  python make_promo.py
Natija:           promo/kinolar_olami_reklama.mp4
"""
import os
import re
import sys
import math
import wave
import asyncio
import subprocess
import numpy as np
from functools import lru_cache
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import imageio_ffmpeg

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

BASE = os.path.dirname(os.path.abspath(__file__))
TMP = os.path.join(BASE, "_tmp")
os.makedirs(TMP, exist_ok=True)
FF = imageio_ffmpeg.get_ffmpeg_exe()

W, H, FPS = 1080, 1920, 30
BG = (11, 15, 26)
RED = (255, 61, 46)
ORANGE = (255, 130, 40)
GOLD = (255, 201, 74)
WHITE = (255, 255, 255)
GRAY = (150, 165, 185)
BOT_USERNAME = "@kinolarr_olami_bot"
BRAND = "KINOLAR OLAMI"

VOICE = "uz-UZ-SardorNeural"
SCENES = [
    # (ovozli matn, minimal davomiyligi)
    ("Kino ko'rishni yaxshi ko'rasizmi? Endi kino topish juda oson!", 3.6),
    ("Nom qidirib vaqt yo'qotmang. Shunchaki kodni yozing!", 4.6),
    ("Botga kirasiz, kino kodini yozasiz, va kino darhol chiqadi!", 7.2),
    ("O'zbek tilida kinolar, har kuni yangi qismlar, hammasi bitta botda!", 5.0),
    ("Kinolar Olami. Hoziroq Telegramda kinolarr olami bot ni qidiring va kino ko'rishni boshlang!", 5.4),
]


# ---------------------------------------------------------------- yordamchilar
@lru_cache(maxsize=None)
def font(size):
    for name in ("arialbd.ttf", "segoeuib.ttf", "arial.ttf"):
        p = os.path.join("C:/Windows/Fonts", name)
        if os.path.exists(p):
            return ImageFont.truetype(p, size)
    return ImageFont.load_default()


def clamp(x, a=0.0, b=1.0):
    return max(a, min(b, x))


def prog(t, start, dur):
    return clamp((t - start) / dur) if dur > 0 else (1.0 if t >= start else 0.0)


def ease_out(x):
    return 1 - (1 - x) ** 3


def ease_back(x):
    c1, c3 = 1.70158, 2.70158
    return 1 + c3 * (x - 1) ** 3 + c1 * (x - 1) ** 2


def lerp(a, b, k):
    return a + (b - a) * k


def mix(c1, c2, k):
    return tuple(int(lerp(c1[i], c2[i], k)) for i in range(3))


def grad_image(w, h, c1, c2, horizontal=True):
    if horizontal:
        a = np.linspace(0, 1, w)[None, :, None]
        arr = np.array(c1)[None, None, :] * (1 - a) + np.array(c2)[None, None, :] * a
        arr = np.repeat(arr, h, axis=0)
    else:
        a = np.linspace(0, 1, h)[:, None, None]
        arr = np.array(c1)[None, None, :] * (1 - a) + np.array(c2)[None, None, :] * a
        arr = np.repeat(arr, w, axis=1)
    return Image.fromarray(arr.astype(np.uint8), "RGB")


def draw_text(canvas, text, cx, cy, fnt, fill=WHITE, alpha=1.0, grad=None, shadow=True, scale=1.0):
    if alpha <= 0.01 or scale <= 0.01:
        return
    l, t, r, b = fnt.getbbox(text)
    w, h = r - l, b - t
    pad = 24
    mask = Image.new("L", (w + 2 * pad, h + 2 * pad), 0)
    ImageDraw.Draw(mask).text((pad - l, pad - t), text, font=fnt, fill=255)
    if scale != 1.0:
        mask = mask.resize((max(1, int(mask.width * scale)), max(1, int(mask.height * scale))), Image.BILINEAR)
    if alpha < 1.0:
        mask = mask.point(lambda v: int(v * alpha))
    x = int(cx - mask.width / 2)
    y = int(cy - mask.height / 2)
    if shadow:
        sm = mask.filter(ImageFilter.GaussianBlur(10)).point(lambda v: int(v * 0.65))
        canvas.paste((0, 0, 0), (x + 3, y + 10), sm)
    if grad:
        gi = grad_image(mask.width, mask.height, grad[0], grad[1], horizontal=True)
        canvas.paste(gi, (x, y), mask)
    else:
        canvas.paste(fill, (x, y), mask)


def rrect(canvas, box, radius, fill, outline=None, width=0):
    ImageDraw.Draw(canvas).rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=width)


@lru_cache(maxsize=None)
def glow_asset(size, color):
    m = Image.new("L", (size, size), 0)
    ImageDraw.Draw(m).ellipse((size * 0.22, size * 0.22, size * 0.78, size * 0.78), fill=255)
    m = m.filter(ImageFilter.GaussianBlur(size * 0.13))
    return Image.new("RGB", (size, size), color), m


def paste_glow(canvas, cx, cy, size, color, k=1.0):
    size = int(size)
    if size < 8 or k <= 0:
        return
    img, m = glow_asset(size, color)
    if k < 1.0:
        m = m.point(lambda v: int(v * k))
    canvas.paste(img, (int(cx - size / 2), int(cy - size / 2)), m)


@lru_cache(maxsize=None)
def play_button_base():
    s = 600
    g = grad_image(s, s, (255, 90, 45), (225, 30, 60), horizontal=False)
    m = Image.new("L", (s, s), 0)
    ImageDraw.Draw(m).ellipse((10, 10, s - 10, s - 10), fill=255)
    g.putalpha(m)
    d = ImageDraw.Draw(g)
    tri = [(s * 0.40, s * 0.30), (s * 0.40, s * 0.70), (s * 0.73, s * 0.50)]
    d.polygon(tri, fill=(255, 255, 255, 255))
    return g


def draw_play(canvas, cx, cy, r, glow=True, k=1.0):
    if r < 4:
        return
    if glow:
        paste_glow(canvas, cx, cy, int(r * 5), (255, 70, 40), 0.55 * k)
    img = play_button_base().resize((int(r * 2), int(r * 2)), Image.LANCZOS)
    canvas.paste(img, (int(cx - r), int(cy - r)), img)


@lru_cache(maxsize=None)
def logo_circle(size):
    p = os.path.join(BASE, "logo_icon.png")
    if os.path.exists(p):
        im = Image.open(p).convert("RGB")
        s = min(im.size)
        im = im.crop(((im.width - s) // 2, (im.height - s) // 2, (im.width + s) // 2, (im.height + s) // 2))
        im = im.resize((size, size), Image.LANCZOS)
    else:
        im = Image.new("RGB", (size, size), BG)
        pb = play_button_base().resize((int(size * 0.7), int(size * 0.7)), Image.LANCZOS)
        im.paste(pb, (int(size * 0.15), int(size * 0.15)), pb)
    m = Image.new("L", (size, size), 0)
    ImageDraw.Draw(m).ellipse((2, 2, size - 3, size - 3), fill=255)
    m = m.filter(ImageFilter.GaussianBlur(1.2))
    im = im.convert("RGBA")
    im.putalpha(m)
    return im


def draw_logo(canvas, cx, cy, size, ring=True, glow_k=0.0):
    if size < 8:
        return
    if glow_k > 0:
        paste_glow(canvas, cx, cy, int(size * 2.1), (255, 90, 40), glow_k)
    if ring:
        d = ImageDraw.Draw(canvas)
        d.ellipse((cx - size / 2 - 8, cy - size / 2 - 8, cx + size / 2 + 8, cy + size / 2 + 8), outline=GOLD, width=6)
    lg = logo_circle(int(size))
    canvas.paste(lg, (int(cx - size / 2), int(cy - size / 2)), lg)


# ---------------------------------------------------------------- fon
_BASE_BG = grad_image(W, H, (16, 22, 40), (8, 9, 18), horizontal=False)
_PARTICLES = [(np.random.RandomState(i).rand(), np.random.RandomState(i + 99).rand(),
               2 + np.random.RandomState(i + 7).rand() * 5, 18 + np.random.RandomState(i + 3).rand() * 40)
              for i in range(38)]


def background(t_global):
    img = _BASE_BG.copy()
    # yumshoq harakatlanuvchi yorug'lik dog'lari
    paste_glow(img, 200 + 160 * math.sin(t_global * 0.7), 450 + 120 * math.cos(t_global * 0.5), 1100, (190, 40, 40), 0.30)
    paste_glow(img, 880 + 140 * math.cos(t_global * 0.6), 1500 + 160 * math.sin(t_global * 0.8), 1100, (230, 140, 30), 0.22)
    d = ImageDraw.Draw(img)
    # pastdan yuqoriga uchib chiquvchi zarrachalar
    for px, py, r, sp in _PARTICLES:
        y = (py * H - t_global * sp * 6) % H
        x = px * W + 20 * math.sin(t_global + px * 9)
        d.ellipse((x - r, y - r, x + r, y + r), fill=(255, 190, 70) if r > 4 else (255, 120, 60))
    # kino plyonkasi chetlari
    off = (t_global * 140) % 90
    for side_x in (0, W - 70):
        d.rectangle((side_x, 0, side_x + 70, H), fill=(6, 7, 12))
        yy = -90 + off
        while yy < H:
            d.rounded_rectangle((side_x + 18, yy, side_x + 52, yy + 52), radius=9, fill=(30, 36, 52))
            yy += 90
    return img


# ---------------------------------------------------------------- sahnalar
def scene_hook(c, t, d):
    pill_a = ease_out(prog(t, 0.1, 0.4))
    rrect(c, (330, 150, 750, 240), 45, (30, 20, 25), outline=GOLD, width=3)
    draw_text(c, "TELEGRAM BOT", 540, 195, font(40), GOLD, alpha=pill_a, shadow=False)

    k1 = ease_back(prog(t, 0.25, 0.55))
    draw_text(c, "KINO", 540, 520 - (1 - k1) * 120, font(250), grad=(RED, GOLD), alpha=prog(t, 0.25, 0.3), scale=0.6 + 0.4 * k1)
    k2 = ease_back(prog(t, 0.65, 0.55))
    draw_text(c, "KO'RISH", 540, 760 - (1 - k2) * 100, font(190), WHITE, alpha=prog(t, 0.65, 0.3), scale=0.6 + 0.4 * k2)
    k3 = ease_back(prog(t, 1.1, 0.55))
    draw_text(c, "ENDI JUDA OSON!", 540, 960 - (1 - k3) * 80, font(100), GOLD, alpha=prog(t, 1.1, 0.3), scale=0.7 + 0.3 * k3)

    pb = ease_back(prog(t, 1.4, 0.6))
    pulse = 1 + 0.06 * math.sin(t * 6)
    draw_play(c, 540, 1380, 170 * pb * pulse, glow=True, k=0.6 + 0.4 * math.sin(t * 6) ** 2)
    draw_text(c, "Kodni yozing, kino chiqadi", 540, 1650, font(54), GRAY, alpha=prog(t, 2.0, 0.5), shadow=False)


def scene_code(c, t, d):
    a1 = ease_out(prog(t, 0.1, 0.4))
    draw_text(c, "Nom qidirib", 540, 320, font(110), WHITE, alpha=a1)
    draw_text(c, "vaqt yo'qotmang", 540, 450, font(110), WHITE, alpha=a1)
    s = ease_out(prog(t, 1.3, 0.35))
    if s > 0:
        dr = ImageDraw.Draw(c)
        dr.line((160, 330 + 70, 160 + int(760 * s), 330 - 90 + 70 * 0), fill=RED, width=14) if False else None
        dr.line((140, 400, 140 + int(800 * s), 400), fill=RED, width=16)

    k = ease_back(prog(t, 1.9, 0.6))
    draw_text(c, "Faqat", 540, 700 - (1 - k) * 60, font(100), GRAY, alpha=prog(t, 1.9, 0.3), scale=0.7 + 0.3 * k)
    draw_text(c, "KOD YOZING!", 540, 860 - (1 - k) * 80, font(160), grad=(GOLD, ORANGE), alpha=prog(t, 1.9, 0.3), scale=0.6 + 0.4 * k)

    # kod raqamlari
    nums = ["1", "2", "3", "4", "5"]
    size, gap = 150, 24
    total = len(nums) * size + (len(nums) - 1) * gap
    x0 = (W - total) / 2
    for i, n in enumerate(nums):
        kk = ease_back(prog(t, 2.5 + i * 0.18, 0.5))
        if kk <= 0:
            continue
        bob = 12 * math.sin(t * 3 + i)
        cx = x0 + i * (size + gap) + size / 2
        cy = 1250 + bob
        half = size / 2 * kk
        rrect(c, (cx - half, cy - half, cx + half, cy + half), 36, (28, 34, 52), outline=GOLD, width=4)
        draw_text(c, n, cx, cy - 4, font(100), WHITE, alpha=clamp(kk), scale=kk, shadow=False)
    draw_text(c, "Har bir kinoning o'z kodi bor", 540, 1480, font(52), GRAY, alpha=prog(t, 3.6, 0.5), shadow=False)


def dots_bubble(c, x, y, t):
    rrect(c, (x, y, x + 150, y + 80), 40, (24, 37, 51))
    for i in range(3):
        yy = y + 40 - 8 * max(0, math.sin(t * 8 - i * 0.9))
        ImageDraw.Draw(c).ellipse((x + 38 + i * 36 - 9, yy - 9, x + 38 + i * 36 + 9, yy + 9), fill=(190, 200, 215))


def scene_chat(c, t, d):
    draw_text(c, "Kodni yozing,", 540, 150, font(90), WHITE, alpha=ease_out(prog(t, 0.0, 0.4)))
    draw_text(c, "kino darhol chiqadi!", 540, 255, font(90), grad=(GOLD, ORANGE), alpha=ease_out(prog(t, 0.2, 0.4)))

    slide = (1 - ease_out(prog(t, 0.0, 0.7))) * 900
    oy = int(slide)
    px0, py0, px1, py1 = 70, 380 + oy, 1010, 1640 + oy
    rrect(c, (px0, py0, px1, py1), 60, (14, 22, 33), outline=(45, 60, 82), width=4)
    rrect(c, (px0, py0, px1, py0 + 130), 60, (23, 33, 43))
    ImageDraw.Draw(c).rectangle((px0 + 2, py0 + 90, px1 - 2, py0 + 130), fill=(23, 33, 43))
    draw_logo(c, px0 + 85, py0 + 65, 84, ring=False)
    draw_text(c, "Kinolar Olami", px0 + 360, py0 + 48, font(44), WHITE, shadow=False)
    draw_text(c, "bot", px0 + 160, py0 + 98, font(30), GRAY, shadow=False)

    # 1) bot salomi
    k = ease_back(prog(t, 0.8, 0.45))
    if k > 0:
        bx, by = px0 + 30, py0 + 170
        w, h = 560 * clamp(k), 90
        rrect(c, (bx, by, bx + w, by + h), 34, (24, 37, 51))
        draw_text(c, "Kino kodini kiriting:", bx + 280, by + 45, font(38), WHITE, alpha=prog(t, 0.95, 0.25), shadow=False)

    # kirish maydoni
    ix0, iy0, ix1, iy1 = px0 + 24, py1 - 120, px1 - 24, py1 - 30
    rrect(c, (ix0, iy0, ix1, iy1), 45, (23, 33, 43))
    typed = 1.5 <= t < 2.4
    if typed:
        draw_text(c, "1", ix0 + 60, (iy0 + iy1) / 2, font(48), WHITE, shadow=False)
        if int(t * 3) % 2 == 0:
            ImageDraw.Draw(c).line((ix0 + 82, iy0 + 22, ix0 + 82, iy1 - 22), fill=GOLD, width=4)
    else:
        draw_text(c, "Xabar", ix0 + 110, (iy0 + iy1) / 2, font(40), (95, 110, 130), shadow=False)
    sendc = GOLD if typed else (70, 85, 105)
    ImageDraw.Draw(c).ellipse((ix1 - 80, iy0 + 10, ix1 - 10, iy1 - 10), fill=sendc)
    ImageDraw.Draw(c).polygon([(ix1 - 60, iy0 + 22), (ix1 - 60, iy1 - 22), (ix1 - 24, (iy0 + iy1) / 2)], fill=BG)

    # 2) foydalanuvchi xabari
    k = ease_back(prog(t, 2.5, 0.4))
    if k > 0:
        w, h = 130 * clamp(k), 90
        bx, by = px1 - 30 - w, py0 + 290
        rrect(c, (bx, by, bx + w, by + h), 34, (43, 82, 120))
        draw_text(c, "1", bx + w / 2, by + 45, font(46), WHITE, alpha=prog(t, 2.6, 0.2), shadow=False)

    # 3) yozmoqda...
    if 3.0 <= t < 3.8:
        dots_bubble(c, px0 + 30, py0 + 410, t)

    # 4) kino kartochkasi
    k = ease_back(prog(t, 3.8, 0.55))
    if k > 0:
        cw = 840
        bx, by = px0 + 30, py0 + 410
        ch = int(640 * clamp(k))
        rrect(c, (bx, by, bx + cw, by + ch), 36, (24, 37, 51))
        if k > 0.85:
            tx0, ty0, tx1, ty1 = bx + 20, by + 20, bx + cw - 20, by + 380
            th = grad_image(tx1 - tx0, ty1 - ty0, (95, 30, 30), (14, 12, 24), horizontal=False)
            tm = Image.new("L", th.size, 0)
            ImageDraw.Draw(tm).rounded_rectangle((0, 0, th.width - 1, th.height - 1), radius=26, fill=255)
            c.paste(th, (tx0, ty0), tm)
            draw_play(c, (tx0 + tx1) / 2, (ty0 + ty1) / 2, 78, glow=False)
            rrect(c, (tx1 - 120, ty0 + 18, tx1 - 22, ty0 + 70), 14, GOLD)
            draw_text(c, "HD", tx1 - 71, ty0 + 44, font(34), BG, shadow=False)
            draw_text(c, "Forsaj 1 (O'zbek tilida)", bx + cw / 2, by + 430, font(44), WHITE, shadow=False)
            draw_text(c, "Kino kodi: 1", bx + cw / 2, by + 490, font(36), GOLD, shadow=False)
            draw_text(c, "Faqat bot ichida tomosha qilish mumkin", bx + cw / 2, by + 545, font(30), GRAY, shadow=False)


def check_icon(c, cx, cy, r):
    d = ImageDraw.Draw(c)
    d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=GOLD)
    d.line([(cx - r * 0.45, cy + r * 0.02), (cx - r * 0.1, cy + r * 0.38), (cx + r * 0.5, cy - r * 0.35)], fill=BG, width=int(r * 0.22), joint="curve")


def scene_features(c, t, d):
    draw_text(c, "NEGA AYNAN BIZ?", 540, 270, font(88), grad=(GOLD, ORANGE), alpha=ease_out(prog(t, 0.0, 0.4)))
    items = ["O'zbek tilida kinolar", "Faqat kod yozasiz", "Har kuni yangi kinolar", "Telefonda tez va qulay"]
    for i, it in enumerate(items):
        k = ease_out(prog(t, 0.5 + i * 0.5, 0.5))
        if k <= 0:
            continue
        y = 560 + i * 250
        x_off = (1 - k) * 1100
        rrect(c, (110 + x_off, y - 85, 970 + x_off, y + 85), 50, (22, 28, 44), outline=(70, 55, 40), width=3)
        check_icon(c, 200 + x_off, y, 46)
        draw_text(c, it, 600 + x_off, y, font(54), WHITE, shadow=False)
    draw_text(c, "Hammasi bitta botda", 540, 1620, font(60), GRAY, alpha=prog(t, 2.8, 0.5), shadow=False)


def scene_cta(c, t, d):
    k = ease_back(prog(t, 0.1, 0.7))
    pulse = 0.5 + 0.5 * math.sin(t * 4)
    draw_logo(c, 540, 560, 520 * k, ring=True, glow_k=0.5 + 0.3 * pulse)
    draw_text(c, BRAND, 540, 950, font(104), grad=(RED, GOLD), alpha=prog(t, 0.6, 0.4), scale=0.8 + 0.2 * ease_back(prog(t, 0.6, 0.5)))
    draw_text(c, "Telegram bot", 540, 1050, font(52), GRAY, alpha=prog(t, 0.8, 0.4), shadow=False)

    kb = ease_back(prog(t, 1.2, 0.5))
    if kb > 0:
        w = 800 * clamp(kb)
        rrect(c, (540 - w / 2, 1150, 540 + w / 2, 1280), 65, (28, 34, 54), outline=GOLD, width=4)
        draw_text(c, BOT_USERNAME, 540, 1215, font(64), WHITE, alpha=prog(t, 1.35, 0.3), shadow=False)

    kc = ease_back(prog(t, 1.9, 0.5))
    if kc > 0.08:
        s = 1 + 0.04 * math.sin(t * 7)
        w, h = 760 * clamp(kc) * s, 140 * s
        cy = 1450
        paste_glow(c, 540, cy, 1000, (255, 60, 40), 0.35 + 0.2 * pulse)
        g = grad_image(int(w), int(h), (255, 70, 40), (255, 140, 40), horizontal=True)
        m = Image.new("L", g.size, 0)
        ImageDraw.Draw(m).rounded_rectangle((0, 0, g.width - 1, g.height - 1), radius=int(h / 2), fill=255)
        c.paste(g, (int(540 - w / 2), int(cy - h / 2)), m)
        draw_text(c, "HOZIROQ KIRING", 540, cy, font(62), WHITE, alpha=prog(t, 2.1, 0.3), shadow=False)
    draw_text(c, "Havola profilda (link in bio)", 540, 1640, font(44), GRAY, alpha=prog(t, 2.6, 0.5), shadow=False)


SCENE_FUNCS = [scene_hook, scene_code, scene_chat, scene_features, scene_cta]


# ---------------------------------------------------------------- audio
def probe_duration(path):
    r = subprocess.run([FF, "-i", path], capture_output=True, text=True, errors="ignore")
    m = re.search(r"Duration:\s*(\d+):(\d+):(\d+\.\d+)", r.stderr)
    if not m:
        return 0.0
    return int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3))


async def _tts(text, out):
    import edge_tts
    com = edge_tts.Communicate(text, VOICE, rate="+6%")
    await com.save(out)


def make_voice():
    durs, files = [], []
    for i, (text, mn) in enumerate(SCENES):
        mp3 = os.path.join(TMP, f"v{i}.mp3")
        ok = False
        try:
            asyncio.run(_tts(text, mp3))
            ok = os.path.exists(mp3) and os.path.getsize(mp3) > 1000
        except Exception as e:
            print("TTS xatolik:", e)
        ad = probe_duration(mp3) if ok else 0.0
        durs.append(max(mn, ad + 0.7))
        files.append(mp3 if ok else None)
        print(f"  sahna {i + 1}: ovoz {ad:.2f}s -> sahna {durs[-1]:.2f}s")
    return files, durs


def build_voice_track(files, durs):
    parts = []
    for i, (f, d) in enumerate(zip(files, durs)):
        out = os.path.join(TMP, f"p{i}.wav")
        if f:
            subprocess.run([FF, "-y", "-i", f, "-af", "apad", "-t", f"{d:.3f}", "-ar", "44100", "-ac", "1", out],
                           capture_output=True)
        else:
            subprocess.run([FF, "-y", "-f", "lavfi", "-i", "anullsrc=r=44100:cl=mono", "-t", f"{d:.3f}", out],
                           capture_output=True)
        parts.append(out)
    lst = os.path.join(TMP, "list.txt")
    with open(lst, "w", encoding="utf-8") as fh:
        for p in parts:
            fh.write(f"file '{p.replace(chr(92), '/')}'\n")
    voice = os.path.join(TMP, "voice.wav")
    subprocess.run([FF, "-y", "-f", "concat", "-safe", "0", "-i", lst, "-c", "copy", voice], capture_output=True)
    return voice


def synth_music(total, path, sr=44100, bpm=112):
    n = int((total + 1) * sr)
    out = np.zeros(n)
    beat = 60.0 / bpm
    rng = np.random.RandomState(3)

    def add(sig, start):
        i = int(start * sr)
        j = min(n, i + len(sig))
        if i < n:
            out[i:j] += sig[: j - i]

    kt = np.arange(int(0.4 * sr)) / sr
    freq = 45 + 110 * np.exp(-kt * 32)
    kick = np.sin(2 * np.pi * np.cumsum(freq) / sr) * np.exp(-kt * 8) * 1.0
    ht = np.arange(int(0.08 * sr)) / sr
    hat = np.diff(rng.randn(len(ht) + 1)) * np.exp(-ht * 60) * 0.25
    roots = [55.0, 43.65, 65.41, 49.0]
    chords = [(220.0, 261.63, 329.63), (174.61, 220.0, 261.63), (261.63, 329.63, 392.0), (196.0, 246.94, 293.66)]

    t_cur, bar = 0.0, 0
    while t_cur < total + 1:
        ch = bar % 4
        for b in range(4):
            bt = t_cur + b * beat
            add(kick, bt)
            add(hat, bt + beat / 2)
            # bass (8-chi nota)
            for h in range(2):
                st = bt + h * beat / 2
                nt = np.arange(int(beat / 2 * sr)) / sr
                f = roots[ch] * (2 if (b % 2 and h) else 1)
                s = (np.sin(2 * np.pi * f * nt) + 0.4 * np.sin(2 * np.pi * 2 * f * nt)) * np.exp(-nt * 5) * 0.55
                add(s, st)
            # arpeggio (16-lik)
            for h in range(4):
                st = bt + h * beat / 4
                nt = np.arange(int(beat / 4 * sr * 1.5)) / sr
                f = chords[ch][(b * 4 + h) % 3] * 2
                s = np.sin(2 * np.pi * f * nt) * np.exp(-nt * 14) * 0.18
                add(s, st)
        # pad
        pt = np.arange(int(4 * beat * sr)) / sr
        env = np.minimum(1, pt / 0.5) * np.minimum(1, (4 * beat - pt) / 0.5)
        pad = sum(np.sin(2 * np.pi * f * pt) for f in chords[ch]) * env * 0.07
        add(pad, t_cur)
        t_cur += 4 * beat
        bar += 1

    out = out / (np.max(np.abs(out)) + 1e-9) * 0.9
    fi = int(0.4 * sr)
    out[:fi] *= np.linspace(0, 1, fi)
    fo = int(1.8 * sr)
    end_i = int(total * sr)
    out[end_i - fo:end_i] *= np.linspace(1, 0, fo)
    out[end_i:] = 0
    pcm = (out * 32767).astype(np.int16)
    with wave.open(path, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        wf.writeframes(pcm.tobytes())


# ---------------------------------------------------------------- render
def main():
    print("1/4 Ovoz (O'zbek tilida) tayyorlanmoqda...")
    files, durs = make_voice()
    total = sum(durs)
    print(f"   Umumiy davomiylik: {total:.1f}s")

    print("2/4 Ovoz va musiqa yig'ilmoqda...")
    voice = build_voice_track(files, durs)
    music = os.path.join(TMP, "music.wav")
    synth_music(total, music)

    print("3/4 Video kadrlar chizilmoqda...")
    silent = os.path.join(TMP, "silent.mp4")
    proc = subprocess.Popen(
        [FF, "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
         "-c:v", "libx264", "-preset", "medium", "-crf", "17", "-pix_fmt", "yuv420p", "-movflags", "+faststart", silent],
        stdin=subprocess.PIPE, stderr=subprocess.DEVNULL)

    cover_done = False
    frame_idx = 0
    t_start = 0.0
    for si, (fn, dur) in enumerate(zip(SCENE_FUNCS, durs)):
        nframes = int(round(dur * FPS))
        for f in range(nframes):
            t = f / FPS
            tg = t_start + t
            frame = background(tg)
            fn(frame, t, dur)
            # sahna oxiri/boshi yumshoq o'tish
            fade = min(prog(t, 0, 0.25), 1 - prog(t, dur - 0.25, 0.25)) if si < len(SCENE_FUNCS) - 1 else prog(t, 0, 0.25)
            if fade < 1.0:
                frame = Image.blend(Image.new("RGB", (W, H), BG), frame, clamp(fade))
            if si == len(SCENE_FUNCS) - 1 and not cover_done and t >= 3.0:
                frame.save(os.path.join(BASE, "kinolar_olami_cover.png"))
                cover_done = True
            proc.stdin.write(frame.tobytes())
            frame_idx += 1
            if frame_idx % 60 == 0:
                print(f"   {frame_idx} kadr...")
        t_start += dur
    proc.stdin.close()
    proc.wait()

    print("4/4 Yakuniy video (ovoz + musiqa) yig'ilmoqda...")
    final = os.path.join(BASE, "kinolar_olami_reklama.mp4")
    subprocess.run([
        FF, "-y", "-i", silent, "-i", voice, "-i", music,
        "-filter_complex", "[1:a]volume=1.5[v];[2:a]volume=0.20[m];[v][m]amix=inputs=2:duration=first:normalize=0[a]",
        "-map", "0:v", "-map", "[a]", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-shortest", final
    ], capture_output=True)
    print("TAYYOR:", final, f"({os.path.getsize(final) / 1048576:.1f} MB)")


if __name__ == "__main__":
    main()
