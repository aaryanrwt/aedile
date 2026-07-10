import math


class ArchitectureGraph:
    def __init__(self) -> None:
        self.nodes: set[str] = set()
        # adjacency list for directed graph: node -> set of target nodes
        self.edges: dict[str, set[str]] = {}
        # reverse adjacency list for tracking incoming edges
        self.incoming_edges: dict[str, set[str]] = {}
        # metadata mapping from module name to file path
        self.module_to_file: dict[str, str] = {}

    def add_node(self, module: str, filepath: str = "") -> None:
        self.nodes.add(module)
        if module not in self.edges:
            self.edges[module] = set()
        if module not in self.incoming_edges:
            self.incoming_edges[module] = set()
        if filepath:
            self.module_to_file[module] = filepath

    def add_edge(self, from_module: str, to_module: str) -> None:
        if from_module not in self.nodes:
            self.add_node(from_module)
        if to_module not in self.nodes:
            self.add_node(to_module)

        self.edges[from_module].add(to_module)
        self.incoming_edges[to_module].add(from_module)

    def remove_edge(self, from_module: str, to_module: str) -> None:
        if from_module in self.edges:
            self.edges[from_module].discard(to_module)
        if to_module in self.incoming_edges:
            self.incoming_edges[to_module].discard(from_module)

    def get_dependencies(self, module: str) -> set[str]:
        return self.edges.get(module, set())

    def get_dependents(self, module: str) -> set[str]:
        return self.incoming_edges.get(module, set())

    def find_all_cycles(self) -> list[list[str]]:
        """Finds all dependency cycles in the graph using Tarjan's Strongly Connected Components.
        Returns a list of cycles, where each cycle is a list of modules forming a loop.
        """
        index = 0
        indices: dict[str, int] = {}
        lowlink: dict[str, int] = {}
        on_stack: set[str] = set()
        stack: list[str] = []
        sccs: list[list[str]] = []

        def strongconnect(node: str) -> None:
            nonlocal index
            indices[node] = index
            lowlink[node] = index
            index += 1
            stack.append(node)
            on_stack.add(node)

            # Traverse neighbors
            for neighbor in sorted(self.edges.get(node, set())):
                if neighbor not in indices:
                    strongconnect(neighbor)
                    lowlink[node] = min(lowlink[node], lowlink[neighbor])
                elif neighbor in on_stack:
                    lowlink[node] = min(lowlink[node], indices[neighbor])

            # If node is a root node, pop the stack and generate an SCC
            if lowlink[node] == indices[node]:
                scc = []
                while True:
                    w = stack.pop()
                    on_stack.remove(w)
                    scc.append(w)
                    if w == node:
                        break
                # Only keep SCCs that are actual cycles
                # An SCC is a cycle if its length > 1, or if it is length 1 and has a self-loop
                if len(scc) > 1:
                    sccs.append(scc)
                elif len(scc) == 1:
                    if scc[0] in self.edges.get(scc[0], set()):
                        sccs.append(scc)

        for node in sorted(self.nodes):
            if node not in indices:
                strongconnect(node)

        # Normalize order of each cycle to match execution path
        normalized_cycles = []
        for scc in sccs:
            # Reconstruct path order using simple path-finding inside the SCC
            normalized_cycles.append(self._order_cycle(scc))

        return normalized_cycles

    def _order_cycle(self, scc: list[str]) -> list[str]:
        """Arranges the nodes in the SCC into a sequence representing the cycle order."""
        scc_set = set(scc)
        if not scc:
            return []

        start = sorted(scc)[0]
        ordered = [start]
        visited = {start}

        curr = start
        while len(ordered) < len(scc):
            next_node = None
            for neighbor in sorted(self.edges.get(curr, set())):
                if neighbor in scc_set and neighbor not in visited:
                    next_node = neighbor
                    break
            if next_node:
                ordered.append(next_node)
                visited.add(next_node)
                curr = next_node
            else:
                break
        return ordered

    def find_shortest_path(self, start: str, end: str) -> list[str] | None:
        """Finds the shortest path between start and end modules using BFS."""
        if start not in self.nodes or end not in self.nodes:
            return None
        if start == end:
            return [start]

        queue: list[list[str]] = [[start]]
        visited: set[str] = {start}

        while queue:
            path = queue.pop(0)
            node = path[-1]

            for neighbor in self.edges.get(node, set()):
                if neighbor == end:
                    return path + [end]
                if neighbor not in visited:
                    visited.add(neighbor)
                    queue.append(path + [neighbor])
        return None

    def export_mermaid(self) -> str:
        """Generates a Mermaid class/dependency diagram representation of the graph."""
        lines = ["graph TD"]
        # Declare nodes to style them
        for node in sorted(self.nodes):
            safe_id = node.replace(".", "_")
            lines.append(f'    {safe_id}["{node}"]')

        # Declare edges
        for from_node in sorted(self.edges.keys()):
            from_id = from_node.replace(".", "_")
            for to_node in sorted(self.edges[from_node]):
                to_id = to_node.replace(".", "_")
                lines.append(f"    {from_id} --> {to_id}")

        return "\n".join(lines)

    def export_svg(self) -> str:
        """Generates a beautiful SVG of the dependency graph using a circular layout."""
        if not self.nodes:
            return '<svg xmlns="http://www.w3.org/2000/svg" width="200" height="200"><text x="20" y="100">Empty Graph</text></svg>'

        # Circular layout calculation
        nodes_list = sorted(list(self.nodes))
        num_nodes = len(nodes_list)
        radius = min(400, 50 * num_nodes)
        center_x = radius + 150
        center_y = radius + 150
        svg_width = center_x * 2
        svg_height = center_y * 2

        node_positions: dict[str, tuple[float, float]] = {}
        for i, node in enumerate(nodes_list):
            angle = (2 * math.pi * i) / num_nodes
            x = center_x + radius * math.cos(angle)
            y = center_y + radius * math.sin(angle)
            node_positions[node] = (x, y)

        svg_lines = [
            f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {svg_width} {svg_height}" width="100%" height="100%" style="background-color: #0d1117; font-family: sans-serif;">',
            '  <defs>',
            '    <marker id="arrow" viewBox="0 0 10 10" refX="24" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">',
            '      <path d="M 0 0 L 10 5 L 0 10 z" fill="#58a6ff" />',
            '    </marker>',
            '  </defs>',
            '  <rect width="100%" height="100%" fill="#0d1117" />'
        ]

        # Draw edges
        for from_node, targets in self.edges.items():
            fx, fy = node_positions[from_node]
            for to_node in targets:
                tx, ty = node_positions[to_node]
                # Draw edge lines
                svg_lines.append(
                    f'  <line x1="{fx:.1f}" y1="{fy:.1f}" x2="{tx:.1f}" y2="{ty:.1f}" '
                    f'stroke="#30363d" stroke-width="1.5" marker-end="url(#arrow)" />'
                )

        # Draw nodes
        for node, (x, y) in node_positions.items():
            # Styling nodes based on common levels (e.g. shared vs core)
            fill_color = "#1f6feb"
            if "shared" in node:
                fill_color = "#238636"
            elif "cli" in node:
                fill_color = "#8957e5"
            elif "rules" in node:
                fill_color = "#da3633"

            svg_lines.append(
                f'  <circle cx="{x:.1f}" cy="{y:.1f}" r="12" fill="{fill_color}" '
                f'stroke="#c9d1d9" stroke-width="1.5" />'
            )
            # Add labels offset
            svg_lines.append(
                f'  <text x="{x:.1f}" y="{y-18:.1f}" font-size="12" fill="#c9d1d9" '
                f'text-anchor="middle" font-weight="bold">{node}</text>'
            )

        svg_lines.append("</svg>")
        return "\n".join(svg_lines)
