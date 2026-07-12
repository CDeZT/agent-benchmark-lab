def free_space(d):
    return [[1.0, float(d)], [0.0, 1.0]]


def thin_lens_matrix(f):
    if f == 0:
        raise ValueError("focal length must be non-zero")
    return [[1.0, 0.0], [-1.0 / float(f), 1.0]]


def cascade(matrices):
    if not matrices:
        raise ValueError("cascade requires at least one matrix")
    result = [[1.0, 0.0], [0.0, 1.0]]
    for m in matrices:
        result = _mul(m, result)  # apply next element on the left
    return result


def _mul(a, b):
    return [
        [a[0][0] * b[0][0] + a[0][1] * b[1][0], a[0][0] * b[0][1] + a[0][1] * b[1][1]],
        [a[1][0] * b[0][0] + a[1][1] * b[1][0], a[1][0] * b[0][1] + a[1][1] * b[1][1]],
    ]
