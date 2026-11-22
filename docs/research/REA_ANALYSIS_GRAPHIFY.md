# REA-Methodology Reverse-Engineering Analysis: `Graphify-Labs/graphify`

- **Target**: `https://github.com/Graphify-Labs/graphify`
- **Methodology**: `morluto/rea` evidence-first static inspection (Observed facts, Derived architecture, Inferred trade-offs, Unknowns, and Aedile integration).
- **Aedile AST Scan**: `103` Python files in `graphify/`, `103` nodes, `26` directed edges, `0` cycles.

---

## 1. Observed Facts (Source & Contract Evidence)

1. **7-Stage Pipeline (`ARCHITECTURE.md:L8-L35`)**:
   - `detect() -> extract() -> build() -> cluster() -> analyze helpers -> report.generate() -> export.to_*()`.
2. **Evidence Provenance Tags (`README.md:L43,L122`)**:
   - Every edge carries a confidence tag (`EXTRACTED` = explicit in source, `INFERRED` = derived by resolution), and path queries report the weakest-hop confidence.
3. **Graph Intelligence (`graphify/analyze.py:L1-L100`)**:
   - `god_nodes(G)`: Most-connected architectural hubs (filtering `_BUILTIN_NOISE_LABELS` and synthetic file/method stubs).
   - `surprising_connections(G)`: Cross-community / cross-subsystem bridges.
   - `suggest_questions(G, communities, labels)`: Surfaces high-value architectural questions.
   - `graph_diff(G_old, G_new)` & `find_import_cycles(G)`: Structural delta and cycle detection.
4. **Security & Memory Guards (`graphify/security.py:L20-L100`)**:
   - Enforces a 512 MiB `graph.json` memory-bomb cap (`_MAX_GRAPH_FILE_BYTES`, overridable via `GRAPHIFY_MAX_GRAPH_BYTES`) before `json.loads()`, plus SSRF/IP range blocking (`_ip_is_blocked`).
5. **Multi-Format Exporters (`graphify/export.py`, `ARCHITECTURE.md:L25`)**:
   - Exports `to_json`, `to_html`, `to_obsidian`, `to_svg`, `to_graphml`, `to_canvas`, `to_cypher`.
6. **Live File Watcher & Dual MCP (`watch.py`, `serve.py`)**:
   - `watch()` debounced rebuilds + stdio/HTTP MCP server (`explain`, `path`, `query`).

---

## 2. Derived Architecture

```text
CLI / Skill / Watch / MCP (cli.py, watch.py, serve.py)
   │
   ▼
Detect & Extract (detect.py, extract.py, extractors/*, cache.py)
   │
   ▼
Graph Build & Cluster (build.py -> nx.Graph, cluster.py -> Leiden communities)
   │
   ▼
Analysis & Security (analyze.py, affected.py, security.py, validate.py)
   │
   ▼
Report & Export (report.py, export.py, wiki.py, callflow_html.py)
```

---

## 3. Inferred Trade-Offs & Unknowns

- **Strengths**: Rich knowledge-graph queries (`god_nodes`, `surprising_connections`, `suggest_questions`, `graph_diff`, `explain`, `path`), broad format exports (`GraphML`, `Cypher`), and hardened JSON memory caps.
- **Limitations / Unknowns**: Relies on heavy external dependencies (`networkx`, tree-sitter grammars, optional LLM passes for docs/media), and focuses on *read-only exploration* rather than *pre-edit architectural rule enforcement* (`LayerRule`, `BoundaryRule`, `NamingRule`, `ArchitectureVerifier`).

---

## 4. Capabilities Implemented in Aedile

1. **Graph Insights Engine (`src/aedile/core/graph_insights.py`)**:
   - Zero-dependency `god_nodes()`, `detect_communities()` (label-propagation / connected-component subsystem clustering), `surprising_connections()`, `suggest_questions()`, `explain_module()`, and `graph_diff()`.
2. **CLI & MCP Exposure (`aedile explain`, `aedile path`, `aedile insights`, `aedile_explain`, `aedile_path`)**:
   - Query hubs, shortest paths, cross-subsystem bridges, and module blast radius without reading raw files.
3. **GraphML & Cypher Exporters (`ArchitectureGraph.export_graphml()`, `export_cypher()`)**:
   - Export Aedile's dependency graph directly to Gephi/yEd (`GraphML`) or Neo4j/Memgraph (`Cypher`).
4. **Cache Memory-Bomb Cap (`ScanCache` in `cache.py`)**:
   - Reject oversized `.aedile/cache.json` files (`AEDILE_MAX_CACHE_BYTES`, default 64 MiB) before `json.load()`.
