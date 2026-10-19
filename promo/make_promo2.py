# -*- coding: utf-8 -*-
"""
KINOLAR OLAMI - Instagram Reels reklama videosi v2 (KINEMATOGRAFIK).
3D yozuvlar, portlashlar, nur shu'lalari, glitch, bloom, perspektiv telefon,
musiqaga sinxron silkinish va zarbalar.

Ishga tushirish:
    python make_promo2.py            -> to'liq video (promo/kinolar_olami_reklama_v2.mp4)
    python make_promo2.py --preview  -> faqat kadrlar jadvali (_tmp/preview.png)
"""
import os
import re
import sys
import math
import wave
import asyncio
import subprocess
import multiprocessing as mp
import numpy as np
from functools import lru_cache
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageChops
import imageio_ffmpeg

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

BASE = os.path.dirname(os.path.abspath(__file__))
ASSETS = os.path.join(BASE, "assets")
TMP = os.path.join(BASE, "_tmp")
os.makedirs(TMP, exist_ok=True)
FF = imageio_ffmpeg.get_ffmpeg_exe()

W, H, FPS = 1080, 1920, 30
BPM = 112
BEAT = 60.0 / BPM
BG = (8, 10, 20)
RED = (255, 61, 46)
ORANGE = (255, 130, 40)
GOLD = (255, 201, 74)
WHITE = (255, 255, 255)
GRAY = (170, 182, 200)
BOT_USERNAME = "@kinolarr_olami_bot"
BRAND = "KINOLAR OLAMI"
VOICE = "uz-UZ-SardorNeural"

SCENES = [
    ("Kino ko'rishni yaxshi ko'rasizmi? Endi kino topish juda oson!", 3.8),
    ("Nom qidirib vaqt yo'qotmang. Shunchaki kodni yozing!", 4.8),
    ("Botga kirasiz, kino kodini yozasiz, va kino darhol chiqadi!", 7.4),
    ("O'zbek tilida kinolar, har kuni yangi qismlar, hammasi bitta botda!", 5.2),
    ("Kinolar Olami. Hoziroq Telegramda kinolarr olami bot ni qidiring va kino ko'rishni boshlang!", 5.6),
]

# ------------------------------------------------------------------ yordamchilar
@lru_cache(maxsize=None)
def font(size):
    for name in ("arialbd.ttf", "segoeuib.ttf", "arial.ttf"):
        p = os.path.join("C:/Windows/Fonts", name)
        if os.path.exists(p):
            return ImageFont.truetype(p, size)
    return ImageFont.load_default()


def fit(text, maxw, size):
    while size > 20 and font(size).getlength(text) > maxw:
        size -= 4
    return font(size)


def clamp(x, a=0.0, b=1.0):
    return max(a, min(b, x))


def prog(t, start, dur):
    return clamp((t - start) / dur) if dur > 0 else (1.0 if t >= start else 0.0)


def ease_out(x):
    return 1 - (1 - x) ** 3


def ease_in_out(x):
    return 3 * x * x - 2 * x ** 3


def ease_back(x):
    c1, c3 = 1.70158, 2.70158
    return 1 + c3 * (x - 1) ** 3 + c1 * (x - 1) ** 2


def lerp(a, b, k):
    return a + (b - a) * k


def mixc(c1, c2, k):
    return tuple(int(lerp(c1[i], c2[i], k)) for i in range(3))


def scale_col(col, k):
    return tuple(int(clamp(v * k, 0, 255)) for v in col)


@lru_cache(maxsize=256)
def grad_arr(w, h, c1, c2, horizontal):
    if horizontal:
        a = np.linspace(0, 1, w)[None, :, None]
        arr = np.array(c1)[None, None, :] * (1 - a) + np.array(c2)[None, None, :] * a
        arr = np.repeat(arr, h, axis=0)
    else:
        a = np.linspace(0, 1, h)[:, None, None]
        arr = np.array(c1)[None, None, :] * (1 - a) + np.array(c2)[None, None, :] * a
        arr = np.repeat(arr, w, axis=1)
    return arr.astype(np.uint8)


def grad_image(w, h, c1, c2, horizontal=True):
    return Image.fromarray(grad_arr(int(w), int(h), tuple(c1), tuple(c2), horizontal), "RGB")


def text_mask(text, fnt, pad=30):
    l, t, r, b = fnt.getbbox(text)
    w, h = r - l, b - t
    m = Image.new("L", (w + 2 * pad, h + 2 * pad), 0)
    ImageDraw.Draw(m).text((pad - l, pad - t), text, font=fnt, fill=255)
    return m


def draw_text(canvas, text, cx, cy, fnt, fill=WHITE, alpha=1.0, grad=None, shadow=True, scale=1.0):
    if alpha <= 0.01 or scale <= 0.01:
        return
    mask = text_mask(text, fnt, 24)
    if scale != 1.0:
        mask = mask.resize((max(1, int(mask.width * scale)), max(1, int(mask.height * scale))), Image.BILINEAR)
    if alpha < 1.0:
        mask = mask.point(lambda v: int(v * alpha))
    x, y = int(cx - mask.width / 2), int(cy - mask.height / 2)
    if shadow:
        sm = mask.filter(ImageFilter.GaussianBlur(10)).point(lambda v: int(v * 0.7))
        canvas.paste((0, 0, 0), (x + 3, y + 10), sm)
    if grad:
        canvas.paste(grad_image(mask.width, mask.height, grad[0], grad[1], horizontal=True), (x, y), mask)
    else:
        canvas.paste(fill, (x, y), mask)


def draw_text3d(c, text, cx, cy, fnt, grad=((255, 236, 140), RED), depth=14, dcol=(95, 14, 20),
                alpha=1.0, scale=1.0, sweep=None, shadow=True):
    if alpha <= 0.02 or scale <= 0.02:
        return
    mask = text_mask(text, fnt, 30)
    if scale != 1.0:
        mask = mask.resize((max(1, int(mask.width * scale)), max(1, int(mask.height * scale))), Image.BILINEAR)
    if alpha < 1.0:
        mask = mask.point(lambda v: int(v * alpha))
    x, y = int(cx - mask.width / 2), int(cy - mask.height / 2)
    dep = max(1, int(depth * scale))
    if shadow:
        sm = mask.filter(ImageFilter.GaussianBlur(16)).point(lambda v: int(v * 0.75))
        c.paste((0, 0, 0), (x + 8, y + dep + 20), sm)
    for d in range(dep, 0, -2):
        c.paste(mixc(dcol, (28, 4, 8), (d / dep) * 0.55), (x + int(d * 0.5), y + d), mask)
    c.paste(grad_image(mask.width, mask.height, grad[0], grad[1], horizontal=False), (x, y), mask)
    if sweep is not None:
        mw, mh = mask.size
        xs = (np.arange(mw)[None, :] + np.arange(mh)[:, None] * 0.5) / (mw + mh * 0.5)
        band = np.exp(-((xs - (sweep * 1.6 - 0.3)) * 9) ** 2)
        hl = (np.asarray(mask, dtype=np.float32) * band * 0.95).astype(np.uint8)
        c.paste((255, 255, 255), (x, y), Image.fromarray(hl))


def slam_text(c, text, cx, cy, fnt, t, t0, stagger, grad, depth=16, sweep=None):
    widths = [fnt.getlength(ch) for ch in text]
    x = cx - sum(widths) / 2
    for i, ch in enumerate(text):
        wch = widths[i]
        ccx = x + wch / 2
        x += wch
        if ch == " ":
            continue
        tt = t - (t0 + i * stagger)
        if tt < 0:
            continue
        p = prog(tt, 0, 0.26)
        sc = 1 + 2.4 * (1 - ease_out(p))
        draw_text3d(c, ch, ccx, cy - (1 - ease_out(p)) * 50, fnt, grad=grad, depth=depth,
                    alpha=clamp(p * 3), scale=sc, sweep=sweep, shadow=(p > 0.5))


def rrect(canvas, box, radius, fill, outline=None, width=0):
    ImageDraw.Draw(canvas).rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=width)


def glass(c, fx, box, radius, alpha=0.66, border=GOLD, bw=3, glow=0.75):
    x0, y0, x1, y1 = [int(v) for v in box]
    w, h = x1 - x0, y1 - y0
    if w < 4 or h < 4:
        return
    m = Image.new("L", (w, h), 0)
    ImageDraw.Draw(m).rounded_rectangle((0, 0, w - 1, h - 1), radius=radius, fill=int(255 * alpha))
    c.paste((8, 12, 26), (x0, y0), m)
    ImageDraw.Draw(fx).rounded_rectangle((x0, y0, x1, y1), radius=radius, outline=scale_col(border, glow), width=bw)


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
    g = grad_image(s, s, (255, 110, 55), (225, 25, 60), horizontal=False)
    m = Image.new("L", (s, s), 0)
    ImageDraw.Draw(m).ellipse((10, 10, s - 10, s - 10), fill=255)
    g.putalpha(m)
    ImageDraw.Draw(g).polygon([(s * 0.40, s * 0.30), (s * 0.40, s * 0.70), (s * 0.73, s * 0.50)], fill=(255, 255, 255, 255))
    return g


def draw_play(canvas, cx, cy, r):
    if r < 4:
        return
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


# ------------------------------------------------------------------ effekt qurilish bloklari
@lru_cache(maxsize=8)
def polar_cache(cx, cy):
    hw, hh = W // 2, H // 2
    yy, xx = np.mgrid[0:hh, 0:hw].astype(np.float32)
    dx, dy = xx - cx / 2.0, yy - cy / 2.0
    return np.arctan2(dy, dx), np.hypot(dx, dy)


def rays(fx, cx, cy, t, n=16, speed=0.5, strength=0.5, color=(255, 150, 55), power=3.0, reach=0.75):
    ang, r = polar_cache(int(cx), int(cy))
    inten = (0.5 + 0.5 * np.sin(ang * n + t * speed)) ** power
    inten = inten * np.exp(-r / (H / 2 * reach)) * strength
    arr = (inten[..., None] * np.array(color, dtype=np.float32)[None, None, :]).clip(0, 255).astype(np.uint8)
    im = Image.fromarray(arr, "RGB").resize((W, H), Image.BILINEAR)
    fx.paste(ImageChops.add(fx, im))


def ring(fx, cx, cy, ts, color=(255, 205, 110), maxr=850, dur=0.9, width=28):
    p = prog(ts, 0, dur)
    if p <= 0 or p >= 1:
        return
    r = maxr * ease_out(p)
    col = scale_col(color, 1 - p)
    ImageDraw.Draw(fx).ellipse((cx - r, cy - r, cx + r, cy + r), outline=col, width=max(2, int(width * (1 - p))))


def burst(fx, cx, cy, ts, n=70, seed=1, v0=250, v1=1100, life=1.3, grav=700, cols=(GOLD, ORANGE, WHITE)):
    if ts <= 0 or ts > life:
        return
    rs = np.random.RandomState(seed)
    d = ImageDraw.Draw(fx)
    a = clamp(1 - ts / life)
    for k in range(n):
        ang = rs.rand() * 6.2832
        v = v0 + rs.rand() * (v1 - v0)
        wd = 1 + rs.rand() * 4
        col = cols[k % len(cols)]

        def pos(tt):
            f = v * tt * (1 - 0.3 * tt / life)
            return cx + math.cos(ang) * f, cy + math.sin(ang) * f + 0.5 * grav * tt * tt

        p1, p0 = pos(ts), pos(max(0.0, ts - 0.05))
        d.line((p0[0], p0[1], p1[0], p1[1]), fill=scale_col(col, a), width=max(1, int(wd * (0.5 + a))))


_CONF = [(np.random.RandomState(k).rand() * W, 120 + np.random.RandomState(k + 50).rand() * 260,
          np.random.RandomState(k + 9).rand() * 6.28, 12 + np.random.RandomState(k + 3).rand() * 16,
          [(255, 201, 74), (255, 90, 60), (255, 255, 255), (255, 140, 40)][k % 4]) for k in range(48)]


def confetti(c, tg):
    d = ImageDraw.Draw(c)
    for x0, vy, ph, sz, col in _CONF:
        y = (-60 + tg * vy + ph * 60) % (H + 120) - 60
        x = x0 + 50 * math.sin(tg * 1.7 + ph)
        a = tg * 4 + ph
        cs, sn = math.cos(a), math.sin(a)
        pts = [(x + cs * sz - sn * sz * 0.5, y + sn * sz + cs * sz * 0.5),
               (x - cs * sz - sn * sz * 0.5, y - sn * sz + cs * sz * 0.5),
               (x - cs * sz + sn * sz * 0.5, y - sn * sz - cs * sz * 0.5),
               (x + cs * sz + sn * sz * 0.5, y + sn * sz - cs * sz * 0.5)]
        d.polygon(pts, fill=col)


def find_coeffs(dst, src):
    rows = []
    for p1, p2 in zip(dst, src):
        rows.append([p1[0], p1[1], 1, 0, 0, 0, -p2[0] * p1[0], -p2[0] * p1[1]])
        rows.append([0, 0, 0, p1[0], p1[1], 1, -p2[1] * p1[0], -p2[1] * p1[1]])
    return np.linalg.solve(np.array(rows, dtype=float), np.array(src, dtype=float).reshape(8))


# ------------------------------------------------------------------ fon rasmlari
@lru_cache(maxsize=None)
def get_bg(name):
    p = os.path.join(ASSETS, name)
    if not os.path.exists(p):
        return None
    im = Image.open(p).convert("RGB")
    TW, TH = int(W * 1.5), int(H * 1.5)
    s = max(TW / im.width, TH / im.height)
    im = im.resize((int(im.width * s) + 1, int(im.height * s) + 1), Image.LANCZOS)
    l, t = (im.width - TW) // 2, (im.height - TH) // 2
    return im.crop((l, t, l + TW, t + TH))


_GRAD_BG = grad_image(W, H, (14, 18, 36), (6, 7, 16), horizontal=False)

BG_CFG = [
    # (rasm, z0, z1, panx0, panx1, pany0, pany1, qorong'ilik)
    ("bg_hero.png", 1.00, 1.30, 0.0, 0.0, 0.0, -0.2, 0.18),
    ("bg_posters.png", 1.25, 1.25, 0.0, 0.0, 0.9, -0.9, 0.42),
    ("bg_cinema.png", 1.00, 1.25, 0.0, 0.0, 0.3, -0.2, 0.50),
    ("bg_tunnel.png", 1.00, 1.70, 0.0, 0.0, 0.0, 0.0, 0.15),
    ("bg_finale.png", 1.35, 1.00, 0.0, 0.0, 0.0, 0.0, 0.12),
]


def scene_bg(si, t, dur):
    name, z0, z1, px0, px1, py0, py1, dark = BG_CFG[si]
    big = get_bg(name)
    if big is None:
        im = _GRAD_BG.copy()
    else:
        p = ease_in_out(clamp(t / dur))
        z = lerp(z0, z1, p)
        px, py = lerp(px0, px1, p), lerp(py0, py1, p)
        BW, BH = big.size
        vw, vh = BW / z, BH / z
        cx = BW / 2 + px * (BW - vw) / 2
        cy = BH / 2 + py * (BH - vh) / 2
        im = big.resize((W, H), Image.BILINEAR, box=(cx - vw / 2, cy - vh / 2, cx + vw / 2, cy + vh / 2))
    if dark > 0:
        im = im.point(lambda v: int(v * (1 - dark)))
    return im


@lru_cache(maxsize=None)
def top_shade(h, a0):
    arr = np.linspace(a0, 0, h)[:, None] * np.ones((1, W))
    return Image.fromarray(arr.astype(np.uint8), "L")


def shade_top(c, h=1000, a=190):
    c.paste((0, 0, 0), (0, 0), top_shade(h, a))


def shade_bottom(c, h=900, a=190):
    c.paste((0, 0, 0), (0, H - h), top_shade(h, a).transpose(Image.FLIP_TOP_BOTTOM))


# ------------------------------------------------------------------ sahnalar
def pill(c, fx, cx, cy, w, h, text, fnt, col=GOLD, alpha=1.0):
    if alpha <= 0.02:
        return
    glass(c, fx, (cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2), h // 2, 0.7, col, 3, 0.9 * alpha)
    draw_text(c, text, cx, cy, fnt, col, alpha=alpha, shadow=False)


def scene1(c, fx, t, dur, tg):
    rays(fx, 540, 1050, tg, n=14, speed=0.7, strength=0.30, color=(255, 120, 45))
    shade_top(c, 1050, 175)
    pill(c, fx, 540, 190, 440, 90, "TELEGRAM BOT", font(40), GOLD, ease_out(prog(t, 0.1, 0.4)))

    f1 = fit("KINO", 900, 330)
    slam_text(c, "KINO", 540, 410, f1, t, 0.30, 0.10, ((255, 240, 150), (255, 80, 40)), depth=22,
              sweep=(t * 0.55) % 1.6 if t > 1.2 else None)
    f2 = fit("KO'RISH", 900, 230)
    slam_text(c, "KO'RISH", 540, 700, f2, t, 0.80, 0.07, ((255, 255, 255), (170, 190, 255)), depth=18,
              sweep=((t - 0.4) * 0.55) % 1.6 if t > 1.5 else None)

    for tl, cx, cy, seed in ((0.95, 540, 430, 1), (1.55, 540, 700, 2)):
        ts = t - tl
        ring(fx, cx, cy, ts, maxr=900)
        burst(fx, cx, cy, ts, 80, seed)

    a = prog(t, 1.6, 0.35)
    if a > 0:
        flick = 1.0 if t > 2.1 else (0.4 + 0.6 * (int(t * 22) % 2))
        draw_text3d(c, "ENDI JUDA OSON!", 540, 905 + (1 - ease_out(a)) * 60, fit("ENDI JUDA OSON!", 900, 112),
                    grad=((255, 245, 190), (255, 160, 40)), depth=8, dcol=(110, 50, 10), alpha=a * flick)
    shade_bottom(c, 500, 150)
    draw_text(c, "Kodni yozing, kino chiqadi", 540, 1790, font(56), WHITE, alpha=prog(t, 2.2, 0.5) * (0.75 + 0.25 * math.sin(t * 6)), shadow=True)


def scene2(c, fx, t, dur, tg):
    rays(fx, 540, 1100, tg, n=10, speed=-0.5, strength=0.20, color=(255, 90, 60))
    shade_top(c, 900, 150)
    # fonda suzuvchi raqamlar
    for k in range(14):
        rs = np.random.RandomState(k + 11)
        x = 120 + rs.rand() * 840
        y = (rs.rand() * H - tg * (40 + rs.rand() * 80)) % H
        draw_text(c, str(rs.randint(0, 10)), x, y, font(int(70 + rs.rand() * 90)), GOLD, alpha=0.16, shadow=False)

    a1 = ease_out(prog(t, 0.1, 0.35))
    gl = (t < 0.6) * (0.5 + 0.5 * (int(t * 30) % 2))
    ox = int(18 * gl * math.sin(t * 90))
    draw_text(c, "Nom qidirib", 540 + ox, 330, font(118), WHITE, alpha=a1)
    draw_text(c, "vaqt yo'qotmang", 540 - ox, 470, fit("vaqt yo'qotmang", 900, 118), WHITE, alpha=a1)
    s = ease_out(prog(t, 1.25, 0.3))
    if s > 0:
        d = ImageDraw.Draw(c)
        d.line((120, 470, 120 + int(840 * s), 470), fill=RED, width=18)
        ImageDraw.Draw(fx).line((120, 470, 120 + int(840 * s), 470), fill=(120, 20, 10), width=26)

    ts = t - 1.9
    draw_text(c, "Faqat", 540, 700, font(100), GRAY, alpha=prog(t, 1.85, 0.3))
    f = fit("KOD YOZING!", 920, 170)
    slam_text(c, "KOD YOZING!", 540, 880, f, t, 1.95, 0.045, ((255, 245, 150), ORANGE), depth=20,
              sweep=((t - 2.6) * 0.7) % 1.6 if t > 2.6 else None)
    land = 1.95 + 10 * 0.045 + 0.26
    ring(fx, 540, 880, t - land, maxr=950)
    burst(fx, 540, 880, t - land, 90, 5)

    nums = ["1", "2", "3", "4", "5"]
    size, gap = 150, 22
    x0 = (W - (len(nums) * size + (len(nums) - 1) * gap)) / 2
    for i, n in enumerate(nums):
        tt = t - (2.9 + i * 0.17)
        if tt < 0:
            continue
        fp = ease_out(prog(tt, 0, 0.5))
        wf = math.sin(math.pi / 2 * fp)
        cx = x0 + i * (size + gap) + size / 2
        cy = 1290 + (1 - fp) * 120 + 12 * math.sin(tg * 3 + i)
        half = size / 2 * wf
        if half < 3:
            continue
        glass(c, fx, (cx - half, cy - size / 2, cx + half, cy + size / 2), 34, 0.8, GOLD, 4, 0.9)
        if fp > 0.55:
            draw_text(c, n, cx, cy - 4, font(104), WHITE, alpha=clamp((fp - 0.55) * 3), scale=wf, shadow=False)
        if 0 < tt < 0.9:
            burst(fx, cx, cy + 40, tt, 14, 20 + i, v0=120, v1=420, life=0.8, grav=500)
    draw_text(c, "Har bir kinoning o'z kodi bor", 540, 1560, font(54), WHITE, alpha=prog(t, 4.0, 0.5), shadow=True)


def build_phone_ui(t):
    ui = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    px0, py0, px1, py1 = 70, 380, 1010, 1640
    rrect(ui, (px0, py0, px1, py1), 64, (14, 22, 33), outline=(255, 190, 90), width=5)
    rrect(ui, (px0, py0, px1, py0 + 130), 64, (23, 33, 43))
    ImageDraw.Draw(ui).rectangle((px0 + 3, py0 + 90, px1 - 3, py0 + 130), fill=(23, 33, 43))
    lg = logo_circle(84)
    ui.paste(lg, (px0 + 43, py0 + 23), lg)
    draw_text(ui, "Kinolar Olami", px0 + 360, py0 + 48, font(44), WHITE, shadow=False)
    draw_text(ui, "bot", px0 + 160, py0 + 98, font(30), GRAY, shadow=False)

    k = ease_back(prog(t, 0.8, 0.45))
    if k > 0.05:
        bx, by = px0 + 30, py0 + 170
        w = 560 * clamp(k)
        rrect(ui, (bx, by, bx + w, by + 90), 34, (24, 37, 51))
        draw_text(ui, "Kino kodini kiriting:", bx + 280, by + 45, font(38), WHITE, alpha=prog(t, 0.95, 0.25), shadow=False)

    ix0, iy0, ix1, iy1 = px0 + 24, py1 - 120, px1 - 24, py1 - 30
    rrect(ui, (ix0, iy0, ix1, iy1), 45, (23, 33, 43))
    typed = 1.5 <= t < 2.4
    if typed:
        draw_text(ui, "1", ix0 + 60, (iy0 + iy1) / 2, font(48), WHITE, shadow=False)
        if int(t * 3) % 2 == 0:
            ImageDraw.Draw(ui).line((ix0 + 82, iy0 + 22, ix0 + 82, iy1 - 22), fill=GOLD, width=4)
    else:
        draw_text(ui, "Xabar", ix0 + 110, (iy0 + iy1) / 2, font(40), (95, 110, 130), shadow=False)
    ImageDraw.Draw(ui).ellipse((ix1 - 80, iy0 + 10, ix1 - 10, iy1 - 10), fill=GOLD if typed else (70, 85, 105))
    ImageDraw.Draw(ui).polygon([(ix1 - 60, iy0 + 22), (ix1 - 60, iy1 - 22), (ix1 - 24, (iy0 + iy1) / 2)], fill=BG)

    k = ease_back(prog(t, 2.5, 0.4))
    if k > 0.05:
        w = 130 * clamp(k)
        bx, by = px1 - 30 - w, py0 + 290
        rrect(ui, (bx, by, bx + w, by + 90), 34, (43, 82, 120))
        draw_text(ui, "1", bx + w / 2, by + 45, font(46), WHITE, alpha=prog(t, 2.6, 0.2), shadow=False)

    if 3.0 <= t < 3.8:
        bx, by = px0 + 30, py0 + 410
        rrect(ui, (bx, by, bx + 150, by + 80), 40, (24, 37, 51))
        for i in range(3):
            yy = by + 40 - 8 * max(0, math.sin(t * 8 - i * 0.9))
            ImageDraw.Draw(ui).ellipse((bx + 38 + i * 36 - 9, yy - 9, bx + 38 + i * 36 + 9, yy + 9), fill=(190, 200, 215))

    k = ease_back(prog(t, 3.8, 0.55))
    if k > 0.05:
        cw = 840
        bx, by = px0 + 30, py0 + 410
        ch = int(640 * clamp(k))
        rrect(ui, (bx, by, bx + cw, by + ch), 36, (24, 37, 51))
        if k > 0.85:
            tx0, ty0, tx1, ty1 = bx + 20, by + 20, bx + cw - 20, by + 380
            th = grad_image(tx1 - tx0, ty1 - ty0, (110, 34, 30), (14, 12, 24), horizontal=False)
            tm = Image.new("L", th.size, 0)
            ImageDraw.Draw(tm).rounded_rectangle((0, 0, th.width - 1, th.height - 1), radius=26, fill=255)
            ui.paste(th, (tx0, ty0), tm)
            draw_play(ui, (tx0 + tx1) / 2, (ty0 + ty1) / 2, 78 * (1 + 0.06 * math.sin(t * 7)))
            rrect(ui, (tx1 - 120, ty0 + 18, tx1 - 22, ty0 + 70), 14, GOLD)
            draw_text(ui, "HD", tx1 - 71, ty0 + 44, font(34), BG, shadow=False)
            draw_text(ui, "Forsaj 1 (O'zbek tilida)", bx + cw / 2, by + 430, font(44), WHITE, shadow=False)
            draw_text(ui, "Kino kodi: 1", bx + cw / 2, by + 490, font(36), GOLD, shadow=False)
            draw_text(ui, "Faqat bot ichida tomosha qilish mumkin", bx + cw / 2, by + 545, font(30), GRAY, shadow=False)
    return ui


def scene3(c, fx, t, dur, tg):
    shade_top(c, 600, 200)
    draw_text3d(c, "Kodni yozing,", 540, 150, font(94), grad=((255, 255, 255), (190, 205, 255)), depth=8, dcol=(20, 30, 70),
                alpha=ease_out(prog(t, 0.0, 0.4)))
    draw_text3d(c, "kino darhol chiqadi!", 540, 262, fit("kino darhol chiqadi!", 900, 94), grad=((255, 245, 160), ORANGE),
                depth=8, dcol=(110, 50, 10), alpha=ease_out(prog(t, 0.2, 0.4)),
                sweep=((t - 0.6) * 0.8) % 1.8 if t > 0.6 else None)

    ui = build_phone_ui(t)
    th = 0.30 * math.sin(tg * 1.15)
    lift = 22 * math.sin(tg * 1.9)
    slide = (1 - ease_out(prog(t, 0.0, 0.8))) * 1100
    cx, cy = W / 2, H / 2 + 80 + lift + slide
    sL, sR = 1 + 0.07 * math.sin(th * 2), 1 - 0.07 * math.sin(th * 2)
    xl, xr = cx - (W / 2) * math.cos(th), cx + (W / 2) * math.cos(th)
    dst = [(xl, cy - H / 2 * sL), (xr, cy - H / 2 * sR), (xr, cy + H / 2 * sR), (xl, cy + H / 2 * sL)]
    src = [(0, 0), (W, 0), (W, H), (0, H)]
    paste_glow(fx, W / 2, cy + 100, 1500, (200, 50, 30), 0.55)
    warped = ui.transform((W, H), Image.PERSPECTIVE, find_coeffs(dst, src), Image.BILINEAR)
    c.paste(warped.convert("RGB"), (0, 0), warped.split()[3])

    ts = t - 3.8
    ring(fx, W / 2, cy + 20, ts, maxr=1000, color=(255, 190, 90))
    burst(fx, W / 2, cy - 20, ts, 110, 9, v0=300, v1=1300)
    if 2.4 < t < 2.6:
        fx.paste(ImageChops.add(fx, Image.new("RGB", (W, H), (40, 28, 12))))


def check_icon(c, fx, cx, cy, r):
    d = ImageDraw.Draw(c)
    d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=GOLD)
    d.line([(cx - r * 0.45, cy + r * 0.02), (cx - r * 0.1, cy + r * 0.38), (cx + r * 0.5, cy - r * 0.35)],
           fill=BG, width=int(r * 0.22), joint="curve")
    ImageDraw.Draw(fx).ellipse((cx - r - 6, cy - r - 6, cx + r + 6, cy + r + 6), outline=(120, 90, 20), width=6)


def scene4(c, fx, t, dur, tg):
    rays(fx, 540, 960, tg, n=12, speed=0.9, strength=0.22, color=(255, 120, 50))
    shade_top(c, 700, 150)
    shade_bottom(c, 500, 140)
    a = ease_out(prog(t, 0.0, 0.4))
    draw_text3d(c, "NEGA AYNAN BIZ?", 540, 270 - (1 - a) * 80, fit("NEGA AYNAN BIZ?", 900, 98),
                grad=((255, 245, 160), ORANGE), depth=12, dcol=(110, 50, 10), alpha=a,
                sweep=((t - 0.3) * 0.8) % 1.8 if t > 0.3 else None)
    items = ["O'zbek tilida kinolar", "Faqat kod yozasiz", "Har kuni yangi kinolar", "Telefonda tez va qulay"]
    for i, it in enumerate(items):
        tt = t - (0.5 + i * 0.5)
        if tt < 0:
            continue
        k = ease_out(prog(tt, 0, 0.5))
        y = 560 + i * 250
        x_off = (1 - k) * 1200 * (1 if i % 2 == 0 else -1)
        glass(c, fx, (100 + x_off, y - 88, 980 + x_off, y + 88), 54, 0.72, GOLD, 4, 0.85)
        check_icon(c, fx, 200 + x_off, y, 48)
        draw_text(c, it, 610 + x_off, y, fit(it, 640, 56), WHITE, shadow=False)
        burst(fx, 540, y, tt - 0.45, 26, 40 + i, v0=150, v1=600, life=0.8, grav=400)
    draw_text(c, "Hammasi bitta botda", 540, 1660, font(64), WHITE, alpha=prog(t, 2.8, 0.5) * (0.8 + 0.2 * math.sin(t * 6)))


def scene5(c, fx, t, dur, tg):
    rays(fx, 540, 600, tg, n=22, speed=1.0, strength=0.55, color=(255, 170, 60), power=4.0, reach=1.0)
    confetti(c, tg)
    shade_bottom(c, 900, 160)

    # logotip 3D aylanib kiradi
    p = prog(t, 0.1, 1.0)
    ang = (1 - ease_out(p)) * 4 * math.pi
    sx = abs(math.cos(ang))
    size = int(540 * ease_back(prog(t, 0.1, 0.8)))
    pulse = 0.5 + 0.5 * math.sin(t * 4)
    if size > 10:
        paste_glow(fx, 540, 600, int(size * 2.4), (255, 100, 40), 0.55 + 0.25 * pulse)
        lg = logo_circle(size)
        w = max(4, int(size * max(sx, 0.05)))
        lg = lg.resize((w, size), Image.BILINEAR)
        c.paste(lg, (int(540 - w / 2), int(600 - size / 2)), lg)
        r = size / 2 + 10
        ImageDraw.Draw(fx).ellipse((540 - r * max(sx, 0.05), 600 - r, 540 + r * max(sx, 0.05), 600 + r), outline=(255, 190, 70), width=7)
    for k in range(4):
        ring(fx, 540, 600, (t - 0.9) - k * 0.55 if t > 0.9 else -1, maxr=760, dur=1.1, width=18)
    burst(fx, 540, 600, t - 0.9, 100, 31, v0=300, v1=1400)

    f = fit(BRAND, 900, 118)
    slam_text(c, BRAND, 540, 1010, f, t, 1.0, 0.045, ((255, 240, 150), (255, 70, 40)), depth=14,
              sweep=((t - 1.8) * 0.8) % 1.8 if t > 1.8 else None)
    draw_text(c, "Telegram bot", 540, 1115, font(52), GRAY, alpha=prog(t, 1.6, 0.4), shadow=True)

    kb = prog(t, 1.9, 0.5)
    if kb > 0:
        w = 800 * ease_back(kb)
        if w > 30:
            glass(c, fx, (540 - w / 2, 1190, 540 + w / 2, 1320), 65, 0.75, GOLD, 4, 0.95)
            draw_text(c, BOT_USERNAME, 540, 1255, fit(BOT_USERNAME, 720, 66), WHITE, alpha=prog(t, 2.1, 0.3), shadow=False)

    kc = ease_back(prog(t, 2.6, 0.5))
    if kc > 0.08:
        s = 1 + 0.045 * math.sin(t * 7)
        w, h = 780 * clamp(kc) * s, 146 * s
        cy = 1500
        paste_glow(fx, 540, cy, 1100, (255, 60, 40), 0.40 + 0.25 * pulse)
        g = grad_image(int(w), int(h), (255, 70, 40), (255, 150, 40), horizontal=True)
        m = Image.new("L", g.size, 0)
        ImageDraw.Draw(m).rounded_rectangle((0, 0, g.width - 1, g.height - 1), radius=int(h / 2), fill=255)
        c.paste(g, (int(540 - w / 2), int(cy - h / 2)), m)
        draw_text(c, "HOZIROQ KIRING", 540, cy, font(64), WHITE, alpha=prog(t, 2.8, 0.3), shadow=False)
    draw_text(c, "Havola profilda (link in bio)", 540, 1690, font(46), WHITE, alpha=prog(t, 3.3, 0.5) * (0.75 + 0.25 * math.sin(t * 5)))


SCENE_FUNCS = [scene1, scene2, scene3, scene4, scene5]

# ------------------------------------------------------------------ post-processing
@lru_cache(maxsize=None)
def vignette_img():
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    r = np.hypot((xx - W / 2) / (W / 2), (yy - H / 2) / (H / 2))
    v = np.clip(1.0 - 0.42 * r ** 2.2, 0.30, 1.0) * 255
    return Image.fromarray(v.astype(np.uint8), "L").convert("RGB")


@lru_cache(maxsize=None)
def grain_tiles():
    rs = np.random.RandomState(5)
    return [Image.fromarray(rs.randint(0, 16, (H, W, 3), dtype=np.uint8), "RGB") for _ in range(3)]


def glitch_chroma(img, amt, seed):
    d = int(2 + amt * 16)
    a = np.array(img)
    out = a.copy()
    out[:, d:, 0] = a[:, :-d, 0]
    out[:, :-d, 2] = a[:, d:, 2]
    if amt > 0.05:
        rs = np.random.RandomState(seed)
        for _ in range(int(3 + amt * 12)):
            y0 = rs.randint(0, H - 120)
            hh = rs.randint(8, int(30 + amt * 140))
            sh = int(rs.randint(-1, 2) * rs.rand() * 160 * amt)
            out[y0:y0 + hh] = np.roll(out[y0:y0 + hh], sh, axis=1)
    return Image.fromarray(out)


def post(img, tg, t, dur, si, total_dur):
    # bloom
    small = img.resize((W // 4, H // 4), Image.BILINEAR).point(lambda v: max(0, v - 135) * 2)
    glow = small.filter(ImageFilter.GaussianBlur(9)).resize((W, H), Image.BILINEAR)
    img = ImageChops.add(img, glow)
    glow2 = small.filter(ImageFilter.GaussianBlur(26)).resize((W, H), Image.BILINEAR)
    img = ImageChops.add(img, glow2)

    # sahna chegarasidagi glitch
    gl = 0.0
    if si > 0:
        gl = max(gl, 1 - t / 0.45)
    gl = max(gl, 1 - (dur - t) / 0.18) if dur - t < 0.18 and si < len(SCENE_FUNCS) - 1 else gl
    gl = clamp(gl)
    img = glitch_chroma(img, gl, int(tg * FPS) // 2 + si * 100)

    img = ImageChops.multiply(img, vignette_img())
    img = ImageChops.add(img, grain_tiles()[int(tg * FPS) % 3], scale=1.0, offset=-6)

    # musiqa urg'usiga sinxron zarba + silkinish
    ph = tg % BEAT
    punch = math.exp(-ph * 9)
    hype = 1.0
    z = 1 + 0.028 * punch * hype + 0.05 * gl
    amp = 9 * punch * hype + 22 * gl
    dx, dy = amp * math.sin(tg * 97), amp * math.cos(tg * 71)
    img = img.transform((W, H), Image.AFFINE,
                        (1 / z, 0, W / 2 - W / (2 * z) + dx, 0, 1 / z, H / 2 - H / (2 * z) + dy), Image.BILINEAR)

    # sahna boshidagi yorqin chaqnash
    if si > 0 and t < 0.5:
        k = 0.65 * math.exp(-t * 11)
        img = Image.blend(img, Image.new("RGB", (W, H), (255, 215, 160)), k)
    # video boshi va oxirida
    if tg < 0.3:
        img = Image.blend(Image.new("RGB", (W, H), (0, 0, 0)), img, tg / 0.3)
    if tg > total_dur - 0.35:
        img = Image.blend(img, Image.new("RGB", (W, H), (0, 0, 0)), clamp((tg - (total_dur - 0.35)) / 0.35))
    return img


# ------------------------------------------------------------------ render funksiyasi
_DURS = []
_STARTS = []


def init_worker(durs):
    global _DURS, _STARTS
    _DURS = list(durs)
    _STARTS = [sum(durs[:i]) for i in range(len(durs))]


def locate(tg):
    si = 0
    for i, s in enumerate(_STARTS):
        if tg >= s:
            si = i
    return si, tg - _STARTS[si], _DURS[si]


def render_frame(i):
    tg = i / FPS
    si, t, dur = locate(tg)
    c = scene_bg(si, t, dur)
    fx = Image.new("RGB", (W, H), (0, 0, 0))
    SCENE_FUNCS[si](c, fx, t, dur, tg)
    img = ImageChops.add(c, fx)
    img = post(img, tg, t, dur, si, sum(_DURS))
    return img.tobytes()


# ------------------------------------------------------------------ audio
def probe_duration(path):
    r = subprocess.run([FF, "-i", path], capture_output=True, text=True, errors="ignore")
    m = re.search(r"Duration:\s*(\d+):(\d+):(\d+\.\d+)", r.stderr)
    return int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3)) if m else 0.0


async def _tts(text, out):
    import edge_tts
    await edge_tts.Communicate(text, VOICE, rate="+6%").save(out)


def make_voice(retts=False):
    durs, files = [], []
    for i, (text, mn) in enumerate(SCENES):
        mp3 = os.path.join(TMP, f"v{i}.mp3")
        ok = os.path.exists(mp3) and os.path.getsize(mp3) > 1000 and not retts
        if not ok:
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
            subprocess.run([FF, "-y", "-i", f, "-af", "apad", "-t", f"{d:.3f}", "-ar", "44100", "-ac", "1", out], capture_output=True)
        else:
            subprocess.run([FF, "-y", "-f", "lavfi", "-i", "anullsrc=r=44100:cl=mono", "-t", f"{d:.3f}", out], capture_output=True)
        parts.append(out)
    lst = os.path.join(TMP, "list.txt")
    with open(lst, "w", encoding="utf-8") as fh:
        for p in parts:
            fh.write(f"file '{p.replace(chr(92), '/')}'\n")
    voice = os.path.join(TMP, "voice.wav")
    subprocess.run([FF, "-y", "-f", "concat", "-safe", "0", "-i", lst, "-c", "copy", voice], capture_output=True)
    return voice


def synth_music(total, starts, path, sr=44100):
    n = int((total + 1) * sr)
    out = np.zeros(n)
    rng = np.random.RandomState(3)

    def add(sig, start):
        i = int(start * sr)
        j = min(n, i + len(sig))
        if 0 <= i < n:
            out[i:j] += sig[: j - i]

    kt = np.arange(int(0.4 * sr)) / sr
    kick = np.sin(2 * np.pi * np.cumsum(45 + 110 * np.exp(-kt * 32)) / sr) * np.exp(-kt * 8)
    ht = np.arange(int(0.08 * sr)) / sr
    hat = np.diff(rng.randn(len(ht) + 1)) * np.exp(-ht * 60) * 0.28
    st = np.arange(int(0.2 * sr)) / sr
    snare = (rng.randn(len(st)) * 0.5 + np.sin(2 * np.pi * 190 * st) * 0.4) * np.exp(-st * 22) * 0.5
    roots = [55.0, 43.65, 65.41, 49.0]
    chords = [(220.0, 261.63, 329.63), (174.61, 220.0, 261.63), (261.63, 329.63, 392.0), (196.0, 246.94, 293.66)]

    t_cur, bar = 0.0, 0
    while t_cur < total + 1:
        ch = bar % 4
        for b in range(4):
            bt = t_cur + b * BEAT
            add(kick, bt)
            add(hat, bt + BEAT / 2)
            if b % 2 == 1:
                add(snare, bt)
            for h in range(2):
                nt = np.arange(int(BEAT / 2 * sr)) / sr
                f = roots[ch] * (2 if (b % 2 and h) else 1)
                add((np.sin(2 * np.pi * f * nt) + 0.45 * np.sin(2 * np.pi * 2 * f * nt)) * np.exp(-nt * 5) * 0.55, bt + h * BEAT / 2)
            for h in range(4):
                nt = np.arange(int(BEAT / 4 * sr * 1.5)) / sr
                f = chords[ch][(b * 4 + h) % 3] * 2
                add(np.sin(2 * np.pi * f * nt) * np.exp(-nt * 14) * 0.2, bt + h * BEAT / 4)
        pt = np.arange(int(4 * BEAT * sr)) / sr
        env = np.minimum(1, pt / 0.5) * np.minimum(1, (4 * BEAT - pt) / 0.5)
        add(sum(np.sin(2 * np.pi * f * pt) for f in chords[ch]) * env * 0.08, t_cur)
        t_cur += 4 * BEAT
        bar += 1

    # sahna almashuvlarida riser + zarba
    for s in starts[1:]:
        rt = np.arange(int(0.7 * sr)) / sr
        riser = (rng.randn(len(rt)) * 0.35 + np.sin(2 * np.pi * np.cumsum(200 + 1700 * (rt / 0.7) ** 2) / sr) * 0.3) * (rt / 0.7) ** 2 * 0.7
        add(riser, s - 0.7)
        it = np.arange(int(1.6 * sr)) / sr
        boom = np.sin(2 * np.pi * np.cumsum(36 + 70 * np.exp(-it * 7)) / sr) * np.exp(-it * 2.4) * 1.3
        crash = rng.randn(len(it)) * np.exp(-it * 7) * 0.45
        add(boom + crash, s)

    out = out / (np.max(np.abs(out)) + 1e-9) * 0.9
    fi = int(0.4 * sr)
    out[:fi] *= np.linspace(0, 1, fi)
    fo = int(1.6 * sr)
    end_i = int(total * sr)
    out[end_i - fo:end_i] *= np.linspace(1, 0, fo)
    out[end_i:] = 0
    with wave.open(path, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        wf.writeframes((out * 32767).astype(np.int16).tobytes())


# ------------------------------------------------------------------ main
def preview(durs):
    init_worker(durs)
    starts = _STARTS
    picks = [(0, 0.5), (0, 1.3), (0, 2.6), (1, 1.0), (1, 3.4),
             (2, 1.6), (2, 4.6), (3, 2.2), (4, 0.7), (4, 3.4)]
    tw, th = 360, 640
    sheet = Image.new("RGB", (tw * 5, th * 2))
    for k, (si, lt) in enumerate(picks):
        i = int((starts[si] + lt) * FPS)
        im = Image.frombytes("RGB", (W, H), render_frame(i)).resize((tw, th), Image.LANCZOS)
        sheet.paste(im, ((k % 5) * tw, (k // 5) * th))
    p = os.path.join(TMP, "preview.png")
    sheet.save(p)
    print("PREVIEW:", p)


def main():
    retts = "--retts" in sys.argv
    print("1/4 Ovoz (O'zbek tilida)...")
    files, durs = make_voice(retts)
    total = sum(durs)
    print(f"   Umumiy davomiylik: {total:.1f}s")
    if "--preview" in sys.argv:
        preview(durs)
        return

    print("2/4 Ovoz va musiqa...")
    voice = build_voice_track(files, durs)
    music = os.path.join(TMP, "music2.wav")
    synth_music(total, [sum(durs[:i]) for i in range(len(durs))], music)

    nframes = int(round(total * FPS))
    silent = os.path.join(TMP, "silent2.mp4")
    procs = max(2, min(8, (os.cpu_count() or 4) - 1))
    print(f"3/4 {nframes} kadr chizilmoqda ({procs} jarayon)...")
    ff = subprocess.Popen(
        [FF, "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
         "-c:v", "libx264", "-preset", "medium", "-crf", "16", "-pix_fmt", "yuv420p", "-movflags", "+faststart", silent],
        stdin=subprocess.PIPE, stderr=subprocess.DEVNULL)
    with mp.Pool(procs, initializer=init_worker, initargs=(durs,)) as pool:
        for k, data in enumerate(pool.imap(render_frame, range(nframes), chunksize=2)):
            ff.stdin.write(data)
            if k % 60 == 0:
                print(f"   {k}/{nframes}")
    ff.stdin.close()
    ff.wait()

    print("4/4 Yakuniy montaj...")
    final = os.path.join(BASE, "kinolar_olami_reklama_v2.mp4")
    flt = ("[1:a]asplit=2[v1][v2];[2:a]volume=0.55[mu];"
           "[mu][v2]sidechaincompress=threshold=0.02:ratio=9:attack=15:release=450[m];"
           "[v1]volume=1.5[v];[v][m]amix=inputs=2:duration=first:normalize=0[a]")
    r = subprocess.run([FF, "-y", "-i", silent, "-i", voice, "-i", music, "-filter_complex", flt,
                        "-map", "0:v", "-map", "[a]", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-shortest", final],
                       capture_output=True, text=True, errors="ignore")
    if not os.path.exists(final):
        print(r.stderr[-1500:])
    print("TAYYOR:", final, f"({os.path.getsize(final) / 1048576:.1f} MB)")


if __name__ == "__main__":
    mp.freeze_support()
    main()
