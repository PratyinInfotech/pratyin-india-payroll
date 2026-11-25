"""Generate the Pratyin HR PWA icon and splash-screen set.

The mobile HR portal (``/hrms``) is a PWA whose install prompt, home-screen
icon and iOS splash screens are served by ``india_payroll/www/hrms.html``.
This script renders that image set from ``public/images/pratyin-logo.png`` so
the artwork is reproducible instead of being committed as opaque binaries
nobody can regenerate.

The visual language deliberately mirrors ``www/login.html``: the navy gradient
backdrop, the gold ring flourish and the white rounded logo card. The source
logo ships on an opaque white background, so it is placed inside that white
card rather than being chroma-keyed onto the navy (keying would eat the
white details inside the mark).

Run with::

    cd apps/india_payroll && ../../env/bin/python \
        india_payroll/india_payroll/scripts/generate_pwa_assets.py
"""

from __future__ import annotations

import os

from PIL import Image, ImageChops, ImageDraw

APP_DIR = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", ".."))
SOURCE_LOGO = os.path.join(APP_DIR, "public", "images", "pratyin-logo.png")
OUT_DIR = os.path.join(APP_DIR, "public", "manifest")

# Brand palette, kept in step with www/login.html.
NAVY_DARK = (11, 31, 77)  # #0b1f4d
NAVY_MID = (19, 48, 110)  # #13306e
NAVY_LIGHT = (30, 58, 138)  # #1e3a8a
GOLD = (234, 179, 8)  # #eab308

# Device sizes referenced by the <link rel="apple-touch-startup-image"> tags.
SPLASH_SIZES = (
	(2048, 2732),
	(2732, 2048),
	(1668, 2388),
	(2388, 1668),
	(1536, 2048),
	(2048, 1536),
	(1668, 2224),
	(2224, 1668),
	(1620, 2160),
	(2160, 1620),
	(1290, 2796),
	(2796, 1290),
	(1179, 2556),
	(2556, 1179),
	(1284, 2778),
	(2778, 1284),
	(1170, 2532),
	(2532, 1170),
	(1125, 2436),
	(2436, 1125),
	(1242, 2688),
	(2688, 1242),
	(828, 1792),
	(1792, 828),
	(1242, 2208),
	(2208, 1242),
	(750, 1334),
	(1334, 750),
	(640, 1136),
	(1136, 640),
)


def trimmed_logo() -> Image.Image:
	"""Return the logo with its surrounding white margin cropped away."""
	logo = Image.open(SOURCE_LOGO).convert("RGB")
	diff = ImageChops.difference(logo, Image.new("RGB", logo.size, (255, 255, 255)))
	# Ignore near-white compression noise so the crop hugs the actual mark.
	mask = diff.convert("L").point(lambda v: 255 if v > 12 else 0)
	return logo.crop(mask.getbbox() or logo.getbbox())


def navy_gradient(width: int, height: int) -> Image.Image:
	"""Render the login page's 155deg navy gradient at an arbitrary size."""
	# Build the ramp on a small vertical strip, then shear it by rotating a
	# deliberately oversized canvas; this keeps the cost independent of the
	# requested size while matching the CSS stop positions (0%, 60%, 100%).
	ramp = Image.new("RGB", (1, 256))
	painter = ImageDraw.Draw(ramp)
	for y in range(256):
		position = y / 255
		if position <= 0.6:
			blend = position / 0.6
			start, end = NAVY_DARK, NAVY_MID
		else:
			blend = (position - 0.6) / 0.4
			start, end = NAVY_MID, NAVY_LIGHT
		painter.point((0, y), tuple(round(a + (b - a) * blend) for a, b in zip(start, end, strict=True)))

	# 155deg in CSS runs top-left to bottom-right; a mild rotation of the
	# vertical ramp reproduces that diagonal without per-pixel maths.
	span = max(width, height) * 2
	diagonal = ramp.resize((span, span), Image.BILINEAR).rotate(-25, resample=Image.BILINEAR)
	left = (span - width) // 2
	top = (span - height) // 2
	return diagonal.crop((left, top, left + width, top + height))


def gold_ring(
	canvas: Image.Image, centre: tuple[int, int], radius: int, thickness: int, alpha: int = 70
) -> None:
	"""Draw the translucent gold ring used as the login page's flourish.

	The login page uses ``rgba(234,179,8,.12)``, which over navy resolves to a
	desaturated blue-grey. That reads fine across an 80px-tall hero but turns
	into a grey smudge once scaled down, so the ring is carried at a higher
	alpha here and kept off the app icons entirely.
	"""
	overlay = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
	ImageDraw.Draw(overlay).ellipse(
		(centre[0] - radius, centre[1] - radius, centre[0] + radius, centre[1] + radius),
		outline=(*GOLD, alpha),
		width=thickness,
	)
	canvas.alpha_composite(overlay) if canvas.mode == "RGBA" else canvas.paste(
		Image.alpha_composite(canvas.convert("RGBA"), overlay).convert("RGB"), (0, 0)
	)


def logo_card(logo: Image.Image, card_size: int) -> Image.Image:
	"""Put the logo on the white rounded card used across the brand."""
	radius = round(card_size * 0.22)
	card = Image.new("RGBA", (card_size, card_size), (0, 0, 0, 0))
	ImageDraw.Draw(card).rounded_rectangle(
		(0, 0, card_size - 1, card_size - 1), radius=radius, fill=(255, 255, 255, 255)
	)

	inner = round(card_size * 0.80)
	scaled = logo.copy()
	scaled.thumbnail((inner, inner), Image.LANCZOS)
	card.paste(scaled, ((card_size - scaled.width) // 2, (card_size - scaled.height) // 2))
	return card


def write_icon(logo: Image.Image, size: int, filename: str, card_ratio: float = 0.62) -> None:
	"""Render a square app icon. ``card_ratio`` keeps maskable safe-area room."""
	canvas = navy_gradient(size, size)
	card = logo_card(logo, round(size * card_ratio))
	canvas.paste(card, ((size - card.width) // 2, (size - card.height) // 2), card)
	canvas.save(os.path.join(OUT_DIR, filename), "PNG", optimize=True)
	print(f"  {filename}  {size}x{size}")


def write_splash(logo: Image.Image, width: int, height: int) -> None:
	canvas = navy_gradient(width, height)
	short_edge = min(width, height)
	gold_ring(
		canvas,
		(round(width * 0.84), round(height * 0.15)),
		round(short_edge * 0.38),
		max(2, round(short_edge * 0.07)),
	)

	card = logo_card(logo, round(short_edge * 0.26))
	canvas.paste(card, ((width - card.width) // 2, (height - card.height) // 2), card)

	filename = f"apple-splash-{width}-{height}.jpg"
	canvas.save(os.path.join(OUT_DIR, filename), "JPEG", quality=86, optimize=True)
	print(f"  {filename}")


def main() -> None:
	os.makedirs(OUT_DIR, exist_ok=True)
	logo = trimmed_logo()

	print("icons:")
	# Maskable icons need the mark inside the inner 80% safe circle.
	write_icon(logo, 192, "manifest-icon-192.maskable.png", card_ratio=0.56)
	write_icon(logo, 512, "manifest-icon-512.maskable.png", card_ratio=0.56)
	# Non-maskable surfaces can use the full canvas.
	write_icon(logo, 196, "favicon-196.png", card_ratio=0.70)
	write_icon(logo, 180, "apple-icon-180.png", card_ratio=0.70)

	print("splash screens:")
	for width, height in SPLASH_SIZES:
		write_splash(logo, width, height)

	print(f"\nwrote {4 + len(SPLASH_SIZES)} files to {OUT_DIR}")


if __name__ == "__main__":
	main()
