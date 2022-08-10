import graphviz

from vocoder.soft_simulate import PathLeaves


def graph(leaves: PathLeaves):
    dot = graphviz.Digraph()
    created_nodes = set[str]()
    for leaf in leaves:
        dot.node(str(id(leaf)), str(leaf.state))
        created_nodes.add(str(id(leaf)))
        while (p := leaf.parent) is not None:
            p_id = str(id(p))
            n_id = str(id(leaf))
            if p_id in created_nodes:
                dot.edge(p_id, n_id)
                break
            dot.node(p_id, str(p.state))
            created_nodes.add(p_id)
            dot.edge(p_id, n_id)
            leaf = p
    return dot
