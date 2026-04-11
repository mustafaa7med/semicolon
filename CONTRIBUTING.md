# Contributing to SemiColon

Thank you for your interest in contributing to **SemiColon**!  
This is an open-source project and all contributions — bug reports, feature
requests, documentation improvements, and code — are welcome.

---

## Code of Conduct

Be kind, constructive, and respectful.  
We follow the [Contributor Covenant](https://www.contributor-covenant.org/).

---

## Getting Started

### 1. Fork & clone

```bash
git clone https://github.com/<your-username>/semicolon.git
cd semicolon
```

### 2. Create a virtual environment

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
```

### 3. Install in editable mode with dev dependencies

```bash
pip install -e ".[dev]"
# or, if you don't have a [dev] extra yet:
pip install -e .
pip install pytest ruff
```

### 4. Run the test suite

```bash
pytest
```

---

## Project Structure

```
semicolon/
├── semicolon/
│   ├── __init__.py      Package version & metadata
│   ├── cli.py           Click CLI entry point
│   ├── formatter.py     Core formatting engine
│   └── keywords.py      River constants & keyword tables
├── tests/
│   ├── test_formatter.py  Unit tests for formatting rules
│   └── test_cli.py        CLI integration tests
├── pyproject.toml
├── README.md
└── CONTRIBUTING.md      ← you are here
```

---

## Formatting Rules are Sacred

The **SemiColon Style** rules defined in `README.md` are the specification.  
Any change to formatting behaviour **must**:

1. Include a clear justification tied to readability.
2. Be approved by the project maintainer (Mostafa Ahmed / Alfie) in a
   GitHub issue *before* a PR is opened.
3. Include a `Before` / `After` example in the PR description.
4. Add or update a test in `tests/test_formatter.py` that covers the change. (If Needed)

---

## Submitting a Bug Report

Open an issue at <https://github.com/mustafaa7med/semicolon/issues> and include:

- Your `semicolon --version` output.
- The **original** SQL that produced unexpected output.
- The **actual** output you received.
- The **expected** output according to the SemiColon Style rules.

A minimal, reproducible example is always appreciated.

---

## Submitting a Pull Request

1. **Open an issue first** for any non-trivial change so we can discuss
   the approach before you invest time coding.
2. Create a branch off `main`:
   ```bash
   git checkout -b fix/my-bug-description
   ```
3. Make your changes, add tests, ensure `pytest` passes.
4. Run the linter:
   ```bash
   ruff check semicolon/
   ```
5. Push and open a PR against `main`.

### PR checklist

- [ ] Tests added or updated
- [ ] `ruff` passes with no new warnings
- [ ] Description includes Before/After SQL if formatting behaviour changed
- [ ] Linked to the relevant issue

---

## Adding a New Formatting Rule

1. Discuss in an issue.
2. Add the rule to `semicolon/formatter.py` (and constants to
   `semicolon/keywords.py` if needed).
3. Document the rule in `README.md` under "The SemiColon Style — Rules".
4. Add tests in `tests/test_formatter.py`.

---

## Release Process (maintainers)

1. Bump `version` in `pyproject.toml` and `semicolon/__init__.py`.
2. Update `CHANGELOG.md` (if present).
3. Tag: `git tag v0.x.y && git push --tags`.
4. Publish: `python -m build && twine upload dist/*`.

---
