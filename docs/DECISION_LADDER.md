# The Decision Ladder Philosophy

Aedile is built around a single engineering principle: **Before writing new code, prove that it deserves to exist.**

To enforce this, Aedile directs AI coding agents to evaluate their implementation plans against a 7-step **Decision Ladder** before generating logic:

---

## The 7 Rungs

### 1. YAGNI (You Aren't Gonna Need It)
Does the requested task actually solve an active problem, or is it speculative? If the feature is speculative, the agent is directed to skip it and report why.

### 2. Codebase Reuse
Does the codebase already contain a helper, class, domain model, or utility that solves this? Re-implementing existing helpers is the most common form of codebase entropy. Aedile checks symbol similarity in the workspace to suggest matching reuse options.

### 3. Standard Library
Does Python's built-in standard library solve the problem (e.g. using `pathlib` instead of custom string path joining, or `functools.lru_cache` instead of writing a custom caching class)?

### 4. Platform Native Features
Can a native database constraint, SQL index, or browser feature (like `<input type="date">` or native CSS transitions) solve the requirement instead of adding application code?

### 5. Declared Dependencies
Is there a pre-installed package in `pyproject.toml` or `requirements.txt` (like `requests` or `pydantic`) that solves this? Agents should not introduce new packages if an existing dependency covers the task.

### 6. One-Line Solutions
Can the requirement be solved with a simple inline statement or standard expression?

### 7. Minimum Diffs
Only if steps 1-6 are exhausted should the agent generate new code, and even then, write the minimal possible diff to solve the problem.

---

## Why it is Effective
By structuring the reasoning process of AI assistants, Aedile transforms agents from "code generators" (which default to writing code) into "systems engineers" (which default to reusing and simplifying).
