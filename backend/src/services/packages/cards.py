"""
The images of a package, drawn with Pillow: Instagram's carousel cards
(1080x1350, 4:5, the tallest a feed post shows uncropped), stories'
frames and TikTok's photos (1080x1920, 9:16).

**Safe margins.** A story or a TikTok is shown under the app's own
interface: the profile and progress bar on top, the reply box or the
caption and buttons at the bottom, TikTok's like/share column on the
right. Text there is covered. So every text block is laid out inside the
frame's `safe` box and never outside it, whatever its length: a block
that does not fit is drawn smaller, down to MIN_FONT, and a point that
still does not fit is left out of the package rather than cut. Margins
follow Meta's and TikTok's creative guidance as published (stories: keep
about 250 px clear at the top and 340 at the bottom; TikTok: about 150 at
the top, 480 at the bottom and 160 on the right), rounded up.

**Fonts.** DejaVu Sans when the system has it (the Docker image installs
fonts-dejavu-core), else Pillow's own scalable font. Both draw Spanish
and Catalan accents; the choice is recorded in the manifest's notes.

The colours are the brand's: black and yellow for Inspiring, black and
crimson for the Devastating edition (frontend globals.css).
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

FONT_DIRS = (
    Path("/usr/share/fonts/truetype/dejavu"),
    Path("/usr/share/fonts/dejavu"),
    Path("/usr/local/share/fonts"),
)

MIN_FONT = 34

INK = (255, 255, 255)
MUTED = (200, 200, 200)
BACKGROUND = (17, 17, 17)
ACCENTS = {"positive": (245, 196, 0), "devastating": (200, 16, 46)}


@dataclass(frozen=True)
class Box:

    left: int

    top: int

    right: int

    bottom: int

    @property
    def width(self) -> int:
        return self.right - self.left

    @property
    def height(self) -> int:
        return self.bottom - self.top


@dataclass(frozen=True)
class Format:

    name: str

    width: int

    height: int

    # Where text may go: inside the platform's interface.
    safe: Box


CAROUSEL = Format("instagram", 1080, 1350, Box(90, 110, 990, 1240))
STORY = Format("stories", 1080, 1920, Box(90, 260, 990, 1570))
TIKTOK = Format("tiktok", 1080, 1920, Box(70, 160, 910, 1430))


@dataclass
class Block:
    """One piece of text on a card: what it says, how big at most, and its colour."""

    text: str

    size: int

    bold: bool = False

    color: tuple[int, int, int] = INK

    # Space after it, in pixels at full size.
    gap: int = 36


# ----------------------------------------------------------------------
# Fonts
# ----------------------------------------------------------------------


def font_name() -> str:

    regular, _ = _font_files()

    return regular.name if regular else "Pillow's built-in font"


@lru_cache(maxsize=1)
def _font_files() -> tuple[Path | None, Path | None]:

    for folder in FONT_DIRS:
        regular, bold = folder / "DejaVuSans.ttf", folder / "DejaVuSans-Bold.ttf"
        if regular.exists():
            return regular, (bold if bold.exists() else regular)

    return None, None


@lru_cache(maxsize=64)
def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:

    regular, heavy = _font_files()
    path = heavy if bold else regular

    if path is None:
        return ImageFont.load_default(size)

    return ImageFont.truetype(str(path), size)


# ----------------------------------------------------------------------
# Laying text out
# ----------------------------------------------------------------------


def wrap(text: str, typeface: ImageFont.FreeTypeFont, width: int) -> list[str] | None:
    """`text` in lines no wider than `width`, or None when one word alone is wider."""

    lines: list[str] = []
    line = ""

    for word in text.split():

        candidate = f"{line} {word}".strip()

        if typeface.getlength(candidate) <= width:
            line = candidate
            continue

        if not line or typeface.getlength(word) > width:
            return None

        lines.append(line)
        line = word

    if line:
        lines.append(line)

    return lines


def layout(blocks: list[Block], box: Box) -> list[tuple[Block, int, list[str]]] | None:
    """
    Each block at the largest common scale at which all of them fit the
    box, as (block, font size, lines); None when nothing at MIN_FONT fits.
    One scale for every block keeps their sizes in proportion.
    """

    smallest = min(block.size for block in blocks)

    for step in range(0, 40):

        scale = 1.0 - step * 0.025
        if smallest * scale < MIN_FONT:
            break

        placed = []
        height = 0

        for block in blocks:

            size = max(int(block.size * scale), MIN_FONT)
            lines = wrap(block.text, font(size, block.bold), box.width)

            if lines is None:
                break

            placed.append((block, size, lines))
            height += len(lines) * line_height(size) + int(block.gap * scale)

        else:
            if height <= box.height:
                return placed

    return None


def line_height(size: int) -> int:

    return int(size * 1.25)


BRAND_SIZE = 34
GLYPH_INSET = 6
FOOTER_SIZE = 30


def body_box(form: Format) -> Box:
    """Where the blocks go: the safe box less the brand line on top and the footer below."""

    box = form.safe

    # Inset a little on each side: a glyph's side bearing can reach a
    # pixel or two past where it is drawn ("j", "W"), and the margins
    # test caught one 1 px outside TikTok's safe box.
    return Box(
        box.left + GLYPH_INSET,
        box.top + 28 + line_height(BRAND_SIZE) + 40,
        box.right - GLYPH_INSET,
        box.bottom - line_height(FOOTER_SIZE) * 2 - 20,
    )


def fits(blocks: list[Block], form: Format) -> bool:

    return layout(blocks, body_box(form)) is not None


# ----------------------------------------------------------------------
# Drawing
# ----------------------------------------------------------------------


def render(
    blocks: list[Block],
    form: Format,
    edition: str,
    brand: str,
    footer: str | None = None,
    position: str | None = None,
    vertical: str = "center",
) -> Image.Image:
    """
    One card. The brand and an accent bar at the top of the safe box, the
    blocks laid out inside it, the footer and the card's place ("2/6") at
    its bottom. Raises ValueError when the blocks cannot fit at MIN_FONT:
    callers check `fits` first.
    """

    accent = ACCENTS.get(edition, ACCENTS["positive"])

    image = Image.new("RGB", (form.width, form.height), BACKGROUND)
    draw = ImageDraw.Draw(image)

    box = form.safe

    # The brand line, then the body below it, and the footer above the
    # bottom edge: all three inside the safe box.
    brand_font = font(BRAND_SIZE, bold=True)
    draw.rectangle((box.left, box.top, box.left + 120, box.top + 10), fill=accent)
    draw.text((box.left, box.top + 28), brand.upper(), font=brand_font, fill=accent)

    footer_font = font(FOOTER_SIZE)
    footer_height = line_height(FOOTER_SIZE) * 2

    body = body_box(form)

    placed = layout(blocks, body)

    if placed is None:
        raise ValueError("The text does not fit the card at the smallest readable size.")

    total = sum(len(lines) * line_height(size) + block.gap for block, size, lines in placed)
    y = body.top if vertical == "top" else body.top + max(0, (body.height - total) // 2)

    for block, size, lines in placed:

        typeface = font(size, block.bold)

        for line in lines:
            draw.text((body.left, y), line, font=typeface, fill=block.color)
            y += line_height(size)

        y += block.gap

    if footer:
        lines = wrap(footer, footer_font, box.width - 140) or [footer[:60]]
        draw.text((box.left, box.bottom - footer_height), lines[0], font=footer_font, fill=MUTED)

    if position:
        width = footer_font.getlength(position)
        draw.text((box.right - width, box.bottom - footer_height), position, font=footer_font, fill=MUTED)

    return image


def save(image: Image.Image, path: Path) -> None:

    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path, format="PNG", optimize=True)


def accent_of(edition: str) -> tuple[int, int, int]:

    return ACCENTS.get(edition, ACCENTS["positive"])
