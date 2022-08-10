from tests.fixtures.programs import Program
from vocoder.compile_grammar import compile_grammar
from vocoder.namespace import Namespace
from vocoder.soft import Soft, add_skip_transition, add_symbol_transition
from vocoder.soft_simulate import (
    Executor,
    Node,
    initial_path_leaves,
    simplify,
    step_tree,
    text_simulate,
)


def test_step_tree_skip_transitions():
    soft = Soft()
    state = soft.initial
    for _ in range(5):
        state = add_skip_transition(soft, state)
    stepped = step_tree(soft, [Node(soft.initial)])
    assert len(stepped) == 1
    (node,) = stepped
    assert soft.is_final_state(node.state)


def test_step_tree_symbol_transitions():
    soft = Soft()
    add_symbol_transition(soft, soft.initial, "xyz")
    initial_node = Node(soft.initial)
    stepped = step_tree(soft, [initial_node])
    assert len(stepped) == 1
    (node,) = stepped
    assert node == initial_node


def test_run_text(program: Program):
    lexicon_registry = program.grammar.lexicon_registry
    soft = compile_grammar(
        program.grammar.config,
        program.grammar.lexicon_registry,
        program.grammar.attribute_registry,
    )
    interpreter = Executor(lexicon_registry, Namespace())
    path_leaves = initial_path_leaves(soft)
    for line in program.input:
        words, path_leaves = text_simulate(soft, path_leaves, lexicon_registry, line)
        path_leaves, output = simplify(path_leaves)
        interpreter.eat(words, output)
    program.test()
