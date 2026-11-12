"""Shared locations for source assets, font exports, and supporting output."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / 'src'
FONTS = ROOT / 'fonts'
ASSETS = ROOT / 'assets'
REFERENCE_IMAGE = ASSETS / 'alphabet-reference.webp'
REFERENCE_FONTS = ASSETS / 'reference-fonts'
GENERATED = ROOT / 'generated'
GLYPHS = GENERATED / 'glyphs'
METADATA = GENERATED / 'metadata'
PREVIEWS = GENERATED / 'previews'
BLOG = GENERATED / 'blog'
DOCS = ROOT / 'docs'
