1. Human-consumption text (comments, commit messages, replies): fewest words possible, down to the point.
2. No superlatives or praise; give the cold hard truth.
3. Don't touch blocks of code unrelated to the feature; minimize changed lines.
4. Strictly adhere to the layered boundary hierarchy — each layer communicates only with its immediate neighbor directly below it; never punch holes (controllers/UI never call DB/raw drivers/network clients directly).
5. Commit messages: blank line between subject and body; subject ≤ 50 chars (72 hard limit); capitalize subject; no trailing period; imperative mood ("If applied, this commit will …"); wrap body at 72; body explains what and why, not how.
6. Bug fixes are test-first: write the failing test, observe it fail, then fix, then observe it pass.
