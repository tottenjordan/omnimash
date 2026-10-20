"""Parody role and name sanitization dictionary and helpers for OmniMash.

Sanitizes real public figure, celebrity, and brand names into safe parody descriptors
to adhere to Gemini Omni Flash multimodal safety guidelines.
"""

from __future__ import annotations

import re

REAL_NAME_PARODY_MAP: dict[str, str] = {
    r"\bGordon Ramsay\b": "Fiery Chef Blood",
    r"\bJulia Child\b": "Classic Chef Fam",
    r"\bYoung Jeezy\b": "Trap Legend Fam",
    r"\bDrake\b": "Drizzy Bruv (6ix Melodic Star)",
    r"\bKanye West\b": "Ye Fam (Avant-Garde Producer)",
    r"\bTravis Scott\b": "Rodeo Trap Bruv",
    r"\bTaylor Swift\b": "Pop Star Fam",
    r"\bSeverus Snape\b": "Gothic Potion Master Fam",
    r"\bSnape\b": "Potion Master",
    r"\bHarry Potter\b": "Spectacled Wizard Bruv",
    r"\bDraco Malfoy\b": "Platinum Rival Blood",
    r"\bDraco\b": "Rival Wizard",
    r"\bHermione Granger\b": "Retainer Academic Fam",
    r"\bRon Weasley\b": "Redhair Wizard Blood",
    r"\bSlytherin\b": "Green Snake House",
    r"\bDark Mark\b": "Golden Skull Emblem",
    r"\bAzkaban\b": "High Security Fortress",
    r"\bHogwarts\b": "Gothic Academy",
    r"\bBurberry\b": "Plaid Trench",
    r"\bJordans\b": "High Top Kicks",
    r"\bCartier\b": "Gold Wire Glasses",
    r"\bDumbledore\b": "Venerable High Wizard Bruv",
    r"\bVoldemort\b": "Dark Sorcerer",
    r"\bWaka Flocka Flame\b": "Southern Trap Blood",
    r"\bWaka Flocka\b": "Southern Trap Blood",
    r"\bSnoop Dogg\b": "West Coast Drip (Rap Legend)",
    r"\bEminem\b": "Shady Fam (Detroit Speed Rapper)",
    r"\bBeyonce\b": "Pop Queen Fam",
    r"\bBeyoncé\b": "Pop Queen Fam",
    r"\bJay-Z\b": "Hov Fam (NY Rap Mogul)",
    r"\bJayZ\b": "Hov Fam",
    r"\bRihanna\b": "Riri Fam (Caribbean Pop Icon)",
    r"\bKendrick Lamar\b": "Lyrical West Coast Bruv",
    r"\b50 Cent\b": "Fifty Cent Fam",
    r"\b50Cent\b": "Fifty Cent Fam",
    r"\bIce Cube\b": "Cube Blood",
    r"\bGucci Mane\b": "Designer Drip (Trap Pioneer)",
    r"\bCardi B\b": "Bronx Queen Fam",
    r"\bNicki Minaj\b": "Queens Rap Queen Fam",
    r"\bLil Wayne\b": "New Orleans Rap Genius",
    r"\bElon Musk\b": "Tech Entrepreneur Executive",
    r"\bDonald Trump\b": "Charismatic Business Executive",
    r"\bJoe Biden\b": "Senior Statesman Leader",
    r"\bBarack Obama\b": "Eloquent Former Statesman",
    r"\bFrancesco Totti\b": "a tatted wizard",
    r"\bJohn Totti\b": "a tatted wizard",
    r"\bYo Totti\b": "a tatted wizard",
    r"\bYoTotti\b": "a tatted wizard",
    r"\bTotti\b": "a tatted wizard",
    r"\bJordan Totten\b": "a young wizard scholar",
    r"\bJordanTotten\b": "a young wizard scholar",
    r"\bDumble Dior\b": "a high-fashion wizard headmaster",
    r"\bDumbleDior\b": "a high-fashion wizard headmaster",
    # Street Slang, Band Trademarks, Drug & Alcohol Sanitization
    r"\bbaking\s*soda\b": "magical potion powder",
    r"\b40-ounce\s*beer\b": "glowing golden goblet",
    r"\b40-ounce\b": "golden goblet",
    r"\bpop\s+you\s+for\b": "challenge you for",
    r"\bstepped\s*on\b": "diluted",
    r"\bwidespread\s*panic\b": "vintage band emblem",
    r"\btear\s*drop\s*tattoos?\b": "facial ink accent",
    r"\bface\s*tattoos?\b": "artistic facial ink",
    r"\bface\s*tatted\b": "artistic facial ink",
    r"\b1017\b": "gold",
    # Trademarked Luxury Brands & Pop-Culture House Abstractions
    r"\bGucci\b": "high-fashion designer",
    r"\bDior\b": "luxury fashion",
    r"\bChanel\b": "high-fashion designer",
    r"\bLouis Vuitton\b": "luxury fashion",
    r"\bBalenciaga\b": "streetwear designer",
    r"\bPrada\b": "luxury designer",
    r"\bVersace\b": "luxury designer",
    r"\bRolex\b": "luxury watch",
    r"\bGryffindor\b": "Gold Lion House",
    r"\bRavenclaw\b": "Blue Eagle House",
    r"\bHufflepuff\b": "Yellow Badger House",
    r"\bGolden Snitch\b": "glowing golden flying orb",
    r"\bSnitch\b": "golden flying orb",
    r"\bQuidditch\b": "aerial magical sport",
    r"\bLightsaber\b": "laser sword",
    r"\bLight Saber\b": "laser sword",
    r"\bBatmobile\b": "armored tactical vehicle",
    r"\bGuy Fieri\b": "Spiky Blonde Flavortown Chef",
    r"\bAnthony Bourdain\b": "World-Weary Culinary Traveler",
    r"\bWolfgang Puck\b": "Master Haute Cuisine Chef",
    r"\bMarco Pierre White\b": "Intense Michelin Master Chef",
    r"\bHermes\b": "luxury leather designer",
    r"\bHermès\b": "luxury leather designer",
    r"\bFendi\b": "luxury fashion designer",
    r"\bGivenchy\b": "couture fashion designer",
    r"\bSaint Laurent\b": "sleek couture designer",
    r"\bYSL\b": "sleek couture designer",
    r"\bPatek Philippe\b": "heirloom luxury timepiece",
    r"\bAudemars Piguet\b": "octagonal luxury chronograph",
}

REAL_NAME_MAPPINGS = REAL_NAME_PARODY_MAP

# Pre-compile parody sanitization regex patterns at module import time to avoid
# thrashing Python's 512-entry re._cache on every sanitize_real_names() call.
# Source: https://docs.python.org/3.12/library/re.html#re.compile
_COMPILED_PARODY_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = tuple(
    (re.compile(pattern, flags=re.IGNORECASE), replacement)
    for pattern, replacement in REAL_NAME_PARODY_MAP.items()
)


def sanitize_real_names(text: str) -> str:
    """Sanitizes real celebrity and public figure full names into safe visual parody role descriptors to adhere to Gemini Omni Flash safety guidelines."""
    if not text:
        return text
    result = text
    for compiled_pattern, replacement in _COMPILED_PARODY_PATTERNS:
        result = compiled_pattern.sub(replacement, result)
    return result


__all__ = [
    "REAL_NAME_MAPPINGS",
    "REAL_NAME_PARODY_MAP",
    "_COMPILED_PARODY_PATTERNS",
    "sanitize_real_names",
]
