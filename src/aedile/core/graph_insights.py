"""Knowledge-graph intelligence: god nodes, communities, bridges, explain & diff."""

from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any

from aedile.core.graph import ArchitectureGraph


def god_nodes(graph: ArchitectureGraph, top_n: int = 8) -> list[dict[str, Any]]:
    """Returns the most-connected hub modules in the dependency graph."""
    ranked: list[dict[str, Any]] = []
    for node in sorted(graph.nodes):
        ca = len(graph.incoming_edges.get(node, set()))
        ce = len(graph.edges.get(node, set()))
        deg = ca + ce
        if deg == 0:
            continue
        ranked.append({"module": node, "degree": deg, "fan_in": ca, "fan_out": ce})
    ranked.sort(key=lambda item: (item["degree"], item["fan_in"]), reverse=True)
    return ranked[:top_n]


def detect_communities(graph: ArchitectureGraph, max_iters: int = 12) -> dict[int, list[str]]:
    """Zero-dependency label propagation clustering over the undirected dependency graph."""
    if not graph.nodes:
        return {}

    neighbors: dict[str, set[str]] = defaultdict(set)
    for u in graph.nodes:
        for v in graph.edges.get(u, set()):
            if u != v:
                neighbors[u].add(v)
                neighbors[v].add(u)

    sorted_nodes = sorted(graph.nodes)
    labels = {node: idx for idx, node in enumerate(sorted_nodes)}

    for _ in range(max_iters):
        changed = False
        for node in sorted_nodes:
            nbrs = neighbors.get(node)
            if not nbrs:
                continue
            counts = Counter(labels[n] for n in nbrs)
            best_label = min(counts.keys(), key=lambda lbl: (-counts[lbl], lbl))
            if best_label != labels[node]:
                labels[node] = best_label
                changed = True
        if not changed:
            break

    groups: dict[int, list[str]] = defaultdict(list)
    for node in sorted_nodes:
        groups[labels[node]].append(node)

    # Re-index community IDs cleanly from 0..K-1 ordered by size descending
    ordered = sorted(groups.values(), key=len, reverse=True)
    return {cid: members for cid, members in enumerate(ordered)}


def surprising_connections(
    graph: ArchitectureGraph, communities: dict[int, list[str]] | None = None
) -> list[dict[str, Any]]:
    """Finds cross-community edges that bridge otherwise separate subsystems."""
    comms = communities if communities is not None else detect_communities(graph)
    node_to_comm = {n: cid for cid, members in comms.items() for n in members}

    bridges: list[dict[str, Any]] = []
    for src in sorted(graph.edges.keys()):
        c_src = node_to_comm.get(src, -1)
        for dst in sorted(graph.edges[src]):
            c_dst = node_to_comm.get(dst, -1)
            if c_src != c_dst:
                bridges.append(
                    {
                        "from": src,
                        "to": dst,
                        "from_community": c_src,
                        "to_community": c_dst,
                        "is_lazy": graph.edge_lazy.get((src, dst), False),
                    }
                )
    return bridges


def suggest_questions(
    graph: ArchitectureGraph, communities: dict[int, list[str]] | None = None
) -> list[str]:
    """Generates concrete architectural investigation questions from graph topology."""
    comms = communities if communities is not None else detect_communities(graph)
    hubs = god_nodes(graph, top_n=3)
    cycles = graph.find_all_cycles()
    bridges = surprising_connections(graph, comms)

    questions: list[str] = []
    if hubs:
        top = hubs[0]
        questions.append(
            f"Why does `{top['module']}` have degree {top['degree']} "
            f"(fan_in={top['fan_in']}, fan_out={top['fan_out']})? Can its responsibilities be split?"
        )
    if cycles:
        cyc = " -> ".join(cycles[0]) + f" -> {cycles[0][0]}"
        questions.append(f"How can the dependency cycle `{cyc}` be broken?")
    if bridges:
        b = bridges[0]
        questions.append(
            f"Is the cross-subsystem edge `{b['from']} -> {b['to']}` "
            f"(community {b['from_community']} -> {b['to_community']}) intentional?"
        )
    if not questions and graph.nodes:
        questions.append("All scanned modules are decoupled with zero cycles detected.")
    return questions


def explain_module(graph: ArchitectureGraph, module: str) -> dict[str, Any]:
    """Returns full structural context for a single module in `graph`."""
    if module not in graph.nodes:
        candidates = [n for n in sorted(graph.nodes) if module in n]
        return {"found": False, "module": module, "candidates": candidates[:8]}

    metrics = graph.get_coupling_metrics(module)
    deps = sorted(graph.get_dependencies(module))
    dependents = sorted(graph.get_dependents(module))
    blast = sorted(graph.get_blast_radius(module))
    return {
        "found": True,
        "module": module,
        "filepath": graph.module_to_file.get(module, ""),
        "metrics": metrics,
        "imports": deps,
        "imported_by": dependents,
        "blast_radius": blast,
    }


def graph_diff(old_graph: ArchitectureGraph, new_graph: ArchitectureGraph) -> dict[str, list[Any]]:
    """Computes added/removed nodes and edges between two `ArchitectureGraph` snapshots."""
    old_edges = {(u, v) for u, targets in old_graph.edges.items() for v in targets}
    new_edges = {(u, v) for u, targets in new_graph.edges.items() for v in targets}
    return {
        "added_nodes": sorted(new_graph.nodes - old_graph.nodes),
        "removed_nodes": sorted(old_graph.nodes - new_graph.nodes),
        "added_edges": sorted(new_edges - old_edges),
        "removed_edges": sorted(old_edges - new_edges),
    }
