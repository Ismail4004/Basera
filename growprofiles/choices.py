"""The fixed answers a grow profile can hold (Figma "Create a grow profile").

The model stores the short code (for example "FULL_SUN") in its text columns, so
these lists live here rather than as database choices. Each entry is
(code, label, hint); the hint is the small line under the label on the form.
The matching code in matching/services.py reads the same codes.
"""

SPACE_TYPES = [
    ("INDOOR", "Indoor", "Inside a room or balcony"),
    ("OUTDOOR", "Outdoor", "Garden, yard or rooftop"),
]

SUNLIGHT = [
    ("FULL_SUN", "Full sun", "6+ hours of direct sun"),
    ("PARTIAL_SHADE", "Partial shade", "3–6 hours of sun"),
    ("SHADE", "Shade", "Under 3 hours of sun"),
]

SOILS = [
    ("SANDY", "Sandy", "Drains fast"),
    ("LOAM", "Loam", "Balanced, rich"),
    ("CLAY", "Clay", "Holds water"),
    ("ROCKY", "Rocky", "Stony, well drained"),
]

WATER = [
    ("LOW", "Low", "Once a week or less"),
    ("MEDIUM", "Medium", "A few times a week"),
    ("HIGH", "High", "Daily or irrigated"),
]

PURPOSES = [
    ("SHADE_COOLING", "Shade & cooling", ""),
    ("FOOD", "Food", ""),
    ("POLLINATOR", "Pollinators", ""),
    ("EROSION_CONTROL", "Erosion control", ""),
    ("ORNAMENTAL", "Ornamental", ""),
    ("MEDICINAL", "Medicinal", ""),
]


def label_for(options, code):
    """The label for a stored code ("FULL_SUN" -> "Full sun"); unknown codes pass through."""
    return {c: label for c, label, _ in options}.get(code, code)
