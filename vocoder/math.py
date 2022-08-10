import math

negative_infinity = -float("inf")


def logadd(*args: float) -> float:
    if all(a == negative_infinity for a in args):
        return negative_infinity
    a_max = max(args)
    lsp = math.log(sum(math.exp(a - a_max) for a in args))
    return a_max + lsp
