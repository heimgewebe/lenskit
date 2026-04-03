import sys

with open("docs/atlas-blaupause.md", "r", encoding="utf-8") as f:
    text = f.read()

text = text.replace("- [~] SQLite-FTS evaluieren und festziehen", "- [ ] SQLite-FTS evaluieren und festziehen (teilweise: Evaluierung in chunks_fts, aber Integration in search.py fehlt)")

with open("docs/atlas-blaupause.md", "w", encoding="utf-8") as f:
    f.write(text)
