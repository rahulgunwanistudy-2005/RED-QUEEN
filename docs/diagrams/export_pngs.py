from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parent
RAW_DIR = ROOT / "raw"
OUT_DIR = ROOT / "png"
CANVAS = (1800, 1200)
BACKGROUND = "#090a0a"
FOREGROUND = "#f0f0eb"
MUTED = "#8c9490"
ACCENT = "#e34b43"

DIAGRAMS = [
    ("01-system-architecture", "System Architecture", "Client → three agent planes → geap.py seam → Google Cloud"),
    ("02-hardening-state-machine", "Crash-Recoverable State Machine", "Idempotent transitions, approval gates, and the kill -9 replay boundary"),
    ("03-attack-harden-verify-loop", "Attack → Harden → Verify", "The autonomous red / blue / green control loop with mutation return"),
    ("04-verifier-trust-boundary", "Verifier Isolation & Trust Boundaries", "Separate identity, constrained database role, and denied reward-hacking paths"),
    ("05-full-cycle-sequence", "One Complete Sentinel Cycle", "Calls, durable writes, policy application, verification, and return paths over time"),
    ("06-heterogeneous-fleet", "Heterogeneous Agent Fleet", "Same evolved payload and tools; different prompt, model, and authority design"),
    ("07-durable-data-model", "Durable Data Model", "Findings, runs, policies, spans, verifications, corpus, and two uniqueness guards"),
    ("08-memory-hierarchy", "Memory Hierarchy", "Session state → pgvector campaign memory → Vertex Memory Bank"),
    ("09-gcp-deployment-topology", "Google Cloud Deployment Topology", "Cloud Run, two service identities, managed AI services, SQL, events, and tracing"),
]


def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    candidates = [
        "/System/Library/Fonts/SFNS.ttf" if not bold else "/System/Library/Fonts/SFNSDisplay-Bold.otf",
        "/System/Library/Fonts/Supplemental/Arial.ttf" if not bold else "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf" if not bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    ]
    for candidate in candidates:
        if Path(candidate).exists():
            return ImageFont.truetype(candidate, size=size)
    return ImageFont.load_default()


TITLE_FONT = font(48, bold=True)
SUBTITLE_FONT = font(21)
LABEL_FONT = font(17, bold=True)
FOOTER_FONT = font(15)


def contain(image: Image.Image, width: int, height: int) -> Image.Image:
    scale = min(width / image.width, height / image.height)
    size = (max(1, round(image.width * scale)), max(1, round(image.height * scale)))
    return image.resize(size, Image.Resampling.LANCZOS)


def render(name: str, title: str, subtitle: str, index: int) -> Path:
    source = Image.open(RAW_DIR / f"{name}.png").convert("RGBA")
    source = contain(source, 1650, 900)

    canvas = Image.new("RGBA", CANVAS, BACKGROUND)
    draw = ImageDraw.Draw(canvas)

    draw.rounded_rectangle((72, 54, 300, 92), radius=19, fill="#151818", outline="#343938", width=1)
    draw.ellipse((89, 67, 101, 79), fill=ACCENT)
    draw.text((114, 62), "RED//QUEEN · SYSTEM MAP", font=LABEL_FONT, fill=FOREGROUND)
    draw.text((1630, 62), f"{index:02d} / 09", font=LABEL_FONT, fill=MUTED)

    draw.text((72, 126), title, font=TITLE_FONT, fill=FOREGROUND)
    draw.text((74, 188), subtitle, font=SUBTITLE_FONT, fill=MUTED)
    draw.line((72, 232, 1728, 232), fill="#2a2e2d", width=2)
    draw.line((72, 232, 224, 232), fill=ACCENT, width=3)

    x = (CANVAS[0] - source.width) // 2
    y = 260 + (830 - source.height) // 2
    canvas.alpha_composite(source, (x, y))

    draw.line((72, 1122, 1728, 1122), fill="#222625", width=1)
    draw.text((72, 1144), "REPOSITORY-BACKED · EDITABLE MERMAID SOURCE INCLUDED", font=FOOTER_FONT, fill="#69706d")
    draw.text((1466, 1144), "SENTINEL EVOLUTION", font=FOOTER_FONT, fill="#69706d")

    destination = OUT_DIR / f"{name}.png"
    canvas.convert("RGB").save(destination, format="PNG", optimize=True)
    return destination


def contact_sheet(paths: list[Path]) -> Path:
    sheet = Image.new("RGB", (1800, 1200), "#070808")
    draw = ImageDraw.Draw(sheet)
    draw.text((48, 35), "RED//QUEEN · ARCHITECTURE SERIES", font=font(34, bold=True), fill=FOREGROUND)
    draw.text((48, 80), "Nine repo-backed diagrams · 1800 × 1200 PNG masters", font=SUBTITLE_FONT, fill=MUTED)

    thumb_w, thumb_h = 544, 324
    gap_x, gap_y = 34, 35
    start_x, start_y = 48, 132
    for idx, path in enumerate(paths):
        row, col = divmod(idx, 3)
        x = start_x + col * (thumb_w + gap_x)
        y = start_y + row * (thumb_h + gap_y)
        thumb = Image.open(path).convert("RGB").resize((thumb_w, thumb_h), Image.Resampling.LANCZOS)
        sheet.paste(thumb, (x, y))
        draw.rounded_rectangle((x, y, x + thumb_w, y + thumb_h), radius=8, outline="#343938", width=2)

    destination = OUT_DIR / "00-contact-sheet.png"
    sheet.save(destination, format="PNG", optimize=True)
    return destination


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    paths = [render(name, title, subtitle, index) for index, (name, title, subtitle) in enumerate(DIAGRAMS, 1)]
    contact_sheet(paths)


if __name__ == "__main__":
    main()
