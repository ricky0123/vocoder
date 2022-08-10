import transformers
from transformers import Wav2Vec2ForCTC, Wav2Vec2Processor

from vocoder.token_encoding import TokenEncoding

transformers.logging.set_verbosity_error()


def load_model():
    processor = Wav2Vec2Processor.from_pretrained("facebook/wav2vec2-base-960h")
    model = Wav2Vec2ForCTC.from_pretrained("facebook/wav2vec2-base-960h")

    def _model(x):
        in_ = processor(x, sampling_rate=16000, return_tensors="pt").input_values[0]
        logits = model(in_).logits[0]
        return logits.detach().cpu().numpy()

    return _model


token_encoding = TokenEncoding.from_str_to_token(
    {
        ".": 0,
        "<s>": 1,
        "</s>": 2,
        "<unk>": 3,
        " ": 4,
        "e": 5,
        "t": 6,
        "a": 7,
        "o": 8,
        "n": 9,
        "i": 10,
        "h": 11,
        "s": 12,
        "r": 13,
        "d": 14,
        "l": 15,
        "u": 16,
        "m": 17,
        "w": 18,
        "c": 19,
        "f": 20,
        "g": 21,
        "y": 22,
        "p": 23,
        "b": 24,
        "v": 25,
        "k": 26,
        "'": 27,
        "x": 28,
        "j": 29,
        "q": 30,
        "z": 31,
    }
)
