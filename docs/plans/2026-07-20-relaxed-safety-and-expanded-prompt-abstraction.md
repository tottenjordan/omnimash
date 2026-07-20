# Implementation Plan - Relaxed Safety Settings & Expanded Pop-Culture Prompt Abstraction

**Branch**: `feature/relaxed-safety-and-expanded-prompt-abstraction`
**Objective**: Relax Gemini Omni Flash safety filters to `BLOCK_NONE` across all harm categories and expand the Responsible AI prompt abstraction dictionary with extensive pop-culture, superhero, fantasy, gaming, anime, and celebrity character mappings to ensure 100% reliable generation without safety rejections.

---

## User Review Required Checkpoint

> [!IMPORTANT]
> - All changes will be developed on feature branch `feature/relaxed-safety-and-expanded-prompt-abstraction`.
> - PR will be opened via `gh pr create` and await explicit user review before merge.
> - No cloud redeployments will be performed without explicit user approval.
> - No `Co-Authored-By` trailers in commits or PRs.

---

## Task Breakdown

### Task 1: Expanded Prompt Abstraction Dictionary (`src/omnimash/engine/omni_client.py`)
- Expand `_abstract_prompt_for_responsible_ai(prompt: str) -> str` with comprehensive pop-culture mappings:
  - **Harry Potter**: Snape, Severus Snape, Hagrid, McGonagall, Voldemort, Dumbledore, Hermione, Ron, Harry, Draco.
  - **Star Wars**: Darth Vader, Luke Skywalker, Yoda, Obi-Wan Kenobi, Han Solo, Chewbacca, Kylo Ren, Stormtrooper.
  - **Superheroes (Marvel/DC)**: Batman, Bruce Wayne, Joker, Superman, Spider-Man, Iron Man, Tony Stark, Thanos, Thor, Wolverine, Hulk.
  - **Fantasy & Sci-Fi (LOTR, etc.)**: Gandalf, Frodo, Sauron, Gollum, Legolas.
  - **Gaming & Anime**: Goku, Naruto, Mario, Luigi, Bowser, Sonic, Master Chief, Pikachu.
  - **Celebrities & Cultural Icons**: Gordon Ramsay, Julia Child, Snoop Dogg, Eminem, Drake, Kendrick Lamar, Kanye West / Ye, Beyonce, Taylor Swift, Elon Musk, Donald Trump, Kamala Harris, Joe Biden, Barack Obama, Gucci Mane, Jeezy.
- Write/update tests in `tests/engine/test_omni_client.py` asserting prompt abstraction replaces new character names with rich visual archetypes.

### Task 2: Permissive GenAI SDK Safety Settings (`src/omnimash/engine/omni_client.py`)
- Define `get_relaxed_safety_settings()` helper returning `types.SafetySetting` instances configured with `HarmBlockThreshold.BLOCK_NONE` across:
  - `HARM_CATEGORY_HARASSMENT`
  - `HARM_CATEGORY_HATE_SPEECH`
  - `HARM_CATEGORY_SEXUALLY_EXPLICIT`
  - `HARM_CATEGORY_DANGEROUS_CONTENT`
  - `HARM_CATEGORY_CIVIC_INTEGRITY`
- In `OmniFlashClient._generate_live_omni_flash_video`:
  - Pass `safety_settings=get_relaxed_safety_settings()` in the kwargs to `self._genai_client.interactions.create(...)`.
- Add unit tests in `tests/engine/test_omni_client.py` verifying `safety_settings` generation and passing.

### Task 3: Documentation Refresh & Verification
- Update `docs/notes/request_lifecycle.md` and `README.md` to document relaxed `BLOCK_NONE` safety settings and expanded pop-culture character abstraction.
- Run `uv run ruff check --fix . && uv run ruff format . && uv run ty check . && uv run pytest` to ensure 100% passing tests.

### Task 4: PR Creation & Review Gate
- Push branch `feature/relaxed-safety-and-expanded-prompt-abstraction` and open PR via `gh pr create`.
