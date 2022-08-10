from tests.fixtures.programs import Program
from vocoder.acoustic_models.wav2vec2 import token_encoding
from vocoder.simulate_ctc import simulate_ctc


def test_simulate_ctc(program: Program):
    for utterance in program.input:
        ctc_output = simulate_ctc(utterance, token_encoding)
        predicted_utterance = token_encoding.greedy_decode_tokens(ctc_output)
        assert utterance == predicted_utterance
