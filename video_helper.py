# -*- coding: utf-8 -*-
import os

DEMO_VIDEO_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "demo_kino.mp4")


def ensure_demo_video() -> str:
    """
    Agar demo_kino.mp4 mavjud bo'lsa yo'lini qaytaradi.
    Agar mavjud bo'lmasa va cv2 o'rnatilgan bo'lsa, yaratadi.
    Aks holda xatolik bermay xavfsiz ishlaydi.
    """
    if os.path.exists(DEMO_VIDEO_PATH) and os.path.getsize(DEMO_VIDEO_PATH) > 1000:
        return DEMO_VIDEO_PATH

    try:
        import cv2
        import numpy as np

        width, height = 1280, 720
        fps = 24
        duration_sec = 5
        total_frames = fps * duration_sec

        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
        out = cv2.VideoWriter(DEMO_VIDEO_PATH, fourcc, fps, (width, height))

        for i in range(total_frames):
            frame = np.zeros((height, width, 3), dtype=np.uint8)
            for y in range(height):
                val = int(15 + (y / height) * 35)
                frame[y, :] = (val + 15, val, val - 5 if val >= 5 else 0)

            cv2.rectangle(frame, (40, 40), (width - 40, height - 40), (0, 165, 255), 3)
            cv2.putText(
                frame, "VIP KINO BOT - FULL HD",
                (width // 2 - 310, 355),
                cv2.FONT_HERSHEY_DUPLEX, 1.5, (255, 255, 255), 3, cv2.LINE_AA
            )
            out.write(frame)

        out.release()
        return DEMO_VIDEO_PATH
    except Exception:
        return DEMO_VIDEO_PATH
