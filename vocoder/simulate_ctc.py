import numpy as np

from vocoder.token_encoding import TokenEncoding


def simulate_ctc(utterance: str, token_encoding: TokenEncoding) -> np.ndarray:
    encoded_utterance = token_encoding.encode(utterance)

    tokens = list[int]()
    last_token = -1
    for t in encoded_utterance:
        if t == last_token:
            rep = np.random.randint(1, 5)
            tokens.extend([token_encoding.blank] * rep)
        rep = np.random.randint(1, 5)
        tokens.extend([t] * rep)
        last_token = t

    logits = np.random.uniform(size=(len(tokens), token_encoding.n_tokens))

    for row, col in enumerate(tokens):
        logits[row, col] += np.random.uniform(5, 10)

    softmax_out = np.exp(logits) / np.exp(logits).sum(1)[:, None]
    return np.log(softmax_out)
