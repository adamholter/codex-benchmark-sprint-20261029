"""Official mixed-rule extensions, reported separately from the core protocol."""
from adapters import korbench


def load_cases():
    cases = []
    for case in korbench.load_cases(include_mixed=True):
        if case['category'] != 'mixed':
            continue
        case['benchmark'] = 'korbench_mixed'
        case['category'] = case['metadata']['mixed_mode']
        # The upstream scoring adapter dispatches mixed scoring by category.
        case['metadata']['scoring_category'] = 'mixed'
        cases.append(case)
    return cases


def score(case, response):
    return korbench.score(dict(case, category='mixed'), response)
