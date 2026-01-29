# Contributing to V.E.R.A.

Thank you for your interest in contributing to V.E.R.A.! This project aims to make AI systems more trustworthy through formal logic verification.

## Ways to Contribute

### 1. Code Contributions

- **Bug fixes**: Found a bug? Submit a PR!
- **Features**: Check the roadmap in issues for planned features
- **Tests**: More test coverage is always welcome
- **Documentation**: Help improve docs and examples

### 2. Domain Expertise

We especially welcome contributions from:

- **Logicians**: Help validate and extend NTP rules
- **Philosophers**: Input on existence, identity, and predication theory
- **AI/ML Engineers**: Integration with LLM frameworks
- **Data Engineers**: Wikidata ETL and E! Corpus population

### 3. Documentation

- Improve README and docstrings
- Write tutorials and examples
- Translate documentation
- Create diagrams and visualizations

## Development Setup

```bash
# Clone the repository
git clone https://github.com/vera-project/vera.git
cd vera

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install in development mode
pip install -e ".[dev]"

# Run tests
pytest

# Run linting
black src tests
isort src tests
ruff check src tests
mypy src
```

## Pull Request Process

1. **Fork** the repository
2. **Create a branch** for your feature: `git checkout -b feature/amazing-feature`
3. **Write tests** for your changes
4. **Run the test suite**: `pytest`
5. **Run linters**: `black . && isort . && ruff check .`
6. **Commit** with clear messages: `git commit -m "Add amazing feature"`
7. **Push** to your fork: `git push origin feature/amazing-feature`
8. **Open a Pull Request**

## Commit Message Format

```
<type>: <description>

[optional body]

[optional footer]
```

Types:
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation only
- `test`: Adding tests
- `refactor`: Code change that neither fixes a bug nor adds a feature
- `style`: Formatting, missing semicolons, etc.
- `chore`: Maintenance tasks

Example:
```
feat: add D3 strong distinguishability to identity resolution

Implements NTP D3 rule requiring E!(x) ∧ E!(y) for x ≠ y assertions.
Updates IdentityResult to include existence verification for both entities.

Closes #42
```

## Code Style

- Follow PEP 8
- Use type hints
- Write docstrings (Google style)
- Keep functions focused and small
- Comment complex NTP logic thoroughly

## NTP-Specific Guidelines

When working with NTP logic:

1. **Cite sources**: Reference Wessel (1992) or NTP_Formal_Specification for rules
2. **Preserve rule numbering**: R1-R9 must match the validated specification
3. **Document edge cases**: NTP has subtle distinctions (e.g., inner vs outer negation)
4. **Test with philosophical examples**: "Pegasus flies" vs "Socrates is mortal"

## Questions?

- Open an issue for bugs or feature requests
- Start a discussion for questions or ideas
- Contact maintainers for sensitive matters

## Code of Conduct

- Be respectful and inclusive
- Focus on constructive feedback
- Assume good intentions
- Help newcomers

---

*"Truth is a feature, not an option."*
