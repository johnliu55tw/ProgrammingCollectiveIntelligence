def generate_from_file(filename):
    with open(filename) as f:
        first_line = f.readline()
        col_names = first_line.strip().split('\t')[1:]

        for line in f:
            p = line.strip().split('\t')
            yield (p[0], col_names, p[1:])


def readfile(filename):
    row_names = []
    row_vectors = []

    for row_name, col_name, data in generate_from_file(filename):
        row_names.append(row_name)
        row_vectors.append(data)

    # XXX: col_name will always be the same
    return row_names, col_name, row_vectors
