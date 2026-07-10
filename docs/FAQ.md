# Aedile FAQ

## Frequently Asked Questions

### How do I ignore a legacy violation without refactoring?
Use the **baseline feature**. Run `aedile baseline` to record all current violations in `.aedile_baseline.json`. Future checks will only report new violations.

### How do I exclude test files from dead code checking?
Aedile automatically filters out folders matching `**/tests/**`, `**/examples/**`, or files ending in `_test.py` or prefixed with `test_`. You can customize exclusions in the `[project]` section of `aedile.toml`:

```toml
[project]
exclude = [
    "**/tests/**",
    "**/my_custom_folder/**"
]
```

### Can Aedile analyze languages other than Python?
Aedile's core dependency graph, rule checkers, and exporters are **fully language-agnostic**. The parser layer is designed to accept different language drivers. In Version 1, a native Python AST parser is built-in. Drivers for JS/TS/Go/Rust are planned for Version 2 using tree-sitter.

### Why is my import marked as a Cycle Violation?
A circular dependency means module `A` imports `B`, and `B` imports `A` (directly or through intermediate files like `A -> B -> C -> A`). This leads to high coupling and import errors. Use dependency inversion (injecting interfaces/protocols) or merge tightly bound packages.
