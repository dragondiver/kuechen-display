"""Screenshots des drehbaren Modells der Projektseite aus acht Richtungen.

Öffnet die Seite im installierten Chrome ohne Fenster, dreht das Modell mit der Maus
in 45°-Schritten und legt die Bilder nach projektseite/.

Aufruf aus dem Repo:
    uv run --with playwright --with pillow python gehaeuse/zielentwurf/projektseite.py
"""

import os
import sys

from PIL import Image
from playwright.sync_api import sync_playwright

URL = "https://dragondiver.github.io/kuechen-display/projekt/"
ZIEL = os.path.join(os.path.dirname(os.path.abspath(__file__)), "projektseite")
GRAD_JE_PIXEL = 0.45  # aus docs/projekt/index.html: dreh.az -= dx * .45
SCHRITT = 45


def ziehen(seite, x, y, dx, dy=0):
    seite.mouse.move(x, y)
    seite.mouse.down()
    for i in range(1, 11):
        seite.mouse.move(x + dx * i / 10, y + dy * i / 10)
    seite.mouse.up()
    seite.wait_for_timeout(1200)


if __name__ == "__main__":
    url = sys.argv[1] if len(sys.argv) > 1 else URL
    os.makedirs(ZIEL, exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch(
            channel="chrome",
            headless=True,
            args=["--use-angle=metal", "--enable-webgl"],
        )
        seite = browser.new_page(
            viewport={"width": 1400, "height": 1000}, device_scale_factor=1.5
        )
        seite.goto(url, wait_until="networkidle")
        seite.wait_for_timeout(4000)
        cv = seite.locator("#gl")
        cv.scroll_into_view_if_needed()
        r = cv.bounding_box()
        x, y = r["x"] + r["width"] / 2, r["y"] + r["height"] / 2
        dateien = []
        for i in range(360 // SCHRITT):
            name = f"seite_{i + 1}.jpg"  # Bild 1 ist die Startansicht der Seite, danach je 45° weiter
            cv.screenshot(path=os.path.join(ZIEL, name), type="jpeg", quality=88)
            dateien.append(name)
            ziehen(seite, x, y, -SCHRITT / GRAD_JE_PIXEL)
        ziehen(seite, x, y, 0, 200)  # Blick von oben, bis zum Anschlag der Seite
        cv.screenshot(
            path=os.path.join(ZIEL, "seite_von_oben.jpg"), type="jpeg", quality=88
        )
        browser.close()
    b, h = Image.open(os.path.join(ZIEL, dateien[0])).size
    b, h = b // 3, h // 3
    blatt = Image.new("RGB", (4 * b, 2 * h), (255, 255, 255))
    for i, d in enumerate(dateien):
        blatt.paste(
            Image.open(os.path.join(ZIEL, d)).convert("RGB").resize((b, h)),
            ((i % 4) * b, (i // 4) * h),
        )
    blatt.save(os.path.join(ZIEL, "seite_uebersicht.jpg"), quality=88)
    print("fertig:", ZIEL)
