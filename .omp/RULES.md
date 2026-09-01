1. Human-consumption text (comments, commit messages, replies): fewest words possible, down to the point.
2. No superlatives or praise; give the cold hard truth.
3. Don't touch blocks of code unrelated to the feature; minimize changed lines.
4. Strictly adhere to the layered boundary hierarchy — each layer communicates only with its immediate neighbor directly below it; never punch holes (controllers/UI never call DB/raw drivers/network clients directly).
5. Commit messages: blank line between subject and body; subject ≤ 50 chars (72 hard limit); capitalize subject; no trailing period; imperative mood ("If applied, this commit will …"); wrap body at 72; body explains what and why, not how.
6. Bug fixes are test-first: write the failing test, observe it fail, then fix, then observe it pass.
7. Avoid magic numbers and strings by extracting recurring or meaningful values into descriptive constants (const) or enums. Keep self-explanatory, one-off values inline to avoid clutter. If a value comes from a spec (e.g. HTTP 200 OK), use a constant regardless.
8. Keep function names short. Less than 30 characters.
9. Use enums instead of booleans for function parameters.
10. Add a small, to the point, comment to explain *what* the block does and *why*. Use examples when possible. Propose ASCII drawings to explain complete systems.
11. Treat member visibility changes as a breaking design shift. Keep all fields and functions private unless external access is strictly required by the design. Prompt the user for explicit approval before changing any access modifier from private to internal or public.
12. Program to levels of abstraction. Lower-level mechanics (e.g., raw hardware I/O, sector parsing, direct socket streams) must be encapsulated in a dedicated driver/abstraction layer. Expose clean, high-level APIs to the rest of the application so calling code works with domain concepts, not raw implementation details.
13. Service-layer naming: orchestration entrypoints are <capability>_service.py, one per use case. Drivers keep plain capability names (formats.py, parse.py, errors.py); no bare service.py anywhere. Package __init__.py is the only public import surface. When a component reaches ~3 entrypoints, promote to a `services/` subdirectory with the same filenames.
