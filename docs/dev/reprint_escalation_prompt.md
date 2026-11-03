# Stage 4 — Reprint-duplicate framework escalation prompt

Keep this file handy. The iterative "encode a shipped-canonical with EXISTING
primitives" phase of Stage 4 is **over** — every remaining `needs_encoding` group
needs a genuinely new engine primitive. To advance, run a fresh Claude Code session
in `swu-game/` with this file as the prompt. It self-selects the primitive off the
live roadmap in the `[[reprint-duplicates]]` memory, so it never goes stale — do NOT
hardcode a card here.

---

Read docs/dev/plans/reprint_duplicates_plan.md (Stage 4), the [[reprint-duplicates]] memory
(project_reprint_duplicates.md) for the per-primitive roadmap of the remaining
shipped-canonical needs_encoding groups, and the recipe in docs/dev/encoding_guide.md.

The iterative easy-encode phase is OVER — every remaining group needs a genuinely new
engine primitive. This session builds ONE such primitive end to end.

1. CHOOSE the primitive yourself. From the roadmap's per-primitive groupings, rank by
   leverage and pick the top one:
     - Primary: most needs_encoding groups cleared per single new primitive.
     - Tie-break 1: smallest engine surface — fewest chokepoints touched, closest
       mirror to an existing push_/resolve_ or observer pattern.
     - Tie-break 2: no dependency on a second unbuilt primitive.
   State the ranking and your pick in one line before designing. Skip any primitive
   already built in a prior session (check the roadmap for cleared cards).

2. DESIGN FIRST. Before writing code, read the full text of every card the primitive
   serves (via CardRepository on data/swu.db) and the closest existing primitive it
   extends. Write a short design note: the new decision kind / effect / observer, its
   dataclass + push_/resolve_ shape, which existing pattern it mirrors, and every
   engine chokepoint it touches. If the design balloons beyond one primitive, STOP and
   report — don't half-build two.

3. IMPLEMENT the primitive in the engine (actions.py / registry.py / abilities as
   appropriate), then encode the CANONICAL member of each group it serves per the
   docs/dev/encoding_guide.md recipe, reusing the new primitive. Register in the correct
   src/swu/cards/<set>/abilities.py.

4. Add focused tests with the card number in each method name, covering the primitive's
   decision flow (including AutoResolveEffects-to-quiescence for optional no-target
   effects, and the AcceptTrigger/decline paths).

5. Add every sibling of each encoded group to REPRINT_ALIASES in
   src/swu/cards/reprints.py (guarded face-identity aliasing).

6. Run: the new tests, then the fast tier. Run `python scripts/find_reprints.py
   --check` and confirm the encoded groups are now fully covered (0 text-bearing
   members). The fast tier has ~118 pre-existing WinError-5 web PermissionError
   collection errors — those are not real failures.

7. Record in memory: the primitive built, the groups it cleared (needs_encoding /
   already_covered deltas), the reused patterns, and any follow-on cards the new
   primitive ALSO unblocks. Update the [[reprint-duplicates]] roadmap to remove the
   cleared cards.

Env: use .venv/Scripts/python.exe with SWU_DB=data/swu.db and PYTHONIOENCODING=utf-8;
read docs/reprints_worklist.json as UTF-8.

If mid-build you discover the primitive needs a SECOND new primitive to work, STOP and
report the dependency rather than building both.
