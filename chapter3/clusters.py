import logging
import random
from math import sqrt
from itertools import combinations

from PIL import Image, ImageDraw


logger = logging.getLogger(__name__)


def generate_from_file(filename):
    with open(filename) as f:
        first_line = f.readline()
        col_names = first_line.strip().split('\t')[1:]

        for line in f:
            p = line.strip().split('\t')
            yield (p[0], col_names, [int(s) for s in p[1:]])


def readfile(filename):
    row_names = []
    row_vectors = []

    for row_name, col_name, data in generate_from_file(filename):
        row_names.append(row_name)
        row_vectors.append(data)

    # XXX: col_name will always be the same
    return row_names, col_name, row_vectors


def transpose(rows):
    t = [[] for _ in range(len(rows[0]))]
    for row in rows:
        for idx, e in enumerate(row):
            t[idx].append(e)

    return t


def pearson(v1, v2):
    if len(v1) != len(v2):
        raise ValueError('Length of v1 != v2: {} != {}'.format(len(v1), len(v2)))

    sum1 = sum(v1)
    sum2 = sum(v2)

    sq_sum1 = sum(v ** 2 for v in v1)
    sq_sum2 = sum(v ** 2 for v in v2)

    p_sum = sum(v1 * v2 for v1, v2 in zip(v1, v2))

    num = p_sum - (sum1 * sum2 / len(v1))
    den = sqrt((sq_sum1 - sum1 ** 2 / len(v1)) * (sq_sum2 - sum2 ** 2 / len(v1)))
    if den == 0:
        return 0

    # Returned value should be distance. The lower the distance the closer they are.
    return 1.0 - num / den


def tanimoto(v1, v2):
    if len(v1) != len(v2):
        raise ValueError('Length of v1 != v2: {} != {}'.format(len(v1), len(v2)))

    intersected = 0
    in_v1 = 0
    in_v2 = 0

    for e1, e2 in zip(v1, v2):
        if e1 != 0:
            in_v1 += 1
        if e2 != 0:
            in_v2 += 1
        if e1 != 0 and e2 != 0:
            intersected += 1

    return 1.0 - (float(intersected) / (in_v1 + in_v2 - intersected))


class Cluster(object):

    def __init__(self, vec, left=None, right=None, distance=0.0, id=None):
        self.vec = vec
        self.left = left
        self.right = right
        self.distance = distance
        self.id = id

    def height(self):
        if self.left is None and self.right is None:
            return 1
        else:
            return self.left.height() + self.right.height()

    def depth(self):
        if self.left is None and self.right is None:
            return 0
        else:
            return max(self.left.depth(), self.right.depth()) + self.distance


def hierarchical_cluster(rows, distance=pearson):
    # Create the initial (leaf node)
    clusters = [Cluster(row, id=i) for i, row in enumerate(rows)]
    new_merged_cluster_id = -1  # ID for merged cluster. Will be -1, -2, -3, ...

    # Loop until clusters number reaches 1
    dist_cache = {}  # Stores dist calculated previously
    while len(clusters) > 1:
        # Find the closest pair in the clusters
        closest_dist = 1.0  # The maximum possible value from "distance" function
        for c1, c2 in combinations(clusters, 2):
            if (c1.id, c2.id) in dist_cache:
                dist = dist_cache[(c1.id, c2.id)]
            else:
                dist = distance(c1.vec, c2.vec)
                dist_cache[(c1.id, c2.id)] = dist

            if dist < closest_dist:
                closest = (c1, c2)
                closest_dist = dist
        logger.debug('Closest pair: ({}, {}), dist: {}'.format(
            closest[0].id, closest[1].id, closest_dist))

        # Merge the closest pair
        vec_len = len(closest[0].vec)
        merged_vec = [(closest[0].vec[i] + closest[1].vec[i]) / 2.0
                      for i in range(vec_len)]

        # Create a new cluster
        merged_cluster = Cluster(merged_vec,
                                 left=closest[0],
                                 right=closest[1],
                                 distance=closest_dist,
                                 id=new_merged_cluster_id)

        # Replace the closest cluster pairs with merged cluster
        clusters.remove(closest[0])
        clusters.remove(closest[1])
        clusters.append(merged_cluster)
        new_merged_cluster_id -= 1

    return clusters[0]


def print_cluster(cluster, labels=None, n=0):
    for i in range(n):
        print(' ', end='')

    if cluster.id < 0:
        # Merged cluster.
        print('-')
    else:
        # Leaf
        if labels is None:
            print(cluster.id)
        else:
            print(labels[cluster.id])

    # Recursively print the left and right branch
    if cluster.left is not None:
        print_cluster(cluster.left, labels=labels, n=n+1)
    if cluster.right is not None:
        print_cluster(cluster.right, labels=labels, n=n+1)


def draw_dendrogram(clust, labels, jpeg='clusters.jpg'):
    # 20 pixel high and fixed width for each final cluster
    height = clust.height() * 20
    width = 1500
    depth = clust.depth()

    # Width is fixed. Scale distance accordingly
    width_margin = 300
    scaling = (width - width_margin) / depth

    img = Image.new('RGB', (width, height), (255, 255, 255))
    draw = ImageDraw.Draw(img)

    # Draw the first horizontal line,
    draw.line((0, height/2, 10, height/2), fill=(255, 0, 0))

    # Then the rest
    draw_node(draw, clust, 10, (height/2), scaling, labels)
    img.save(jpeg, 'JPEG')


def draw_node(draw, clust, x, y, scaling, labels):
    if clust.id < 0:
        left_h = clust.left.height() * 20
        right_h = clust.right.height() * 20
        total_h = left_h + right_h
        top = y - total_h / 2
        bottom = y + total_h / 2

        # Horizontal Line length
        line_length = clust.distance * scaling

        # Vertical line from this cluster to children
        draw.line((x, top+left_h/2, x, bottom-right_h/2), fill=(255, 0, 0))

        # Horizontal line to left cluster
        draw.line((x, top+left_h/2, x+line_length, top+left_h/2), fill=(255, 0, 0))

        # Horizontal line to right cluster
        draw.line((x, bottom-right_h/2, x+line_length, bottom-right_h/2), fill=(255, 0, 0))

        # Recursively call the function to the left and right node
        draw_node(draw, clust.left, x+line_length, top+left_h/2, scaling, labels)
        draw_node(draw, clust.right, x+line_length, bottom-right_h/2, scaling, labels)
    else:
        draw.text((x+5, y-7), labels[clust.id], (0, 0, 0))


def kmean_cluster(rows, distance=pearson, k=4):
    dimension = len(rows[0])
    # Determine the minimum and maximum values for each point
    ranges = [(min(row[i] for row in rows), max(row[i] for row in rows))
              for i in range(dimension)]

    # Create k randomly placed centroids
    clusters = list()
    for i in range(k):
        p = [random.random() * (ranges[i][1] - ranges[i][0]) + ranges[i][0]
             for i in range(dimension)]
        clusters.append(p)

    last_match = None
    for t in range(100):
        logger.info(last_match)
        logger.info(f'Iteration {t}')
        match_list = [[] for _ in range(k)]

        for row_idx, row in enumerate(rows):
            # Find the closest cluster to the row
            # Initialization
            closest = distance(clusters[0], row)
            closest_cluster_idx = 0
            for idx, cluster in enumerate(clusters):
                d = distance(cluster, row)
                if d < closest:
                    closest = d
                    closest_cluster_idx = idx
            match_list[closest_cluster_idx].append(row_idx)

        # If the results are the same as last time, this is complete
        if match_list == last_match:
            break
        else:
            last_match = match_list

        # Move the centroids to the average of their members
        for cluster_idx, matched_rows in enumerate(match_list):
            avgs = [0.0] * dimension
            if matched_rows:
                for row_idx in matched_rows:
                    for i in range(dimension):
                        avgs[i] += rows[row_idx][i]
                for i in range(dimension):
                    avgs[i] /= len(matched_rows)
                clusters[cluster_idx] = avgs

    return match_list


def scaledown(rows, distance=pearson, rate=0.01, complete_iterate=False):
    n = len(rows)

    dist_m = [[distance(rows[i], rows[j]) for j in range(n)]
              for i in range(n)]

    # Randomly initialize the starting points of the locations in 2D
    data_2d = [[random.random(), random.random()] for _ in range(n)]
    dist_2d = [[0.0 for j in range(n)] for i in range(n)]

    last_error = None
    for m in range(0, 1000):
        logger.info(f'Iteration {m}')
        # Calculate the distance in 2D
        for i in range(n):
            for j in range(n):
                d1 = (data_2d[i][0] - data_2d[j][0]) ** 2
                d2 = (data_2d[i][1] - data_2d[j][1]) ** 2
                dist_2d[i][j] = sqrt(d1 + d2)

        # Move points
        grad = [[0.0, 0.0] for i in range(n)]

        total_error = 0
        for j in range(n):
            for k in range(n):
                if j == k:
                    continue
                # The error is percent difference between the distances
                error = (dist_2d[j][k] - dist_m[j][k]) / dist_m[j][k]

                # Each point needs to be moved away from or toward the other
                # point in proportion to how much error it has and the current
                # distance between them
                grad[j][0] += ((data_2d[j][0] - data_2d[k][0]) / dist_2d[j][k]) * error
                grad[j][1] += ((data_2d[j][1] - data_2d[k][1]) / dist_2d[j][k]) * error

                # Keep track of the total error
                total_error += abs(error)
        logger.info(f'Total error: {total_error}')

        # If the answer got worse by moving the points, we are done
        if not complete_iterate and last_error and last_error < total_error:
            break
        last_error = total_error

        # Move each of the points by the learning rate times the gradient
        for i in range(n):
            data_2d[i][0] -= grad[i][0] * rate
            data_2d[i][1] -= grad[i][1] * rate

    return data_2d


def draw_2d(data, labels, jpeg='mds2d.jpg'):
    img = Image.new('RGB', (2000, 2000), (255, 255, 255))
    draw = ImageDraw.Draw(img)

    for i in range(len(data)):
        x = (data[i][0] + 0.5) * 1000
        y = (data[i][1] + 0.5) * 1000
        draw.text((x, y), labels[i], (0, 0, 0))
    img.save(jpeg, 'JPEG')
