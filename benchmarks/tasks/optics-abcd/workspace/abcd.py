def free_space(d):
    # Buggy: swaps B
    return [[1, 0], [d, 1]]


def thin_lens_matrix(f):
    # Buggy: positive C
    return [[1, 0], [1 / f, 1]]


def cascade(matrices):
    # Buggy: multiplies in wrong order and no empty check
    result = [[1, 0], [0, 1]]
    for m in matrices:
        result = _mul(result, m)
    return result


def _mul(a, b):
    return [
        [a[0][0] * b[0][0] + a[0][1] * b[1][0], a[0][0] * b[0][1] + a[0][1] * b[1][1]],
        [a[1][0] * b[0][0] + a[1][1] * b[1][0], a[1][0] * b[0][1] + a[1][1] * b[1][1]],
    ]
