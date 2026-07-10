# Aedile Design Specification

Aedile is engineered to maintain codebase structure using lightweight, zero-dependency, local-first AST extraction.

## 1. Intermediate Representation (IR)

To decouple codebase analysis from concrete languages, Aedile parses source files into a language-neutral Intermediate Representation (IR).

### `SourceFile` Model
Represents a single parsed module.
- `filepath`: Absolute canonical path.
- `relative_path`: Path relative to the project root.
- `file_hash`: SHA256 file checksum to enable incremental scan caches.
- `imports`: List of `Import` bindings.
- `symbols`: List of `Symbol` definitions.

### `Import` Model
Represents an external or internal package reference.
- `module`: Target module string (e.g. `aedile.core.scanner`).
- `names`: Specific exported variables/classes/functions imported, or empty.
- `line`: Starting line of the import statement.

### `Symbol` Model
Represents defined blocks.
- `name`: Identifier of the symbol.
- `kind`: 'class', 'function', or 'method'.
- `line` & `end_line`: Code region boundaries.

---

## 2. Graph Builders

Aedile constructs two graphs to analyze project health:

1. **Module Dependency Graph**:
   - Nodes: Module namespaces (e.g. `aedile.shared.config`).
   - Edges: Directed imports between files.
2. **Directory Layer Graph**:
   - Nodes: Directory packages (e.g. `src/aedile/cli`).
   - Edges: Aggregate module imports between packages.

---

## 3. Visualization Exporters

### Mermaid Generator
Constructs Mermaid flowchart files (`graph TD`) mapping safe node IDs to module strings.

### SVG Circular Layout
- Automatically places $N$ modules in a radial circle to prevent overlapping layout edge crossings.
- Calculates node $(X, Y)$ coordinates using:
  \[
  X = C_x + R \cdot \cos(\theta), \quad Y = C_y + R \cdot \sin(\theta)
  \]
  where $\theta = \frac{2\pi \cdot i}{N}$.
- Employs color-coded fill palettes indicating levels and highlights paths.
