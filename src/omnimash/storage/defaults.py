"""Default character seed data fixtures for OmniMash."""

from typing import Any

DEFAULT_CHARACTERS: list[dict[str, Any]] = [
    {
        "role_id": "Role A",
        "name": 'Harry "Gucci"',
        "description": "Harry Potter, a young wizard with round gold wire-rim Cartier glasses, untidy jet-black hair, and distinct lightning scar wearing a red Gucci tracksuit",
        "reference_url": "gs://reference-images-jt-trend-trawler/harry_drip.jpeg",
        "aesthetic_tags": ["Red Gucci Tracksuit", "Cartier Glasses"],
        "voice_style": "Fast-paced confident Atlanta rap flow with autotune",
    },
    {
        "role_id": "Role B",
        "name": 'Young Draco "Jeezy"',
        "description": 'Young Draco "Jeezy", pale blonde rival wizard with slicked-back platinum hair, sharp sneering facial features, and tailored green velvet blazer',
        "reference_url": "gs://reference-images-jt-trend-trawler/draco.jpeg",
        "aesthetic_tags": ["Platinum Slicked Hair", "Diamond Iced-Out Chain"],
        "voice_style": "Pompous, cynical British drawl with aggressive rap cadence",
    },
    {
        "role_id": "Role A",
        "name": "Cyborg Gordon Ramsay",
        "description": "Cyborg Gordon Ramsay, a fiery celebrity chef with sharp blond hair, intense focused gaze, robotic eye implant, and chrome chef jacket",
        "reference_url": "gs://reference-images-jt-trend-trawler/gordon_ramsay.jpeg",
        "aesthetic_tags": [
            "Chrome Chef Jacket",
            "Bionic Eye Implant",
            "Cybernetic Kitchen Knife",
        ],
        "voice_style": "Aggressive British shouting with robotic vocoder undertones",
    },
    {
        "role_id": "Role B",
        "name": "Neon Julia Child",
        "description": "Neon Julia Child, legendary TV chef with towering frame, pearl necklace, vibrant neon French apron, and whisk",
        "reference_url": "gs://reference-images-jt-trend-trawler/julia_child.jpeg",
        "aesthetic_tags": ["Neon French Apron", "Pearl Necklace", "Glowing Whisk"],
        "voice_style": "Warbling, enthusiastic high-pitched mid-Atlantic accent with electronic delay",
    },
]
