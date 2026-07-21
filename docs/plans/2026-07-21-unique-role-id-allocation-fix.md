# Unique Character Role ID Allocation Fix Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Eliminate `role_id` collisions (e.g. duplicate `Role C` or `Role B`) when adding or deleting character roles in OmniMash, ensuring every role has a strictly unique ID regardless of deletion order.

**Why Collisions Occurred:**
`addCharacterRole` and `handleLoadVaultCharacter` previously computed new role IDs using `65 + characters.length`. Deleting `Role A` left 2 characters (`Role B`, `Role C`), making `characters.length = 2`. The length formula selected `65 + 2 = 67` (`Role C`), creating a duplicate `Role C` collision.

**Proposed Solution:**
1. **Smart Role Allocator (`src/omnimash/api/app.py`)**:
   - Implement `getNextAvailableRoleId(existingCharacters)`:
     ```javascript
     const getNextAvailableRoleId = (charList) => {
         const usedLetters = new Set(
             (charList || []).map(c => {
                 const match = (c.role_id || "").match(/Role ([A-Z])/i);
                 return match ? match[1].toUpperCase() : null;
             }).filter(Boolean)
         );
         for (let i = 0; i < 26; i++) {
             const letter = String.fromCharCode(65 + i);
             if (!usedLetters.has(letter)) {
                 return `Role ${letter}`;
             }
         }
         return `Role ${charList.length + 1}`;
     };
     ```
2. **Apply Allocator Across All Role Handlers (`src/omnimash/api/app.py`)**:
   - Use `getNextAvailableRoleId` in `addCharacterRole`, `handleLoadVaultCharacter`, and `handleLoadSessionRoster`.
3. **Integration Tests (`tests/api/test_integration.py`)**:
   - Add test case verifying deleting `Role A` and adding a new role allocates `Role A` without creating duplicate `Role C` entries.

**Tech Stack:** Python 3.12, React 18, FastAPI, pytest, uv, ruff, ty.

---

## Bite-Sized Execution Tasks

### Task 1: Add getNextAvailableRoleId Helper & Update Role Handlers in app.py
- Update `src/omnimash/api/app.py` with `getNextAvailableRoleId`.
- Apply allocator in `addCharacterRole`, `handleLoadVaultCharacter`, and `handleLoadSessionRoster`.
- Add test assertions in `tests/api/test_integration.py`.
- Run `uv run pytest tests/api/test_integration.py`.

### Task 2: Full Verification & Quality Suite Pass
- Run full test suite (`uv run pytest`, `ruff check`, `ruff format`, `ty check`).

---

## Verification Plan

### Automated Tests
- Integration tests: `uv run pytest tests/api/test_integration.py`
- Full test suite: `uv run pytest`

### Manual Verification
1. Run local dev server (`uv run python -m omnimash.api.app`).
2. Have 3 roles (`Role A`, `Role B`, `Role C`).
3. Delete `Role A`. Click **+ Add Character Role**.
4. Observe new role is assigned **`Role A`** (lowest unused letter) with ZERO collisions!
