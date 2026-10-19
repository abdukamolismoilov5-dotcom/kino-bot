# -*- coding: utf-8 -*-
import os
import cv2
import numpy as np

DEMO_VIDEO_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "demo_kino.mp4")


def ensure_demo_video() -> str:
    """
    Agar kino uchun admin hali katta video fayl biriktirmagan bo'lsa,
    bot test paytidayoq haqiqiy himoyalangan (protect_content=True) video
    jo'natib bera olishi uchun maxsus HD MP4 video yaratadi.
    """
    if os.path.exists(DEMO_VIDEO_PATH) and os.path.getsize(DEMO_VIDEO_PATH) > 10000:
        return DEMO_VIDEO_PATH

    width, height = 1280, 720
    fps = 24
    duration_sec = 5
    total_frames = fps * duration_sec

    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    out = cv2.VideoWriter(DEMO_VIDEO_PATH, fourcc, fps, (width, height))

    for i in range(total_frames):
        frame = np.zeros((height, width, 3), dtype=np.uint8)

        # To'q kino-zal foni gradienti
        for y in range(height):
            val = int(15 + (y / height) * 35)
            frame[y, :] = (val + 15, val, val - 5 if val >= 5 else 0)

        # Oltin/Qizil chiziqli ramka
        cv2.rectangle(frame, (40, 40), (width - 40, height - 40), (0, 165, 255), 3)
        cv2.rectangle(frame, (55, 55), (width - 55, height - 55), (50, 50, 200), 1)

        # Animatsion progress effekt
        pulse = int(abs(np.sin(i / 8.0)) * 60)
        cv2.circle(frame, (width // 2, 220), 65, (0, 140 + pulse, 255), -1)
        # Play uchburchagi
        pts = np.array([
            [width // 2 - 20, 190],
            [width // 2 - 20, 250],
            [width // 2 + 30, 220]
        ], np.int32)
        cv2.fillPoly(frame, [pts], (255, 255, 255))

        # Yozuvlar
        cv2.putText(
            frame, "VIP KINO BOT - FULL HD",
            (width // 2 - 310, 355),
            cv2.FONT_HERSHEY_DUPLEX, 1.5, (255, 255, 255), 3, cv2.LINE_AA
        )
        cv2.putText(
            frame, "HIMOYALANGAN KINO PLEER (SAQLASH VA UZATISH TAQIQLANGAN)",
            (width // 2 - 470, 420),
            cv2.FONT_HERSHEY_SIMPLEX, 0.85, (0, 215, 255), 2, cv2.LINE_AA
        )
        cv2.putText(
            frame, "Admin panel (/admin) orqali to'liq kino faylini yuklashingiz mumkin",
            (width // 2 - 460, 500),
            cv2.FONT_HERSHEY_SIMPLEX, 0.8, (200, 200, 200), 2, cv2.LINE_AA
        )

        # Pastki progress bar
        bar_w = int(((i + 1) / total_frames) * (width - 200))
        cv2.rectangle(frame, (100, 580), (width - 100, 600), (60, 60, 60), -1)
        cv2.rectangle(frame, (100, 580), (100 + bar_w, 600), (0, 180, 255), -1)

        out.write(frame)

    out.release()
    return DEMO_VIDEO_PATH
