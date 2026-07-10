# Contributing to Aedile

We welcome contributions to Aedile! To ensure code quality, speed, and safety, we ask contributors to follow these guidelines.

## Development Setup

1. Clone the repository and navigate to the project directory.
2. Initialize virtual environment:
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   ```
3. Install the project in editable mode with development dependencies:
   ```bash
   pip install -e .
   pip install pytest pytest-cov mypy ruff pre-commit
   ```

## Development Quality Gate

Before submitting a Pull Request, please run the following checks locally:

### 1. Formatting & Linting
We use `ruff` to enforce coding style and imports formatting.
```bash
ruff check src/ tests/
```

### 2. Static Typing
We use `mypy` for strict typechecking:
```bash
mypy src/
```

### 3. Testing
We use `pytest` for unit and integration tests. All PRs must maintain or improve test coverage (>95%):
```bash
pytest --cov=src --cov-report=term-missing tests/
```

## Pull Request Guidelines
- Follow [Conventional Commits](https://www.conventionalcommits.org/) for your commit messages.
- Ensure all tests and GitHub workflows pass.
- Update documentation in the `docs/` folder if changing behavior or config settings.
