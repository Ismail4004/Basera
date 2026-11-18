"""Turn a species' free-text needs into the codes a grow profile uses.

Species are stored with plain text ("Full sun", "Low", "Loam, Sandy"), because a
seller can type them. Matching compares codes, so the text is read here once.
Anything unrecognised reads as "unknown" and scores 0 for that criterion instead
of failing.

The species table has no "purposes" column, so what a plant is good for is read
from its ecological role and description by keyword (PURPOSE_WORDS below). If
the team later adds a purposes column to PlantSpecies, only purposes() changes.
"""

PURPOSE_WORDS = {
    "SHADE_COOLING": ("shade", "cool", "canopy"),
    "FOOD": ("fruit", "edible", "nuts", "vegetable", "herbal tea", "tea herb", "food", "eaten", "eat "),
    "POLLINATOR": ("bee", "pollinat", "butterfl", "hoverfl"),
    "EROSION_CONTROL": ("erosion", "bind", "stabilis", "holds", "hold the soil", "holds soil", "slope"),
    "ORNAMENTAL": ("ornament", "showy", "fragrant", "hedge", "cheerful", "colourful", "orchid-like"),
    "MEDICINAL": ("medicin",),
}


def _text(value):
    return (value or "").strip().lower()


def sun_level(text):
    """2 full sun, 1 partial shade, 0 shade, None if unclear."""
    t = _text(text)
    if "full" in t:
        return 2
    if "partial" in t:
        return 1
    if "shade" in t:
        return 0
    return None


def water_level(text):
    """0 low, 1 medium, 2 high, None if unclear."""
    t = _text(text)
    for word, level in (("low", 0), ("medium", 1), ("moderate", 1), ("high", 2)):
        if word in t:
            return level
    return None


def soil_codes(text):
    """The soils a species suits, as profile codes; the text may list several."""
    t = _text(text)
    return {code for word, code in (("sand", "SANDY"), ("loam", "LOAM"), ("clay", "CLAY"), ("rock", "ROCKY")) if word in t}


def purposes(species):
    """The purpose codes a species suits, read from its role and description."""
    t = f"{_text(species.ecological_role)} {_text(species.description)} "
    return {code for code, words in PURPOSE_WORDS.items() if any(w in t for w in words)}
