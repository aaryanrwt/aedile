from typing import Any

from aedile.shared.config import Config


class ReasoningOptimizer:
    def __init__(self, config: Config) -> None:
        self.config = config

    def optimize_plan(
        self,
        query: str,
        similar_symbols: list[dict[str, Any]],
        stdlib_recs: list[dict[str, Any]],
        dep_recs: list[str],
    ) -> str:
        """Analyzes the proposed feature request against codebase intelligence and returns

        a formatted engineering guidance review block for the AI agent.
        """
        sections = []
        sections.append("### 🛡️ AEDILE ENGINEERING INTELLIGENCE REVIEW")
        sections.append(
            "Before writing any code, optimize your implementation plan using this guidance:"
        )

        has_redundancy = False

        # 1. Existing Codebase Abstractions
        if similar_symbols:
            has_redundancy = True
            sections.append("\n#### 🔍 Codebase Reuse Opportunities")
            sections.append(
                "The repository already contains similar functionalities. **Do NOT duplicate them**:"
            )
            for sym in similar_symbols:
                sections.append(
                    f"- **{sym['name']}** ({sym['kind']}) in [{sym['relative_path']}](file:///{sym['relative_path']}) on line {sym['line']} (Confidence: {sym['score']})"
                )
            sections.append(
                "👉 *Recommendation*: Import and reuse these existing functions/classes instead of creating new ones."
            )

        # 2. Standard Library Matches
        if stdlib_recs:
            has_redundancy = True
            sections.append("\n#### 📦 Python Standard Library Solutions")
            sections.append(
                "You can solve this using built-in capabilities without extra dependencies:"
            )
            for rec in stdlib_recs:
                sections.append(f"- **{rec['module']}**: {rec['description']}")
            sections.append("👉 *Recommendation*: Use the standard library imports shown above.")

        # 3. Third-party Dependency Reuse
        if dep_recs:
            has_redundancy = True
            sections.append("\n#### 🔌 Active Project Dependencies")
            sections.append(
                "The project already declares these third-party dependencies. Reuse them:"
            )
            for dep in dep_recs:
                sections.append(f"- **{dep}** (found in project configurations)")
            sections.append(
                "👉 *Recommendation*: Reuse these pre-installed packages; do not install alternatives or write custom mock implementations."
            )

        # 4. Token & Architecture Efficiency Guidelines
        sections.append("\n#### ⚙️ Reasoning & Context Optimization")
        sections.append(
            "To minimize token usage and architectural entropy, structure your implementation plan as follows:"
        )

        if has_redundancy:
            sections.append(
                "- [ ] **Zero Code Generation**: Check if you can complete this task by writing 0 lines of new logic and simply linking/exposing the existing modules."
            )
        else:
            sections.append(
                "- [ ] **Simplicity First**: Implement the minimum necessary logic. Choose a single-module implementation over multi-file setups where possible."
            )

        sections.append(
            "- [ ] **Fewer Tool Calls**: Plan to accomplish this modification in at most 1 to 2 tool calls. Minimize intermediate file writes."
        )
        sections.append(
            "- [ ] **Architectural Integrity**: Ensure any new imports respect the project's layer order constraints."
        )

        return "\n".join(sections)
