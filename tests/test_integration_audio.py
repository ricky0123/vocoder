from tests.fixtures.programs import Program
from vocoder.acoustic_models.wav2vec2 import token_encoding
from vocoder.compile_grammar import compile_grammar
from vocoder.namespace import Namespace
from vocoder.simulate_ctc import simulate_ctc
from vocoder.soft_beam_search import beam_search
from vocoder.soft_simulate import Executor, initial_path_leaves, simplify


def test_run_audio(program: Program):
    soft = compile_grammar(
        program.grammar.config,
        program.grammar.lexicon_registry,
        program.grammar.attribute_registry,
    )
    executor = Executor(program.grammar.lexicon_registry, Namespace())
    path_leaves = initial_path_leaves(soft)
    for line in program.input:
        ctc_output = simulate_ctc(line, token_encoding)
        new_words, _, path_leaves = beam_search(
            soft,
            program.grammar.lexicon_registry,
            path_leaves,
            ctc_output,
            token_encoding,
        )
        path_leaves, output = simplify(path_leaves)
        executor.eat(new_words, output)
    program.test()
