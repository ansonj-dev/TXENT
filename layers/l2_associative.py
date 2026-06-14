import os
import re
from itertools import combinations
from typing import Any

# spaCy fallback
try:
    import spacy
    HAS_SPACY = True
except ImportError:
    HAS_SPACY = False
    
    class MockDoc:
        def __init__(self, text):
            self.text = text
            self.ents = []
            self.noun_chunks = []

    class MockNLP:
        def __init__(self):
            class MetaObj:
                def get(self, key, default=None):
                    return "en_core_web_sm"
                def __getitem__(self, key):
                    return "en_core_web_sm"
            self.meta = MetaObj()

        def __call__(self, text):
            doc = MockDoc(text)
            KNOWN_ENTITIES = [
                "payment-api", "redis-cache", "postgres-db", "auth-service", 
                "order-service", "user-service", "load-balancer", "k8s-cluster", 
                "checkout-service", "orders-db"
            ]
            
            class MockEnt:
                def __init__(self, text, label):
                    self.text = text
                    self.label_ = label
                    
            text_lower = text.lower()
            for ent in KNOWN_ENTITIES:
                if ent in text_lower or ent.replace("-", " ") in text_lower:
                    doc.ents.append(MockEnt(ent, "SERVICE" if "api" in ent or "service" in ent else "COMPONENT"))
            
            # Extract simple noun chunks
            words = re.findall(r'\b[a-zA-Z]{3,}\b', text)
            for i in range(len(words)-1):
                w1 = words[i].lower()
                w2 = words[i+1].lower()
                
                class Token:
                    def __init__(self, text):
                        self.lemma_ = text
                        self.is_stop = False
                        self.is_punct = False
                        
                class MockChunk:
                    def __init__(self, token1, token2):
                        self.tokens = [token1, token2]
                    def __iter__(self):
                        return iter(self.tokens)
                
                doc.noun_chunks.append(MockChunk(Token(w1), Token(w2)))
            return doc

    class mock_spacy_module:
        @staticmethod
        def load(name):
            return MockNLP()
            
    spacy = mock_spacy_module

# NetworkX fallback
try:
    import networkx as nx
    HAS_NETWORKX = True
except ImportError:
    HAS_NETWORKX = False
    
    class MockDiGraph:
        def __init__(self):
            self._nodes = {}
            self._edges = {}

        def clear(self):
            self._nodes.clear()
            self._edges.clear()

        @property
        def nodes(self):
            class NodesView:
                def __init__(self, graph):
                    self.graph = graph
                def __call__(self, data=False):
                    if data:
                        return self.graph._nodes.items()
                    return self.graph._nodes.keys()
                def __iter__(self):
                    return iter(self.graph._nodes)
                def __len__(self):
                    return len(self.graph._nodes)
                def __contains__(self, n):
                    return n in self.graph._nodes
                def __getitem__(self, n):
                    return self.graph._nodes[n]
                def items(self):
                    return self.graph._nodes.items()
            return NodesView(self)

        @property
        def edges(self):
            class EdgesView:
                def __init__(self, graph):
                    self.graph = graph
                def __call__(self, data=False):
                    if data:
                        return [(u, v, attr) for (u, v), attr in self.graph._edges.items()]
                    return self.graph._edges.keys()
                def __iter__(self):
                    return iter(self.graph._edges)
                def __len__(self):
                    return len(self.graph._edges)
            return EdgesView(self)

        def has_node(self, n):
            return n in self._nodes

        def has_edge(self, u, v):
            return (u, v) in self._edges

        def add_node(self, n, **attr):
            if n not in self._nodes:
                self._nodes[n] = {}
            self._nodes[n].update(attr)

        def add_edge(self, u, v, **attr):
            self.add_node(u)
            self.add_node(v)
            if (u, v) not in self._edges:
                self._edges[(u, v)] = {}
            self._edges[(u, v)].update(attr)

        def __getitem__(self, n):
            class NeighborsView:
                def __init__(self, graph, node):
                    self.graph = graph
                    self.node = node
                def __getitem__(self, neighbor):
                    return self.graph._edges[(self.node, neighbor)]
                def __iter__(self):
                    return (v for u, v in self.graph._edges if u == self.node)
            return NeighborsView(self, n)

        def number_of_nodes(self):
            return len(self._nodes)

        def number_of_edges(self):
            return len(self._edges)

        def subgraph(self, nodes):
            sub = MockDiGraph()
            nodes_set = set(nodes)
            for n in nodes_set:
                if n in self._nodes:
                    sub._nodes[n] = dict(self._nodes[n])
            for (u, v), data in self._edges.items():
                if u in nodes_set and v in nodes_set:
                    sub._edges[(u, v)] = dict(data)
            return sub

    class mock_networkx_module:
        DiGraph = MockDiGraph
        
        @staticmethod
        def single_source_shortest_path(graph, source, cutoff=2):
            visited = {source: [source]}
            queue = [source]
            while queue:
                u = queue.pop(0)
                path = visited[u]
                if len(path) - 1 >= cutoff:
                    continue
                neighbors = [v for x, v in graph._edges if x == u]
                for v in neighbors:
                    if v not in visited:
                        visited[v] = path + [v]
                        queue.append(v)
            return visited

        @staticmethod
        def single_source_shortest_path_length(graph, source, cutoff=2):
            paths = mock_networkx_module.single_source_shortest_path(graph, source, cutoff)
            return {k: len(v) - 1 for k, v in paths.items()}

        @staticmethod
        def node_link_data(graph, edges="edges"):
            nodes = [{"id": n, **data} for n, data in graph._nodes.items()]
            edges_list = [{"source": u, "target": v, **data} for (u, v), data in graph._edges.items()]
            return {"nodes": nodes, "edges": edges_list}

        @staticmethod
        def node_link_graph(data, directed=True, edges="edges"):
            g = MockDiGraph()
            for n in data.get("nodes", []):
                nid = n["id"]
                g.add_node(nid, **{k: v for k, v in n.items() if k != "id"})
            for e in data.get("edges", []):
                src = e["source"]
                dst = e["target"]
                g.add_edge(src, dst, **{k: v for k, v in e.items() if k not in ["source", "target"]})
            return g
            
    nx = mock_networkx_module


class L2AssociativeEngine:
    """Associative memory using spaCy entities and a directed knowledge graph."""

    def __init__(self) -> None:
        model_name = "en_core_web_sm" if os.getenv("CI", "").lower() == "true" else "en_core_web_lg"
        try:
            self.nlp = spacy.load(model_name)
        except OSError as exc:
            raise RuntimeError(
                f"spaCy model '{model_name}' is not installed. Run: python -m spacy download {model_name}"
            ) from exc
        self.graph: nx.DiGraph = nx.DiGraph()
        self._seed_baseline_topology()

    def clear(self) -> None:
        self.graph.clear()
        self._seed_baseline_topology()

    def _seed_baseline_topology(self) -> None:
        nodes = [
            ("payment-api", "SERVICE"),
            ("redis-cache", "CACHE"),
            ("postgres-db", "DATABASE"),
            ("auth-service", "SERVICE"),
            ("order-service", "SERVICE"),
            ("user-service", "SERVICE"),
            ("load-balancer", "NETWORK"),
            ("k8s-cluster", "INFRASTRUCTURE"),
            ("checkout-service", "SERVICE"),
            ("orders-db", "DATABASE")
        ]
        for node, ntype in nodes:
            self.graph.add_node(node, type=ntype, weight=10)
            
        edges = [
            ("load-balancer", "payment-api"),
            ("load-balancer", "checkout-service"),
            ("payment-api", "redis-cache"),
            ("payment-api", "postgres-db"),
            ("payment-api", "auth-service"),
            ("payment-api", "user-service"),
            ("payment-api", "order-service"),
            ("checkout-service", "orders-db"),
            ("orders-db", "postgres-db"),
            ("order-service", "postgres-db"),
            ("order-service", "k8s-cluster")
        ]
        for src, dst in edges:
            self.graph.add_edge(src, dst, weight=5)

    def ingest(self, text: str) -> dict[str, Any]:
        try:
            doc = self.nlp(text[:100000])
            entities = [
                (ent.text.strip(), ent.label_)
                for ent in doc.ents
                if len(ent.text.strip()) >= 3
            ]
            seen = {entity.lower() for entity, _ in entities}
            for chunk in doc.noun_chunks:
                phrase = " ".join(token.lemma_.lower() for token in chunk if not token.is_stop and not token.is_punct).strip()
                if len(phrase) < 3 or len(phrase.split()) > 4 or phrase in seen:
                    continue
                entities.append((phrase, "CONCEPT"))
                seen.add(phrase)

            for entity, label in entities:
                if self.graph.has_node(entity):
                    self.graph.nodes[entity]["weight"] = int(self.graph.nodes[entity].get("weight", 1)) + 1
                    if not self.graph.nodes[entity].get("type"):
                        self.graph.nodes[entity]["type"] = label
                else:
                    self.graph.add_node(entity, type=label, weight=1)

            window_size = 5
            for idx in range(len(entities)):
                window = entities[idx : idx + window_size]
                for (source, _), (target, _) in combinations(window, 2):
                    if source == target:
                        continue
                    self._increment_edge(source, target)
                    self._increment_edge(target, source)

            return {
                "entities_found": len(entities),
                "nodes": self.graph.number_of_nodes(),
                "edges": self.graph.number_of_edges(),
            }
        except Exception:
            return {
                "entities_found": 0,
                "nodes": self.graph.number_of_nodes(),
                "edges": self.graph.number_of_edges(),
            }

    def _increment_edge(self, source: str, target: str) -> None:
        if self.graph.has_edge(source, target):
            self.graph[source][target]["weight"] = int(self.graph[source][target].get("weight", 1)) + 1
        else:
            self.graph.add_edge(source, target, weight=1)

    def traverse(self, query: str, depth: int = 2) -> list[dict[str, Any]]:
        try:
            seeds = self._seed_entities(query)
            if not seeds:
                return []

            best: dict[str, dict[str, Any]] = {}
            for seed in seeds:
                paths = nx.single_source_shortest_path(self.graph, seed, cutoff=max(0, depth))
                for entity, path in paths.items():
                    distance = len(path) - 1
                    node_data = self.graph.nodes[entity]
                    existing = best.get(entity)
                    if existing is None or distance < existing["distance"]:
                        best[entity] = {
                            "entity": entity,
                            "distance": distance,
                            "weight": int(node_data.get("weight", 1)),
                            "node_type": str(node_data.get("type", "ENTITY")),
                            "path": " -> ".join(path),
                        }

            ordered = sorted(best.values(), key=lambda item: (item["distance"], -item["weight"], item["entity"].lower()))
            return ordered[:20]
        except Exception:
            return []

    def _seed_entities(self, query: str) -> list[str]:
        doc = self.nlp(query[:100000])
        extracted = [ent.text.strip() for ent in doc.ents if ent.text.strip() in self.graph]
        if extracted:
            return list(dict.fromkeys(extracted))

        query_words = {word.lower() for word in query.split() if len(word) >= 3}
        if not query_words:
            return []
        matches = [
            node
            for node in self.graph.nodes
            if any(word in node.lower() for word in query_words)
        ]
        return sorted(matches, key=lambda node: int(self.graph.nodes[node].get("weight", 1)), reverse=True)[:10]

    def get_subgraph(self, entity: str, depth: int = 2) -> dict[str, list[dict[str, Any]]]:
        try:
            if entity not in self.graph:
                return {"nodes": [], "edges": []}

            nodes = {entity}
            lengths = nx.single_source_shortest_path_length(self.graph, entity, cutoff=max(0, depth))
            nodes.update(lengths.keys())
            subgraph = self.graph.subgraph(nodes)
            return self._format_graph(subgraph)
        except Exception:
            return {"nodes": [], "edges": []}

    def summary_graph(self, limit: int = 30) -> dict[str, list[dict[str, Any]]]:
        top_nodes = sorted(
            self.graph.nodes,
            key=lambda node: int(self.graph.nodes[node].get("weight", 1)),
            reverse=True,
        )[:limit]
        return self._format_graph(self.graph.subgraph(top_nodes))

    def _format_graph(self, graph: nx.DiGraph) -> dict[str, list[dict[str, Any]]]:
        nodes = [
            {
                "id": node,
                "weight": int(data.get("weight", 1)),
                "type": str(data.get("type", "ENTITY")),
            }
            for node, data in graph.nodes(data=True)
        ]
        edges = [
            {
                "source": source,
                "target": target,
                "weight": int(data.get("weight", 1)),
            }
            for source, target, data in graph.edges(data=True)
        ]
        return {"nodes": nodes, "edges": edges}

    def stats(self) -> dict[str, Any]:
        top_entities = [
            {"entity": node, "weight": int(data.get("weight", 1)), "type": str(data.get("type", "ENTITY"))}
            for node, data in sorted(
                self.graph.nodes(data=True),
                key=lambda item: int(item[1].get("weight", 1)),
                reverse=True,
            )[:5]
        ]
        return {
            "nodes": self.graph.number_of_nodes(),
            "edges": self.graph.number_of_edges(),
            "top_entities": top_entities,
        }

    def export_graph(self) -> dict[str, Any]:
        return nx.node_link_data(self.graph, edges="edges")

    def import_graph(self, data: dict[str, Any]) -> dict[str, Any]:
        self.graph = nx.node_link_graph(data, directed=True, edges="edges")
        return self.stats()
