from abcd import free_space, thin_lens_matrix, cascade


def almost_mat(a, b, eps=1e-9):
    return all(abs(a[i][j] - b[i][j]) <= eps for i in range(2) for j in range(2))


assert almost_mat(free_space(2.0), [[1, 2.0], [0, 1]])
assert almost_mat(thin_lens_matrix(50.0), [[1, 0], [-0.02, 1]])

# free space then lens: M = M_lens @ M_space
m = cascade([free_space(100.0), thin_lens_matrix(50.0)])
# A=1, B=100, C=-1/50, D=1-100/50=-1
assert almost_mat(m, [[1.0, 100.0], [-0.02, -1.0]]), m

try:
    cascade([])
    raise AssertionError("expected ValueError")
except ValueError:
    pass

print("ok")
