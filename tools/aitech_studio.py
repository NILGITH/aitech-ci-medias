#!/usr/bin/env python3
"""
AITECH Studio — moteur de visuels (images PNG) et vidéos (MP4) aux couleurs d'AITECH Côte d'Ivoire.

Usage :
  python3 aitech_studio.py image spec.json sortie.png
  python3 aitech_studio.py video spec.json sortie.mp4

spec.json (image) :
  {"format": "square|portrait|story|landscape",
   "offre": "dev|infra|pay|com|presence|marque",
   "surtitre": "Infrastructure & sécurité",
   "titre": "Vos données valent plus que votre serveur",
   "sous_titre": "Sauvegarde NAS automatique, restauration en minutes.",
   "points": ["Sauvegarde quotidienne", "Accès à distance", "Maintenance incluse"],
   "cta": "Diagnostic gratuit : petronildaga@aitech-ci.com"}

spec.json (vidéo) :
  {"format": "story|square|portrait|landscape", "offre": "infra",
   "duree_scene": 3.5,
   "scenes": [ {même structure qu'une image, sans format/offre}, ... ]}
  -> 3 à 6 scènes conseillées ; la dernière scène porte le CTA.

Dépendances : pillow (pip install --break-system-packages pillow), ffmpeg.
"""
import json, math, os, random, subprocess, sys, tempfile, shutil
from PIL import Image, ImageDraw, ImageFont, ImageFilter

FORMATS = {
    "square": (1080, 1080),
    "portrait": (1080, 1350),
    "story": (1080, 1920),
    "landscape": (1200, 627),
}

NAVY = (8, 27, 51)
NAVY2 = (14, 52, 92)
WHITE = (255, 255, 255)
MUTED = (184, 201, 222)
ACCENTS = {
    "dev": ((0, 168, 232), "Développement web & mobile"),
    "infra": ((230, 72, 72), "Infrastructure & sécurité"),
    "pay": ((22, 190, 120), "Paiement & fintech"),
    "com": ((236, 86, 160), "Communication & digital"),
    "presence": ((245, 146, 32), "Gestion de présence"),
    "marque": ((245, 146, 32), "AITECH Côte d'Ivoire"),
}
TAGLINE = "Connecter, Innover, Transformer."
FOOTER = "AITECH Côte d'Ivoire  ·  aitech-ci.com"

FONT_DIRS = ["/usr/share/fonts/truetype/google-fonts", "/usr/share/fonts/truetype/dejavu"]


def font(weight, size):
    names = {
        "bold": ["Poppins-Bold.ttf", "DejaVuSans-Bold.ttf"],
        "medium": ["Poppins-Medium.ttf", "DejaVuSans-Bold.ttf"],
        "regular": ["Poppins-Regular.ttf", "DejaVuSans.ttf"],
        "light": ["Poppins-Light.ttf", "DejaVuSans.ttf"],
    }[weight]
    for n in names:
        for d in FONT_DIRS:
            p = os.path.join(d, n)
            if os.path.exists(p):
                return ImageFont.truetype(p, size)
    return ImageFont.load_default()


def wrap(draw, text, fnt, max_w):
    words, lines, cur = text.split(), [], ""
    for w in words:
        test = (cur + " " + w).strip()
        if draw.textlength(test, font=fnt) <= max_w:
            cur = test
        else:
            if cur:
                lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


def background(w, h, accent, seed):
    img = Image.new("RGB", (w, h), NAVY)
    px = img.load()
    for y in range(h):
        t = y / h
        c = tuple(int(NAVY[i] * (1 - t) + NAVY2[i] * t) for i in range(3))
        for x in range(w):
            px[x, y] = c
    # halo d'accent
    glow = Image.new("RGB", (w, h), (0, 0, 0))
    gd = ImageDraw.Draw(glow)
    r = int(max(w, h) * 0.45)
    gd.ellipse([w - r, -r // 2, w + r, r + r // 2], fill=tuple(int(a * 0.55) for a in accent))
    glow = glow.filter(ImageFilter.GaussianBlur(r // 3))
    img = Image.blend(img, Image.composite(glow, img, glow.convert("L")), 0.6)
    # motif "circuit" : noeuds reliés, discret
    d = ImageDraw.Draw(img, "RGBA")
    rnd = random.Random(seed)
    top = int(min(h * 0.20, w * 0.24))
    nodes = [(rnd.randint(int(w * 0.50), w - 20), rnd.randint(20, top)) for _ in range(12)]
    for i, (x, y) in enumerate(nodes):
        x2, y2 = nodes[(i + 3) % len(nodes)]
        d.line([(x, y), (x2, y), (x2, y2)], fill=(255, 255, 255, 28), width=2)
    for x, y in nodes:
        d.ellipse([x - 5, y - 5, x + 5, y + 5], fill=accent + (150,))
    return img


def _layout(spec, size, accent, offer_label, img, k, draw_it):
    """Place le contenu ; renvoie True si tout tient au-dessus du CTA."""
    w, h = size
    d = ImageDraw.Draw(img)
    land = w > h
    story = h / w > 1.6
    u = min(w, h) / 1080          # unité de base (logo, pied)
    t = u * k                     # unité du texte principal (réduite si débordement)
    m = int(w * 0.08) if not land else int(w * 0.06)

    # zone basse : pied + CTA
    ff = font("regular", int(26 * u)); fi = font("medium", int(26 * u))
    one_line_footer = m + d.textlength(FOOTER, font=ff) + d.textlength(TAGLINE, font=fi) + 40 * u < w - m
    by = h - m - int((70 if one_line_footer else 110) * u)
    limit = by - int(20 * u)
    cta_lines = []
    if spec.get("cta"):
        fc = font("bold", int(32 * t))
        cta_lines = wrap(d, spec["cta"], fc, w - 2 * m - 60 * u)
        bh = int(len(cta_lines) * fc.size * 1.3 + 36 * u)
        cta_top = limit - bh
        limit = cta_top - int(30 * u)

    # en-tête
    if draw_it:
        fl = font("bold", int(46 * u))
        d.text((m, m), "AITECH", font=fl, fill=WHITE)
        lw = d.textlength("AITECH", font=fl)
        d.text((m + lw + 10 * u, m + 8 * u), "CI", font=fl, fill=accent)
    y = int(h * (0.30 if story else 0.22)) if not land else int(m + 90 * u)

    sur = spec.get("surtitre") or offer_label
    fs = font("medium", int(30 * t))
    if draw_it:
        d.rounded_rectangle([m, y, m + d.textlength(sur.upper(), font=fs) + 36 * t, y + 54 * t],
                            radius=int(27 * t), fill=accent)
        d.text((m + 18 * t, y + 9 * t), sur.upper(), font=fs, fill=WHITE)
    y += int(84 * t)

    max_w = w - 2 * m if not land else int(w * 0.70)
    ft = font("bold", int((104 if story else 84) * t))
    for ln in wrap(d, spec.get("titre", ""), ft, max_w):
        if draw_it: d.text((m, y), ln, font=ft, fill=WHITE)
        y += int(ft.size * 1.18)

    if spec.get("sous_titre"):
        y += int(22 * t)
        fsub = font("regular", int((46 if story else 38) * t))
        for ln in wrap(d, spec["sous_titre"], fsub, max_w):
            if draw_it: d.text((m, y), ln, font=fsub, fill=MUTED)
            y += int(fsub.size * 1.35)

    pts = spec.get("points") or []
    if pts:
        y += int(30 * t)
        fp = font("medium", int((44 if story else 36) * t))
        for p in pts[:4]:
            if draw_it: d.ellipse([m, y + fp.size * 0.35, m + fp.size * 0.45, y + fp.size * 0.8], fill=accent)
            for ln in wrap(d, p, fp, max_w - fp.size):
                if draw_it: d.text((m + fp.size * 0.8, y), ln, font=fp, fill=WHITE)
                y += int(fp.size * 1.3)
            y += int(12 * t)

    if not draw_it:
        return y <= limit

    if cta_lines:
        fc = font("bold", int(32 * t))
        bh = int(len(cta_lines) * fc.size * 1.3 + 36 * u)
        top = by - int(20 * u) - bh
        d.rounded_rectangle([m, top, w - m, top + bh], radius=int(18 * u), fill=WHITE)
        ty = top + 18 * u
        for ln in cta_lines:
            d.text((m + 30 * u, ty), ln, font=fc, fill=NAVY)
            ty += fc.size * 1.3

    d.line([(m, by), (w - m, by)], fill=(255, 255, 255), width=max(1, int(2 * u)))
    d.text((m, by + 20 * u), FOOTER, font=ff, fill=MUTED)
    if one_line_footer:
        d.text((w - m - d.textlength(TAGLINE, font=fi), by + 20 * u), TAGLINE, font=fi, fill=accent)
    else:
        d.text((m, by + 58 * u), TAGLINE, font=fi, fill=accent)
    return True


def render(spec, size, accent_key, seed=7):
    accent, offer_label = ACCENTS.get(accent_key, ACCENTS["marque"])
    img = background(size[0], size[1], accent, seed)
    k = 1.0
    while k > 0.45 and not _layout(spec, size, accent, offer_label, img, k, False):
        k *= 0.92
    _layout(spec, size, accent, offer_label, img, k, True)
    return img


def make_image(spec, out):
    size = FORMATS[spec.get("format", "square")]
    render(spec, size, spec.get("offre", "marque")).save(out, "PNG", optimize=True)
    print(out)


def make_video(spec, out):
    size = FORMATS[spec.get("format", "story")]
    dur = float(spec.get("duree_scene", 3.5))
    fps = 30
    xf = 0.6
    tmp = tempfile.mkdtemp(prefix="aitech_vid_")
    try:
        clips = []
        for i, sc in enumerate(spec["scenes"]):
            png = os.path.join(tmp, f"s{i}.png")
            render(sc, size, spec.get("offre", "marque"), seed=7 + i).save(png)
            clip = os.path.join(tmp, f"c{i}.mp4")
            frames = int(dur * fps)
            w, h = size
            # léger zoom avant (effet Ken Burns)
            vf = (f"scale={w*2}:{h*2},zoompan=z='min(zoom+0.0006,1.06)':d={frames}:"
                  f"x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s={w}x{h}:fps={fps},format=yuv420p")
            subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-loop", "1", "-i", png,
                            "-vf", vf, "-t", str(dur), "-c:v", "libx264", "-preset", "veryfast",
                            "-crf", "20", clip], check=True)
            clips.append(clip)
        if len(clips) == 1:
            shutil.copy(clips[0], out)
        else:
            inputs, filt, last, offset = [], [], "[0:v]", 0.0
            for c in clips:
                inputs += ["-i", c]
            for i in range(1, len(clips)):
                offset += dur - xf
                lab = f"[v{i}]"
                filt.append(f"{last}[{i}:v]xfade=transition=fade:duration={xf}:offset={offset:.2f}{lab}")
                last = lab
            subprocess.run(["ffmpeg", "-y", "-loglevel", "error", *inputs, "-filter_complex",
                            ";".join(filt), "-map", last, "-c:v", "libx264", "-preset", "veryfast",
                            "-crf", "20", "-pix_fmt", "yuv420p", "-movflags", "+faststart", out], check=True)
        print(out)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    if len(sys.argv) != 4 or sys.argv[1] not in ("image", "video"):
        print(__doc__)
        sys.exit(1)
    spec = json.load(open(sys.argv[2], encoding="utf-8"))
    (make_image if sys.argv[1] == "image" else make_video)(spec, sys.argv[3])
