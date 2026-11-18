"""The matching algorithm (US-08): score native species against a grow profile.

Pure functions, kept apart from the view so they can be tested on their own.

Step 1, hard filters. A species is a candidate only if it is active, native to
the profile's region and not invasive. Out-of-stock species stay in (they are
marked, not hidden).

Step 2, a weighted score out of 100:

    sunlight 30 · soil 25 · water 20 · indoor/outdoor 15 · purpose 10

Each criterion gives a fraction from 0 to 1, multiplied by its weight, and the
five are added and rounded. Ties are broken by common name.

The species table stores its needs as free text ("Full sun", "Low", "Loam"), so
the text is turned into the same codes the grow profile uses before comparing.
"""

from dataclasses import dataclass, field

from catalog.models import PlantSpecies
from catalog.queries import visible_species

from growprofiles import choices

from . import vocabulary

WEIGHTS = {"sunlight": 30, "soil": 25, "water": 20, "setting": 15, "purpose": 10}

GREAT_FIT = 70  # 70-100
LOW_FIT = 40  # under 40; 40-69 is "good"

SUN_LEVEL = {"FULL_SUN": 2, "PARTIAL_SHADE": 1, "SHADE": 0}
WATER_LEVEL = {"LOW": 0, "MEDIUM": 1, "HIGH": 2}


@dataclass
class Criterion:
    """How one species did on one criterion."""

    key: str
    weight: int
    fraction: float  # 0.0 to 1.0
    state: str  # "match", "partial" or "no match"
    reason: str = ""

    @property
    def points(self):
        return self.weight * self.fraction


@dataclass
class Match:
    species: PlantSpecies
    score: int
    criteria: list = field(default_factory=list)

    @property
    def in_stock(self):
        return self.species.stock_qty > 0

    @property
    def tier(self):
        if self.score >= GREAT_FIT:
            return "great"
        return "good" if self.score >= LOW_FIT else "low"

    @property
    def tier_label(self):
        return {"great": "Great fit", "good": "Good fit", "low": "Low fit"}[self.tier]


def _ordinal_fraction(profile_level, species_level):
    """1.0 for the same level, 0.5 one step away, 0.0 two steps away."""
    if profile_level is None or species_level is None:
        return 0.0
    return 1 - abs(profile_level - species_level) / 2


def _state(fraction):
    return "match" if fraction == 1 else "partial" if fraction > 0 else "no match"


def score_species(profile, species):
    """The five criteria for one species against one profile, each with its reason.

    The reason is written from the same numbers as the score (the fraction and
    the values compared), so the two can never disagree.
    """
    species_sun = vocabulary.sun_level(species.light_need)
    species_water = vocabulary.water_level(species.water_need)
    sun = _ordinal_fraction(SUN_LEVEL.get(profile.sunlight), species_sun)
    water = _ordinal_fraction(WATER_LEVEL.get(profile.water_availability), species_water)

    soils = vocabulary.soil_codes(species.suitable_soils)
    if profile.soil_type in soils:
        soil = 1.0
    elif "LOAM" in soils:  # loam is the adaptable soil
        soil = 0.5
    else:
        soil = 0.0

    setting = 1.0 if species.setting in (profile.space_type, PlantSpecies.Setting.BOTH) else 0.0
    species_purposes = vocabulary.purposes(species)
    purpose = 1.0 if profile.purpose in species_purposes else 0.0

    mine = {
        "sun": _lower(choices.label_for(choices.SUNLIGHT, profile.sunlight)),
        "soil": _lower(choices.label_for(choices.SOILS, profile.soil_type)),
        "water": _lower(choices.label_for(choices.WATER, profile.water_availability)),
        "space": _lower(choices.label_for(choices.SPACE_TYPES, profile.space_type)),
    }
    reasons = {
        "sunlight": (f"Prefers {_SUN_WORDS[species_sun]} — your space gets {mine['sun']}."
                     if species_sun is not None else "Its sunlight need isn't recorded."),
        "soil": _soil_reason(soil, soils, mine["soil"]),
        "water": (f"Needs {_WATER_WORDS[species_water]} water — you can provide {mine['water']} water."
                  if species_water is not None else "Its water need isn't recorded."),
        "setting": _setting_reason(species.setting, mine["space"]),
        "purpose": _purpose_reason(profile.purpose, species_purposes),
    }
    fractions = {"sunlight": sun, "soil": soil, "water": water, "setting": setting, "purpose": purpose}
    return [Criterion(key, WEIGHTS[key], fractions[key], _state(fractions[key]), reasons[key]) for key in WEIGHTS]


_SUN_WORDS = {2: "full sun", 1: "partial shade", 0: "shade"}
_WATER_WORDS = {0: "low", 1: "medium", 2: "high"}
_PURPOSE_WORDS = {
    "SHADE_COOLING": "shade and cooling", "FOOD": "food", "POLLINATOR": "pollinators",
    "EROSION_CONTROL": "erosion control", "ORNAMENTAL": "ornament", "MEDICINAL": "medicine",
}


def _lower(text):
    return text[:1].lower() + text[1:]


def _join(words):
    words = sorted(words)
    return words[0] if len(words) == 1 else ", ".join(words[:-1]) + " or " + words[-1]


def _soil_reason(fraction, soils, mine):
    if not soils:
        return "Its soil need isn't recorded."
    names = _join(choices.label_for(choices.SOILS, c).lower() for c in soils)
    if fraction == 1:
        return f"Prefers {names} soil — your soil is {mine}."
    if fraction == 0.5:
        return f"Prefers {names} soil — adaptable, but your soil is {mine}."
    return f"Prefers {names} soil — your soil is {mine}."


def _setting_reason(setting, space):
    grows = {"INDOOR": "indoors", "OUTDOOR": "outdoors", "BOTH": "indoors or outdoors"}.get(setting, setting.lower())
    return f"Grows {grows} — your space is {space}."


def _purpose_reason(wanted, species_purposes):
    goal = _PURPOSE_WORDS.get(wanted, wanted.lower())
    if wanted in species_purposes:
        return f"Good for {goal} — matches your purpose."
    if species_purposes:
        used = _join(_PURPOSE_WORDS[c] for c in species_purposes)
        return f"Used for {used} — not {goal}."
    return f"Not specifically used for {goal}."


def candidates(profile):
    """Step 1: species a profile may be matched with."""
    return (
        visible_species()
        .filter(is_invasive=False, species_regions__region=profile.region)
        .select_related("seller")
    )


def rank(profile):
    """Every candidate scored and sorted: best score first, then by common name."""
    matches = []
    for species in candidates(profile):
        criteria = score_species(profile, species)
        matches.append(Match(species=species, score=round(sum(c.points for c in criteria)), criteria=criteria))
    matches.sort(key=lambda m: (-m.score, m.species.common_name.lower()))
    return matches
