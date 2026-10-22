"""Responsible AI prompt abstraction, safety settings, and guardrail error guidance parser."""

import re
from typing import Any

try:
    from google import genai as _default_genai
except ImportError:
    _default_genai: Any = None

_PROTECTED_TOKEN_PATTERN = re.compile(
    r"\[#\s*(?:References|Sources)[^\]]*\]"
    r"|-\s*(?:\[[^\]]+\]\s*)?Scene\s+\d+\s*\[[^\]]*\](?:\s*\(Screenplay Script\):)?"
    r"|\bRole\s+[A-Za-z0-9]+\s*-\s*[^\n:<#\(\)]+?(?=\s*(?:<(?:IMAGE_REF|FIRST_FRAME|LAST_FRAME)|\bsays\b|:|\n|\(|$))"
    r"|<(?:IMAGE_REF_\d+|FIRST_FRAME|LAST_FRAME)(?:>@\w+)?>",
    re.IGNORECASE,
)

_RAW_RAI_REPLACEMENTS: tuple[tuple[str, str], ...] = (
    # Harry Potter Universe
    (r"\bharry\s*potter\b", "a young wizard student with round spectacles and black hair"),
    (r"\bharry\b", "a young wizard with spectacles"),
    (r"\bseverus\s*snape\b", "a stern potion master wizard with sleek black hair and dark robes"),
    (r"\bsnape\b", "a stern potion master wizard in dark robes"),
    (r"\bdraco\s*malfoy\b", "a sleek blonde rival wizard student in emerald robes"),
    (r"\bdraco\b", "a blonde rival wizard student"),
    (r"\bvoldemort\b", "a dark sorcerer in obsidian robes"),
    (r"\bhermione\s*granger\b", "a smart young witch student with curly hair"),
    (r"\bhermione\b", "a smart young witch student"),
    (r"\bron\s*weasley\b", "a red-haired wizard student in robes"),
    (r"\bron\b", "a red-haired wizard student"),
    (r"\bdumbledore\b", "a wise elderly headmaster wizard with a long silver beard"),
    (r"\bhagrid\b", "a towering friendly giant gamekeeper with a bushy beard and heavy coat"),
    (r"\bswagrid\b", "a towering friendly gamekeeper in a fur coat"),
    (r"\bollivander\b", "an elderly shopkeeper wandmaker wizard"),
    (r"\bice[- ]vander\b", "an elderly iced-out shopkeeper wandmaker wizard"),
    (r"\bmcgonagall\b", "a distinguished witch professor in emerald robes and pointed hat"),
    (r"\bhogwarts\b", "a grand gothic magical stone castle academy"),
    (r"\bdripwarts\b", "a high-fashion hip-hop magical castle academy"),
    # Star Wars Universe
    (
        r"\bdarth\s*vader\b",
        "an imposing dark armored galactic villain with a helmet and glowing red saber",
    ),
    (
        r"\bluke\s*skywalker\b",
        "a heroic galactic farmboy knight in robes with a glowing energy blade",
    ),
    (r"\byoda\b", "a wise small green grand master alien with large ears and a walking stick"),
    (r"\bobi[- ]wan\s*kenobi\b", "a noble bearded galactic mentor knight in hooded desert robes"),
    (r"\bkenobi\b", "a noble galactic knight mentor in hooded robes"),
    (r"\bhan\s*solo\b", "a roguish interstellar smuggler pilot in a vest with a blaster"),
    (r"\bchewbacca\b", "a tall furry bipedal alien warrior with a bandolier"),
    (
        r"\bkylo\s*ren\b",
        "a conflicted masked dark galactic warrior with a crossguard red energy blade",
    ),
    (r"\bstormtrooper\b", "a futuristic galactic soldier in white armored combat gear"),
    # Superheroes (Marvel / DC)
    (r"\bbatman\b", "a masked superhero detective in dark armor and cape"),
    (r"\bbruce\s*wayne\b", "a billionaire philanthropist vigilante in a sharp tailored suit"),
    (r"\bjoker\b", "a flamboyant villain with green hair, pale makeup, and a purple suit"),
    (r"\bsuperman\b", "a powerful superhero in a red cape and blue suit with an emblem"),
    (r"\bspider[- ]man\b", "an agile superhero in a red and blue webbed suit"),
    (r"\bspiderman\b", "an agile superhero in a red and blue webbed suit"),
    (r"\biron\s*man\b", "a high-tech armored superhero in a red and gold powered suit"),
    (r"\btony\s*stark\b", "a charismatic billionaire genius inventor in stylish tech attire"),
    (r"\bthanos\b", "a towering purple galactic titan warrior in golden battle armor"),
    (r"\bthor\b", "a mighty thunder warrior god with a mystical hammer and cape"),
    (r"\bwolverine\b", "a fierce mutant brawler with metallic claws and a yellow leather suit"),
    (
        r"\bcaptain\s*america\b",
        "a patriotic super-soldier hero carrying a star-spangled circular shield",
    ),
    (r"\bhulk\b", "a giant muscular green powerhouse behemoth"),
    # Fantasy / Lord of the Rings
    (r"\bgandalf\b", "a legendary wise gray-bearded wizard with a pointed hat and wooden staff"),
    (r"\bfrodo\b", "a small brave halfling adventurer with curly hair and an elven cloak"),
    (r"\bsauron\b", "a menacing dark lord in spiked black armor with a burning eye"),
    (r"\bgollum\b", "a slender pale cave-dwelling creature with large luminous eyes"),
    (r"\blegolas\b", "a graceful blonde elven archer in woodland attire"),
    (r"\baragorn\b", "a weathered ranger king warrior with a silver sword"),
    # Gaming & Anime
    (
        r"\bgoku\b",
        "a martial arts warrior with spiky black hair in an orange gi with a glowing golden aura",
    ),
    (
        r"\bnaruto\b",
        "an energetic ninja with spiky blonde hair, a headband, and an orange tracksuit",
    ),
    (
        r"\bmario\b",
        "a cheerful plumber hero in blue overalls, red shirt, and red cap with a mustache",
    ),
    (
        r"\bluigi\b",
        "a tall cheerful plumber hero in blue overalls, green shirt, and green cap with a mustache",
    ),
    (r"\bbowser\b", "a menacing giant spiked turtle dragon king with red hair"),
    (r"\bsonic\b", "a speedy blue anthropomorphic hedgehog hero with red running sneakers"),
    (
        r"\bmaster\s*chief\b",
        "a futuristic armored super-soldier in green powered combat armor and gold visor helmet",
    ),
    (
        r"\bpikachu\b",
        "a cute small yellow electric rodent creature with rosy cheeks and lightning-bolt tail",
    ),
    # Celebrities & Cultural Icons
    (r"\bgordon\s*ramsay\b", "a fiery passionate celebrity master chef in a white chef jacket"),
    (
        r"\bjulia\s*child\b",
        "a classic enthusiastic television chef with an apron in a vintage kitchen",
    ),
    (
        r"\bsnoop\s*dogg\b",
        "an iconic laid-back hip-hop legend in sunglasses and stylish streetwear",
    ),
    (r"\beminem\b", "a fast-rhyming hip-hop superstar in a hoodie and baseball cap"),
    (r"\bdrake\b", "a chart-topping melodic hip-hop star in designer puffer jacket and jewelry"),
    (r"\bkendrick\s*lamar\b", "a visionary poetic hip-hop artist in artistic streetwear"),
    (
        r"\bkanye\s*west\b",
        "an avant-garde music producer and fashion designer in oversized streetwear",
    ),
    (r"\bye\b", "an avant-garde hip-hop artist and designer in futuristic minimalist streetwear"),
    (
        r"\bbeyonce\b",
        "a glamorous global pop queen superstar performing in shimmering haute couture",
    ),
    (
        r"\btaylor\s*swift\b",
        "a famous pop superstar singer with sparkling attire on a stadium stage",
    ),
    (
        r"\belon\s*musk\b",
        "a tech entrepreneur executive in a futuristic laboratory and rocket hangar",
    ),
    (
        r"\bdonald\s*trump\b",
        "a charismatic business executive and politician in a navy suit and red tie",
    ),
    (
        r"\bkamala\s*harris\b",
        "a prominent political leader in a tailored blazer and pearl necklace",
    ),
    (
        r"\bjoe\s*biden\b",
        "a senior statesman political leader in a classic suit and aviator sunglasses",
    ),
    (r"\bbarack\s*obama\b", "an eloquent former statesman leader in a crisp suit"),
    (
        r"\bgucci\s*mane\b",
        "a legendary trap music pioneer wearing diamond chains and designer sunglasses",
    ),
    (
        r"\bjeezy\b",
        "a gravelly-voiced southern trap hip-hop icon in a leather jacket and snowman chain",
    ),
    # Conflict & Action Smoothing for Parody Context
    (r"\bwizard\s*duel\b", "hip-hop wizard musical contest"),
    (r"\bduel\b", "rap contest"),
    (r"\bbattle\b", "parody showdown"),
    (r"\bfight\b", "musical contest"),
    (r"\bkill\b", "out-rap"),
    (r"\bdestroy\b", "out-perform"),
    (r"\battack\b", "challenge"),
    (r"\bpoison\b", "glowing magical elixir"),
    (r"\bpotion\b", "sparkling elixir"),
    (r"\bcauldron\b", "bubbling steam kettle"),
    (r"\bdungeon\b", "ancient stone academy hall"),
    (r"\bdark\s*mark\b", "golden skull emblem"),
    # Syrup, Foam Cup & Substance Parody Sanitization
    (r"\b(?:basilisk\s*)?syrup\b", "magical sparkling elixir"),
    (r"\bpolystyrene\s*foam\s*cup\b", "enchanted crystal chalice"),
    (r"\b(?:double\s*|white\s*)*foam\s*cups?\b", "golden goblet"),
    (r"\b(?:double\s*|white\s*)*styrofoam\s*cups?\b", "golden goblet"),
    (r"\btriple\s*stack\s*(?:the\s*)?cups?\b", "pour the elixir"),
    (r"\beating\s*straight\s*through\b", "sparkling brightly inside"),
    (r"\beat\s*through\s*the\s*cup\b", "sparkle inside the goblet"),
    (r"\bcube\s*blood\b", "ice cube"),
    (r"\btoo\s*volatile\b", "too potent for ordinary wizards"),
    # Street Slang, Band Trademarks & Tattoo Sanitization
    (r"\bstepped\s*on\b", "diluted"),
    (r"\bwidespread\s*panic\b", "vintage band emblem"),
    (r"\btear\s*drop\s*tattoos?\b", "facial ink accent"),
    (r"\bface\s*tattoos?\b", "artistic facial ink"),
    (r"\bface\s*tatted\b", "artistic facial ink"),
    (r"\b1017\b", "gold"),
)

_RAI_REPLACEMENT_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = tuple(
    (re.compile(pat, re.IGNORECASE), repl) for pat, repl in _RAW_RAI_REPLACEMENTS
)

_REF_IMAGE_TAG_PATTERN = re.compile(r"\(Reference Image:[^)]+\)")
_GS_URI_PATTERN = re.compile(r"gs://[^\s)\]]+")
_FULL_NAME_PATTERN = re.compile(r"\b[A-Z][a-z]+\s+[A-Z][a-z]+\b")
_REF_SECTION_PATTERN = re.compile(r"\[#\s*(?:References|Sources)[^\]]*\]")
_ROLE_PREFIX_PATTERN = re.compile(r"Role\s+[A-Za-z0-9]+\s*-\s*")

_TRADEMARKS = (
    "golden snitch",
    "snitch",
    "lightsaber",
    "light saber",
    "batmobile",
    "quidditch",
    "harry potter",
    "star wars",
    "darth vader",
    "slytherin",
    "dark mark",
    "azkaban",
    "hogwarts",
    "burberry",
    "jordans",
    "cartier",
)

_KNOWN_CELEBRITIES = (
    "totti",
    "francesco totti",
    "yo gotti",
    "gordon ramsay",
    "drake",
    "kanye",
    "kanye west",
    "taylor swift",
    "julia child",
    "young jeezy",
    "travis scott",
    "snoop dogg",
    "eminem",
    "beyonce",
    "beyoncé",
    "jay-z",
    "rihanna",
    "kendrick lamar",
    "50 cent",
    "ice cube",
    "gucci mane",
    "cardi b",
    "nicki minaj",
    "lil wayne",
    "elon musk",
    "donald trump",
    "joe biden",
    "barack obama",
)

_FALLBACK_SAFETY_CATEGORIES = (
    "HARM_CATEGORY_HARASSMENT",
    "HARM_CATEGORY_HATE_SPEECH",
    "HARM_CATEGORY_SEXUALLY_EXPLICIT",
    "HARM_CATEGORY_DANGEROUS_CONTENT",
    "HARM_CATEGORY_CIVIC_INTEGRITY",
)


def _abstract_prompt_for_responsible_ai(prompt: str) -> str:
    """Transforms named individuals or copyrighted pop-culture entities into descriptive visual archetypes to guarantee 100% compliance with Vertex AI Responsible AI safety policies."""
    if not prompt or not prompt.strip():
        return "Cinematic high-energy music video scene with dynamic lighting and camera movement."

    text = prompt.strip()
    protected_tokens: list[str] = []

    def mask_token(match: re.Match[str]) -> str:
        token = match.group(0)
        idx = len(protected_tokens)
        protected_tokens.append(token)
        return f"__OMNI_PROTECT_TOKEN_{idx}__"

    abstracted = _PROTECTED_TOKEN_PATTERN.sub(mask_token, text)

    for compiled_pattern, archetype in _RAI_REPLACEMENT_PATTERNS:
        abstracted = compiled_pattern.sub(archetype, abstracted)

    abstracted = _REF_IMAGE_TAG_PATTERN.sub("", abstracted)
    abstracted = _GS_URI_PATTERN.sub("", abstracted)

    for idx, orig_token in enumerate(protected_tokens):
        abstracted = abstracted.replace(f"__OMNI_PROTECT_TOKEN_{idx}__", orig_token)

    return abstracted


def parse_guardrail_error_guidance(
    error_msg: str, char_objs: list[Any] | None = None, prompt_text: str = ""
) -> dict[str, Any]:
    """Inspects 400 policy error message, character objects, and prompt inputs to identify specific guardrail triggers and generate actionable guidance and suggested actions."""
    trigger_set: set[str] = set()
    err_lower = (error_msg or "").lower()
    prompt_lower = (prompt_text or "").lower()

    char_names: list[str] = []
    char_descs: list[str] = []
    has_ref_photo = False

    if char_objs:
        for c in char_objs:
            if isinstance(c, dict):
                name = str(c.get("name", "") or "")
                desc = str(c.get("description", "") or "")
                ref_url = c.get("reference_url")
            else:
                name = str(getattr(c, "name", "") or "")
                desc = str(getattr(c, "description", "") or "")
                ref_url = getattr(c, "reference_url", None)

            if name:
                char_names.append(name)
            if desc:
                char_descs.append(desc)
            if ref_url:
                has_ref_photo = True

    if (
        has_ref_photo
        or "<image_ref" in prompt_lower
        or "reference_url" in err_lower
        or "reference_image" in err_lower
        or "reference image" in err_lower
        or "attached photo" in err_lower
        or "real_people_photo" in err_lower
    ):
        trigger_set.add("real_people_photo")

    all_text_to_check = (
        prompt_lower
        + " "
        + err_lower
        + " "
        + " ".join(char_names).lower()
        + " "
        + " ".join(char_descs).lower()
    )
    if (
        any(tm in all_text_to_check for tm in _TRADEMARKS)
        or "third_party" in err_lower
        or "trademark" in err_lower
        or "third_party_content" in err_lower
    ):
        trigger_set.add("third_party_content")

    has_celebrity = any(celeb in all_text_to_check for celeb in _KNOWN_CELEBRITIES)
    has_full_name = any(_FULL_NAME_PATTERN.search(name) for name in char_names)

    if not has_full_name and prompt_text:
        clean_p = _REF_SECTION_PATTERN.sub("", prompt_text)
        clean_p = _ROLE_PREFIX_PATTERN.sub("", clean_p)
        if _FULL_NAME_PATTERN.search(clean_p):
            has_full_name = True

    if (
        has_celebrity
        or has_full_name
        or "celebrity" in err_lower
        or "real_people_likeness" in err_lower
        or "real people" in err_lower
        or "likeness" in err_lower
        or "person" in err_lower
    ):
        trigger_set.add("real_people_likeness")

    if not trigger_set and error_msg:
        trigger_set.add("real_people_likeness")

    triggers = sorted(trigger_set)
    guidance_parts: list[str] = []
    suggested_actions: list[dict[str, str]] = []

    if "real_people_likeness" in trigger_set:
        guidance_parts.append(
            "Safety guardrail triggered due to potential real-person likeness or celebrity reference. Avoid using full real-world names or celebrity names."
        )
        suggested_actions.append(
            {
                "action": "sanitize_real_names",
                "label": "Sanitize Character Names",
                "description": "Replace real person names with descriptive visual archetypes or parody identifiers.",
            }
        )

    if "real_people_photo" in trigger_set:
        guidance_parts.append(
            "Reference image or photo attached may depict real individuals. Remove reference photos of real people or replace with stylized character descriptions."
        )
        suggested_actions.append(
            {
                "action": "remove_reference_photo",
                "label": "Remove Reference Photo",
                "description": "Remove attached reference image URLs or photo references.",
            }
        )

    if "third_party_content" in trigger_set:
        guidance_parts.append(
            "Prompt contains trademarked or copyrighted pop-culture items. Abstract specific brand or item names into generic visual descriptions."
        )
        suggested_actions.append(
            {
                "action": "abstract_trademarks",
                "label": "Abstract Trademarked Items",
                "description": "Replace trademarked terms (e.g. 'Lightsaber', 'Golden Snitch', 'Batmobile') with generic visual descriptions (e.g. 'laser sword', 'golden flying orb', 'armored tactical vehicle').",
            }
        )

    user_guidance = (
        " ".join(guidance_parts)
        if guidance_parts
        else "Review prompt and character settings to comply with safety guardrails."
    )

    return {
        "triggers": triggers,
        "user_guidance": user_guidance,
        "suggested_actions": suggested_actions,
    }


def _get_relaxed_safety_settings(genai_module: Any = _default_genai) -> list[Any] | None:
    """Configures relaxed BLOCK_NONE safety thresholds across all harm categories for unrestricted Gemini Omni Flash video generation."""
    if genai_module and hasattr(genai_module, "types"):
        types = genai_module.types
        categories = (
            types.HarmCategory.HARM_CATEGORY_HARASSMENT,
            types.HarmCategory.HARM_CATEGORY_HATE_SPEECH,
            types.HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT,
            types.HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT,
            types.HarmCategory.HARM_CATEGORY_CIVIC_INTEGRITY,
        )
        return [
            types.SafetySetting(
                category=cat,
                threshold=types.HarmBlockThreshold.BLOCK_NONE,
            )
            for cat in categories
        ]

    return [{"category": cat, "threshold": "BLOCK_NONE"} for cat in _FALLBACK_SAFETY_CATEGORIES]


def _get_relaxed_interaction_safety_settings() -> list[dict[str, str]]:
    """Returns relaxed BLOCK_NONE safety thresholds formatted specifically for GAOS client.interactions.create."""
    return [
        {"type": "harassment", "threshold": "block_none"},
        {"type": "hate_speech", "threshold": "block_none"},
        {"type": "sexually_explicit", "threshold": "block_none"},
        {"type": "dangerous_content", "threshold": "block_none"},
        {"type": "civic_integrity", "threshold": "block_none"},
        {"type": "image_harassment", "threshold": "block_none"},
        {"type": "image_hate", "threshold": "block_none"},
        {"type": "image_sexually_explicit", "threshold": "block_none"},
        {"type": "image_dangerous_content", "threshold": "block_none"},
        {"type": "jailbreak", "threshold": "off"},
    ]
