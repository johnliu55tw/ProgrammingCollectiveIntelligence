import logging


critics = {
    'Claudia Puig': {
        'Just My Luck': 3.0,
        'Snakes on a Plane': 3.5,
        'Superman Returns': 4.0,
        'The Night Listener': 4.5,
        'You, Me and Dupree': 2.5
    },
    'Gene Seymour': {
        'Just My Luck': 1.5,
        'Lady in the Water': 3.0,
        'Snakes on a Plane': 3.5,
        'Superman Returns': 5.0,
        'The Night Listener': 3.0,
        'You, Me and Dupree': 3.5
    },
    'Jack Matthews': {
        'Lady in the Water': 3.0,
        'Snakes on a Plane': 4.0,
        'Superman Returns': 5.0,
        'The Night Listener': 3.0,
        'You, Me and Dupree': 3.5
    },
    'Lisa Rose': {
        'Just My Luck': 3.0,
        'Lady in the Water': 2.5,
        'Snakes on a Plane': 3.5,
        'Superman Returns': 3.5,
        'The Night Listener': 3.0,
        'You, Me and Dupree': 2.5
    },
    'Michael Phillips': {
        'Lady in the Water': 2.5,
        'Snakes on a Plane': 3.0,
        'Superman Returns': 3.5,
        'The Night Listener': 4.0
    },
    'Mick LaSalle': {
        'Just My Luck': 2.0,
        'Lady in the Water': 3.0,
        'Snakes on a Plane': 4.0,
        'Superman Returns': 3.0,
        'The Night Listener': 3.0,
        'You, Me and Dupree': 2.0
    },
    'Toby': {
        'Snakes on a Plane': 4.5,
        'Superman Returns': 4.0,
        'You, Me and Dupree': 1.0
    }
}


def euclidean_distance(v1, v2, inverse=False):
    from math import sqrt
    """Calculate the euclidean distance of v1 and v2.

    v1: List of values
    v2: List of values
    inverse: Boolean indicates whether the result should be inversed.
        r = (1 / 1 + r)
    """
    if len(v1) != len(v2):
        raise ValueError('Length diff: {} != {}'.format(len(v1), len(v2)))

    result = sqrt(sum((e1 - e2) ** 2 for e1, e2 in zip(v1, v2)))

    return 1 / (1 + result) if inverse else result


def similarity_distance(prefs, person1, person2):
    both_rated_movies = [name
                         for name in prefs[person1]
                         if name in prefs[person2]]

    logging.debug(f'both rated movies: {both_rated_movies}')

    p1_ratings = [prefs[person1][name] for name in both_rated_movies]
    p2_ratings = [prefs[person2][name] for name in both_rated_movies]
    logging.debug(f"Person1's ratings: {p1_ratings}")
    logging.debug(f"Person2's ratings: {p2_ratings}")

    return euclidean_distance(p1_ratings, p2_ratings, inverse=True)
