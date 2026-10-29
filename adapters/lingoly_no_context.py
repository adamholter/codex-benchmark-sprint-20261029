"""Published no-context memorization diagnostic, kept separate from full context."""
from adapters import lingoly


def load_cases():
    cases = lingoly.load_no_context_cases()
    for case in cases:
        case['benchmark'] = 'lingoly_no_context'
    return cases


score = lingoly.score
