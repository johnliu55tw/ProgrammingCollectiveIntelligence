import logging
from math import sqrt
from os.path import join as p_join


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


def similarity_pearson(prefs, person1, person2):
    both_rated_items = [name
                        for name in prefs[person1]
                        if name in prefs[person2]]

    n = len(both_rated_items)

    if n == 0:
        return 0

    sum1 = sum(prefs[person1][item] for item in both_rated_items)
    sum2 = sum(prefs[person2][item] for item in both_rated_items)

    sum1_sq = sum(prefs[person1][item] ** 2 for item in both_rated_items)
    sum2_sq = sum(prefs[person2][item] ** 2 for item in both_rated_items)

    p_sum = sum(prefs[person1][item] * prefs[person2][item] for item in both_rated_items)

    # Calculate pearson score
    num = p_sum - (sum1 * sum2 / n)
    den = sqrt((sum1_sq - (sum1 ** 2) / n) * (sum2_sq - (sum2 ** 2) / n))

    if den == 0:
        return 0

    return num / den


def top_matches(prefs, person, n=None, sim_function=similarity_pearson):
    score_name_pairs = [(sim_function(prefs, person, other), other)
                        for other in prefs if other != person]

    score_name_pairs.sort(key=lambda x: x[0], reverse=True)

    return score_name_pairs[0:n] if n is not None else score_name_pairs


def get_recommendations(prefs, person, sim_function=similarity_pearson):
    matches = [m for m in top_matches(prefs, person, sim_function=sim_function)
               if m[0] > 0]
    item_sum = {}
    sim_sum = {}
    for sim_score, other in matches:
        for item in prefs[other]:
            if item not in prefs[person]:
                item_sum.setdefault(item, 0)
                item_sum[item] += sim_score * prefs[other][item]

                sim_sum.setdefault(item, 0)
                sim_sum[item] += sim_score

    rankings = [(item_sum[item] / sim_sum[item], item) for item in item_sum]
    rankings.sort(reverse=True, key=lambda x: x[0])
    return rankings


def transpose_prefs(prefs):
    transposed = {}
    for name, item_ratings in prefs.items():
        for item, rating in item_ratings.items():
            transposed.setdefault(item, dict())
            transposed[item][name] = rating

    return transposed


def calculate_similar_items(prefs, n=None):
    result = {}
    item_prefs = transpose_prefs(prefs)

    for idx, item in enumerate(item_prefs, start=1):
        if idx % 100 == 0:
            logging.info('Processed: {} / {}'.format(idx, len(item)))
        tops = top_matches(item_prefs, item, n=n, sim_function=similarity_distance)
        result[item] = tops

    return result


def get_recommended_items(prefs, user, sim_items_data=None):
    if sim_items_data is None:
        sim_items_data = calculate_similar_items(prefs)

    user_rating = prefs[user]
    scores = {}
    total_sim_scores = {}

    for item, rating in user_rating.items():
        # Calculate recommendation score of other items
        for sim_score, other_item in sim_items_data[item]:
            if other_item in user_rating:
                continue
            scores.setdefault(other_item, 0)
            scores[other_item] += sim_score * rating

            total_sim_scores.setdefault(other_item, 0)
            total_sim_scores[other_item] += sim_score

    # Normalized the score
    result = [(score / total_sim_scores[item], item)
              for item, score in scores.items()]
    result.sort(key=lambda x: x[0], reverse=True)

    return result


def load_movielens(folder='./ml-100k/', encoding='iso-8859-1'):
    # Get movie id to title mapping
    movies = {}
    with open(p_join(folder, 'u.item'), encoding=encoding) as f:
        for line in f:
            (m_id, m_title) = line.split('|')[0:2]
            movies[m_id] = m_title

    # Get preference data
    prefs = {}
    with open(p_join(folder, 'u.data')) as f:
        for line in f:
            (u_id, m_id, rating, ts) = line.split('\t')
            prefs.setdefault(u_id, dict())
            prefs[u_id][movies[m_id]] = float(rating)

    return prefs
