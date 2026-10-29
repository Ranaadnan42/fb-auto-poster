"""
Web Builder videos ke liye ASAL product jaisi pics (Pillow se):
POS billing screen, sales/stock report, laptop par website, phone par app, WhatsApp contact card.
Business ki asal photos demo_img/ se aati hain - is liye har pic video ke topic se related hoti hai.
Koi price (hamari qeemat) in pics par nahi likhi jati.
"""
import os
import random

from PIL import Image, ImageDraw, ImageFilter, ImageFont

FONTS = os.path.abspath("fonts")
DEMO = os.path.abspath("demo_img")
GREEN = (25, 195, 125)
DARK = (8, 28, 22)

# BUSINESSES (wb_video) -> demo_img folder
FOLDER = {"restaurant": "restaurant", "grocery store": "grocery", "pharmacy": "pharmacy",
          "clothing shop": "fashion", "beauty salon": "salon", "school": "education", "clinic": "clinic",
          "mobile phone shop": "electronics", "bakery": "bakery", "hardware store": "construction",
          "cafe": "cafe", "supermarket": "grocery", "electronics shop": "electronics",
          "real estate agency": "realestate", "gym": "gym", "car workshop": "auto",
          "furniture store": "furniture", "wholesale distributor": "business", "jewellery shop": "jewellery",
          "travel agency": "travel"}

ITEMS = {"restaurant": ["Chicken Biryani", "Zinger Burger", "Fries Large", "Cold Drink", "Kheer"],
         "grocery": ["Basmati Rice 5kg", "Cooking Oil 1L", "Sugar 1kg", "Tea Pack", "Milk 1L"],
         "pharmacy": ["Paracetamol", "Vitamin C", "Cough Syrup", "Bandage Roll", "Hand Sanitizer"],
         "fashion": ["Cotton Shirt", "Denim Jeans", "Ladies Suit", "Kids T-Shirt", "Scarf"],
         "electronics": ["Phone Charger", "Earbuds", "Power Bank", "USB Cable", "Screen Guard"],
         "bakery": ["Chocolate Cake", "Bread Loaf", "Cookies Box", "Pizza Slice", "Donut"],
         "cafe": ["Cappuccino", "Latte", "Club Sandwich", "Brownie", "Fresh Juice"]}
DEFAULT_ITEMS = ["Item A - Pack", "Item B - Box", "Item C", "Item D - 1kg", "Item E"]


def font(size, arabic=False):
    name = "NotoNaskhArabic-Bold.ttf" if arabic else "NotoSans-Bold.ttf"
    try:
        return ImageFont.truetype(os.path.join(FONTS, name), size)
    except Exception:
        return ImageFont.load_default()


def folder(spot):
    return FOLDER.get(spot, "business")


def photo(spot, n=None):
    d = os.path.join(DEMO, folder(spot))
    try:
        files = sorted(f for f in os.listdir(d) if f.lower().endswith((".jpg", ".png")))
    except Exception:
        files = []
    if not files:
        return None
    f = files[n % len(files)] if n is not None else random.choice(files)
    return Image.open(os.path.join(d, f)).convert("RGB")


def cover(img, w, h):
    s = max(w / img.width, h / img.height)
    img = img.resize((max(w, int(img.width * s)), max(h, int(img.height * s))), Image.LANCZOS)
    x, y = (img.width - w) // 2, (img.height - h) // 2
    return img.crop((x, y, x + w, y + h))


def background(W, H, spot):
    p = photo(spot)
    if p:
        bg = cover(p, W, H).filter(ImageFilter.GaussianBlur(28))
        bg = Image.blend(bg, Image.new("RGB", (W, H), DARK), 0.72)
    else:
        bg = Image.new("RGB", (W, H), DARK)
    return bg


def rr(d, box, r, fill, outline=None, width=0):
    d.rounded_rectangle(box, r, fill=fill, outline=outline, width=width)


def shadow(base, box, r):
    sh = Image.new("RGBA", base.size, (0, 0, 0, 0))
    ImageDraw.Draw(sh).rounded_rectangle((box[0] + 10, box[1] + 18, box[2] + 10, box[3] + 18), r,
                                         fill=(0, 0, 0, 150))
    base.paste(sh.filter(ImageFilter.GaussianBlur(18)), (0, 0), sh.filter(ImageFilter.GaussianBlur(18)))


# ------------------------------------------------------------------ screens (content inside device)
def pos_screen(w, h, spot):
    im = Image.new("RGB", (w, h), (244, 247, 246))
    d = ImageDraw.Draw(im)
    u = h / 100
    d.rectangle((0, 0, w, 9 * u), fill=(10, 60, 45))
    d.text((2 * u, 2 * u), "RANA POS", font=font(int(4.5 * u)), fill=GREEN)
    d.text((w - 34 * u, 2.6 * u), "Bill # 1048   Cashier: Ali", font=font(int(3 * u)), fill=(220, 235, 230))
    items = ITEMS.get(folder(spot), DEFAULT_ITEMS)
    lw = int(w * 0.6)
    rr(d, (2 * u, 12 * u, lw, 97 * u), int(1.5 * u), (255, 255, 255))
    d.text((4 * u, 14 * u), "ITEM", font=font(int(3 * u)), fill=(90, 110, 100))
    d.text((lw - 26 * u, 14 * u), "QTY", font=font(int(3 * u)), fill=(90, 110, 100))
    d.text((lw - 13 * u, 14 * u), "AMT", font=font(int(3 * u)), fill=(90, 110, 100))
    y = 20 * u
    total = 0
    for i, it in enumerate(items):
        q = random.randint(1, 3)
        a = random.choice([120, 180, 250, 90, 340, 60]) * q
        total += a
        if i % 2 == 0:
            d.rectangle((3 * u, y - u, lw - u, y + 8 * u), fill=(238, 248, 243))
        d.text((4 * u, y), it, font=font(int(3.6 * u)), fill=(25, 40, 35))
        d.text((lw - 24 * u, y), str(q), font=font(int(3.6 * u)), fill=(25, 40, 35))
        d.text((lw - 13 * u, y), str(a), font=font(int(3.6 * u)), fill=(25, 40, 35))
        y += 10 * u
    # barcode
    bx = 4 * u
    for k in range(int(30 * u / 4)):
        bw = random.choice([2, 3, 5])
        d.rectangle((bx, 80 * u, bx + bw, 92 * u), fill=(20, 20, 20))
        bx += bw + 2
    d.text((bx + 2 * u, 83 * u), "Barcode scan", font=font(int(3 * u)), fill=(90, 110, 100))
    x0 = lw + 2 * u
    rr(d, (x0, 12 * u, w - 2 * u, 40 * u), int(1.5 * u), (10, 60, 45))
    d.text((x0 + 3 * u, 15 * u), "TOTAL", font=font(int(3.4 * u)), fill=(200, 230, 215))
    d.text((x0 + 3 * u, 22 * u), f"{total:,}", font=font(int(10 * u)), fill=GREEN)
    for j, (t, c) in enumerate([("PAY  CASH", GREEN), ("PRINT BILL", (40, 120, 220)),
                                ("HOLD", (230, 150, 40))]):
        yy = 44 * u + j * 17 * u
        rr(d, (x0, yy, w - 2 * u, yy + 14 * u), int(1.5 * u), c)
        d.text((x0 + 3 * u, yy + 4 * u), t, font=font(int(4.2 * u)), fill=(255, 255, 255))
    return im


def report_screen(w, h, spot):
    im = Image.new("RGB", (w, h), (244, 247, 246))
    d = ImageDraw.Draw(im)
    u = h / 100
    d.rectangle((0, 0, w, 9 * u), fill=(10, 60, 45))
    d.text((2 * u, 2 * u), "RANA POS  -  Reports", font=font(int(4.5 * u)), fill=GREEN)
    cards = [("Today Sales", f"{random.randint(38, 96)},{random.randint(100, 999)}"),
             ("Profit", f"{random.randint(8, 22)},{random.randint(100, 999)}"),
             ("Bills", str(random.randint(80, 240))), ("Low Stock", str(random.randint(3, 9)))]
    cw = (w - 10 * u) / 4
    for i, (t, v) in enumerate(cards):
        x = 2 * u + i * (cw + 2 * u)
        rr(d, (x, 12 * u, x + cw, 30 * u), int(1.5 * u), (255, 255, 255))
        d.text((x + 2 * u, 14 * u), t, font=font(int(3 * u)), fill=(90, 110, 100))
        d.text((x + 2 * u, 20 * u), v, font=font(int(6 * u)), fill=(10, 90, 60) if i != 3 else (220, 90, 40))
    rr(d, (2 * u, 33 * u, w * 0.62, 97 * u), int(1.5 * u), (255, 255, 255))
    d.text((4 * u, 35 * u), "Daily Sales - This Week", font=font(int(3.2 * u)), fill=(60, 80, 70))
    days = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    bw = (w * 0.62 - 10 * u) / 7
    for i, dd in enumerate(days):
        bh = random.uniform(18, 46) * u
        x = 4 * u + i * bw
        d.rectangle((x + bw * 0.2, 90 * u - bh, x + bw * 0.8, 90 * u), fill=GREEN)
        d.text((x + bw * 0.22, 91.5 * u), dd, font=font(int(2.6 * u)), fill=(90, 110, 100))
    x0 = w * 0.62 + 2 * u
    rr(d, (x0, 33 * u, w - 2 * u, 97 * u), int(1.5 * u), (255, 255, 255))
    d.text((x0 + 2 * u, 35 * u), "Stock", font=font(int(3.2 * u)), fill=(60, 80, 70))
    for i, it in enumerate(ITEMS.get(folder(spot), DEFAULT_ITEMS)):
        y = 42 * u + i * 10 * u
        st = random.randint(2, 140)
        d.text((x0 + 2 * u, y), it[:16], font=font(int(2.9 * u)), fill=(25, 40, 35))
        d.text((w - 12 * u, y), str(st), font=font(int(2.9 * u)),
               fill=(220, 90, 40) if st < 10 else (10, 90, 60))
    return im


def web_screen(w, h, spot, title):
    im = Image.new("RGB", (w, h), (255, 255, 255))
    d = ImageDraw.Draw(im)
    u = h / 100
    d.rectangle((0, 0, w, 6 * u), fill=(235, 238, 237))
    for k, c in enumerate([(240, 90, 80), (245, 190, 60), (60, 200, 90)]):
        d.ellipse((1.5 * u + k * 3 * u, 1.8 * u, 3.6 * u + k * 3 * u, 3.9 * u), fill=c)
    rr(d, (14 * u, 1.2 * u, w - 6 * u, 4.8 * u), int(1.5 * u), (255, 255, 255))
    d.text((16 * u, 1.6 * u), f"www.{''.join(title.lower().split())[:18]}.com", font=font(int(2.4 * u)),
           fill=(90, 100, 95))
    d.rectangle((0, 6 * u, w, 14 * u), fill=(255, 255, 255))
    d.text((3 * u, 7.8 * u), title, font=font(int(3.8 * u)), fill=(10, 90, 60))
    nav = ["Home", "Menu" if folder(spot) in ("restaurant", "cafe", "bakery") else "Products", "About", "Contact"]
    for i, n in enumerate(nav):
        d.text((w - (len(nav) - i) * 14 * u, 8.6 * u), n, font=font(int(2.8 * u)), fill=(60, 70, 65))
    hero = photo(spot, 0)
    if hero:
        im.paste(cover(hero, w, int(52 * u)), (0, int(14 * u)))
    ov = Image.new("RGBA", (w, int(52 * u)), (0, 0, 0, 110))
    im.paste(ov, (0, int(14 * u)), ov)
    d = ImageDraw.Draw(im)
    d.text((5 * u, 28 * u), title, font=font(int(8 * u)), fill=(255, 255, 255))
    d.text((5 * u, 40 * u), "Order online - fast delivery", font=font(int(3.8 * u)), fill=(230, 240, 235))
    rr(d, (5 * u, 49 * u, 30 * u, 57 * u), int(4 * u), GREEN)
    d.text((8 * u, 50.6 * u), "ORDER NOW", font=font(int(3.4 * u)), fill=(255, 255, 255))
    cw = (w - 8 * u) / 3
    for i in range(3):
        x = 2 * u + i * (cw + 2 * u)
        p = photo(spot, i + 1)
        if p:
            im.paste(cover(p, int(cw), int(22 * u)), (int(x), int(69 * u)))
        d.rectangle((x, 91 * u, x + cw, 99 * u), fill=(244, 247, 246))
        d.text((x + 1.5 * u, 92.3 * u), ["Best Sellers", "New Arrivals", "Special Offers"][i],
               font=font(int(3 * u)), fill=(25, 40, 35))
    return im


def app_screen(w, h, spot, title):
    im = Image.new("RGB", (w, h), (246, 248, 247))
    d = ImageDraw.Draw(im)
    u = w / 100
    d.rectangle((0, 0, w, 30 * u), fill=(10, 60, 45))
    d.text((6 * u, 8 * u), title[:18], font=font(int(7 * u)), fill=(255, 255, 255))
    rr(d, (6 * u, 18 * u, w - 6 * u, 26 * u), int(4 * u), (255, 255, 255))
    d.text((10 * u, 19.6 * u), "Search...", font=font(int(4 * u)), fill=(140, 150, 145))
    y = 34 * u
    for i in range(4):
        rr(d, (5 * u, y, w - 5 * u, y + 30 * u), int(3 * u), (255, 255, 255))
        p = photo(spot, i)
        if p:
            im.paste(cover(p, int(32 * u), int(24 * u)), (int(8 * u), int(y + 3 * u)))
        it = ITEMS.get(folder(spot), DEFAULT_ITEMS)[i]
        d.text((44 * u, y + 5 * u), it[:16], font=font(int(4.6 * u)), fill=(25, 40, 35))
        d.text((44 * u, y + 13 * u), "In stock", font=font(int(3.6 * u)), fill=(90, 130, 110))
        rr(d, (44 * u, y + 20 * u, 80 * u, y + 27 * u), int(3.5 * u), GREEN)
        d.text((50 * u, y + 21 * u), "Add to cart", font=font(int(3.4 * u)), fill=(255, 255, 255))
        y += 34 * u
    d.rectangle((0, h - 16 * u, w, h), fill=(255, 255, 255))
    for i, t in enumerate(["Home", "Orders", "Cart", "Profile"]):
        d.text((6 * u + i * 24 * u, h - 11 * u), t, font=font(int(3.8 * u)),
               fill=GREEN if i == 0 else (120, 130, 125))
    return im


# ------------------------------------------------------------------ devices
def monitor(W, H, spot, screen_fn, label):
    bg = background(W, H, spot).convert("RGBA")
    vertical = H > W
    sw = int(W * (0.9 if vertical else 0.6))
    sh = int(sw * 0.6)
    x, y = (W - sw) // 2, int(H * (0.28 if vertical else 0.18))
    b = int(sw * 0.02)
    shadow(bg, (x - b, y - b, x + sw + b, y + sh + b), b)
    d = ImageDraw.Draw(bg)
    rr(d, (x - b, y - b, x + sw + b, y + sh + b), b, (25, 28, 30))
    bg.paste(screen_fn(sw, sh), (x, y))
    d.rectangle((W // 2 - sw // 14, y + sh + b, W // 2 + sw // 14, y + sh + b + sw // 14), fill=(40, 44, 46))
    rr(d, (W // 2 - sw // 6, y + sh + b + sw // 14, W // 2 + sw // 6, y + sh + b + sw // 11), 8, (40, 44, 46))
    return bg.convert("RGB")


def laptop(W, H, spot, title):
    bg = background(W, H, spot).convert("RGBA")
    vertical = H > W
    sw = int(W * (0.92 if vertical else 0.6))
    sh = int(sw * 0.62)
    x, y = (W - sw) // 2, int(H * (0.28 if vertical else 0.17))
    b = int(sw * 0.025)
    shadow(bg, (x - b, y - b, x + sw + b, y + sh + b * 3), b)
    d = ImageDraw.Draw(bg)
    rr(d, (x - b, y - b, x + sw + b, y + sh + b), b, (28, 30, 32))
    bg.paste(web_screen(sw, sh, spot, title), (x, y))
    d.polygon([(x - b * 3, y + sh + b), (x + sw + b * 3, y + sh + b), (x + sw + b * 5, y + sh + b * 3),
               (x - b * 5, y + sh + b * 3)], fill=(190, 195, 198))
    return bg.convert("RGB")


def phone(W, H, spot, title):
    bg = background(W, H, spot).convert("RGBA")
    vertical = H > W
    ph = int(H * (0.6 if vertical else 0.7))
    pw = int(ph * 0.49)
    x = (W - pw) // 2 if vertical else int(W * 0.6)
    y = int(H * (0.2 if vertical else 0.16))
    b = int(pw * 0.04)
    shadow(bg, (x - b, y - b, x + pw + b, y + ph + b), b * 3)
    d = ImageDraw.Draw(bg)
    rr(d, (x - b, y - b, x + pw + b, y + ph + b), b * 3, (20, 22, 24))
    scr = app_screen(pw, ph, spot, title)
    m = Image.new("L", (pw, ph), 0)
    ImageDraw.Draw(m).rounded_rectangle((0, 0, pw, ph), b * 2, fill=255)
    bg.paste(scr, (x, y), m)
    if not vertical:   # khaali jagah mein business photo
        p = photo(spot, 2)
        if p:
            bw, bh = int(W * 0.44), int(H * 0.56)
            bg.paste(cover(p, bw, bh), (int(W * 0.1), int(H * 0.2)))
    return bg.convert("RGB")


def contact(W, H, spot, wa, site):
    bg = background(W, H, spot)
    d = ImageDraw.Draw(bg)
    cw = int(W * (0.86 if H > W else 0.6))
    chh = int(cw * 0.55)
    x, y = (W - cw) // 2, int(H * (0.34 if H > W else 0.18))
    rr(d, (x, y, x + cw, y + chh), int(cw * 0.04), (255, 255, 255))
    u = cw / 100
    d.ellipse((x + 6 * u, y + 8 * u, x + 22 * u, y + 24 * u), fill=(37, 211, 102))
    d.text((x + 10.5 * u, y + 10 * u), "W", font=font(int(10 * u)), fill=(255, 255, 255))
    d.text((x + 27 * u, y + 9 * u), "WhatsApp", font=font(int(6 * u)), fill=(20, 40, 30))
    d.text((x + 27 * u, y + 17 * u), "Web Builder", font=font(int(4 * u)), fill=(90, 110, 100))
    d.text((x + 6 * u, y + 30 * u), wa, font=font(int(8.5 * u)), fill=(10, 120, 70))
    d.text((x + 6 * u, y + 43 * u), site, font=font(int(4.4 * u)), fill=(60, 80, 70))
    return bg


def business(W, H, spot):
    p = photo(spot)
    if not p:
        return background(W, H, spot)
    return cover(p, W, H)


def make(kind, W, H, spot, path, title="", wa="", site=""):
    """kind: pos | report | website | app | contact | business"""
    if kind == "pos":
        im = monitor(W, H, spot, lambda w, h: pos_screen(w, h, spot), "POS")
    elif kind == "report":
        im = monitor(W, H, spot, lambda w, h: report_screen(w, h, spot), "REPORT")
    elif kind == "website":
        im = laptop(W, H, spot, title)
    elif kind == "app":
        im = phone(W, H, spot, title)
    elif kind == "contact":
        im = contact(W, H, spot, wa, site)
    else:
        im = business(W, H, spot)
    im.save(path, quality=92)
    return path


if __name__ == "__main__":
    os.makedirs("mock_test", exist_ok=True)
    for k in ("pos", "report", "website", "app", "contact", "business"):
        for (w, h) in ((1920, 1080), (1080, 1920)):
            make(k, w, h, "restaurant", f"mock_test/{k}_{w}.jpg", "Al Noor Restaurant",
                 "+92 307 5267349", "client-hunt-six.vercel.app")
    print("ok")
