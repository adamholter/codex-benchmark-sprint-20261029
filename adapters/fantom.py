"""FANToM short-context deterministic question tracks, using upstream methods.

This is a subset evaluation, not the full FANToM All* metric. Free-text
embedding-based belief and fact-F1 tracks are excluded. Original prompts,
choice ordering with seed 99, and per-question scoring are retained.
"""
import ast
import hashlib
import json
from pathlib import Path
import random
import re
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'sources' / 'fantom'
METHODS = {'set_beliefQA_multiple_choices', 'setup_fantom', 'parse_response',
           'evaluate_mc_belief_q', 'evaluate_list_q', 'evaluate_binary_q_with_f1'}


def _upstream():
    tree = ast.parse((SOURCE / 'eval_fantom.py').read_text())
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'FantomEvalAgent')
    cls.body = [n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name in METHODS]
    module = ast.fix_missing_locations(ast.Module(body=[cls], type_ignores=[]))
    scope = {'random': random.Random(99)}
    exec(compile(module, str(SOURCE / 'eval_fantom.py'), 'exec'), scope)
    agent = object.__new__(scope['FantomEvalAgent'])
    agent.args = SimpleNamespace(aggregation_target='set', conversation_input_type='short')
    return agent


class _Rows:
    def __init__(self, rows):
        self.rows = rows

    def iterrows(self):
        return iter(enumerate(self.rows))


def load_cases():
    archive = SOURCE / 'fantom.tar.gz'
    assert hashlib.sha256(archive.read_bytes()).hexdigest() == '1d08dfa0ea474c7f83b9bc7e3a7b466eab25194043489dd618b4c5223e1253a4'
    data = json.loads((SOURCE / 'fantom_v1.json').read_text())
    agent = _upstream()
    agent.fantom_df = _Rows(data)
    agent.setup_fantom()
    cases = []
    for index, qa in enumerate(agent.flattened_fantom):
        kind = qa['question_type']
        if not kind.startswith('tom:') or not kind.endswith((':multiple-choice', ':list', ':binary')):
            continue
        if qa.get('missed_info_accessibility') != 'inaccessible':
            continue
        if qa['correct_answer'] == 'no:long':
            continue
        cases.append({'benchmark': 'fantom', 'id': f"{qa['set_id']}-{index}",
                      'category': kind, 'prompt': qa['input_text'],
                      'gold': qa['correct_answer'],
                      'metadata': {'qa': qa, 'set_id': qa['set_id'], 'input_type': 'short',
                                   'scope': 'deterministic inaccessible-information tracks only'}})
    return cases


def score(case, response):
    agent = _upstream()
    qa = case['metadata']['qa']
    response = agent.parse_response(response)
    kind = qa['question_type']
    if kind.endswith(':multiple-choice'):
        correct = agent.evaluate_mc_belief_q(qa, response)
        options = re.findall(r'\(([ab])\)', response.lower())
        strict_valid = len(set(options)) <= 1
    elif kind.endswith(':list'):
        correct, _, _ = agent.evaluate_list_q(qa, response)
        strict_valid = True
    else:
        correct = agent.evaluate_binary_q_with_f1(qa, response) if response.split() else False
        strict_valid = True
    return {'correct': bool(correct), 'extracted': response,
            'strict_correct': bool(correct and strict_valid),
            'scorer': 'upstream per-question method; not aggregate All*'}


def validate():
    cases = load_cases()
    assert len({c['id'] for c in cases}) == len(cases)
    seen = set()
    for case in cases:
        kind = case['category']
        if kind in seen:
            continue
        seen.add(kind)
        qa = case['metadata']['qa']
        if kind.endswith(':multiple-choice'):
            positive = '(' + chr(97 + qa['correct_answer']) + ')'
            negative = '(' + chr(97 + 1 - qa['correct_answer']) + ')'
        elif kind.endswith(':list'):
            positive = ', '.join(qa['correct_answer'])
            negative = ', '.join(qa['wrong_answer']) or 'Nobody'
        else:
            positive = qa['correct_answer']
            negative = 'no' if positive == 'yes' else 'yes'
        assert score(case, positive)['correct'], (kind, positive)
        assert not score(case, negative)['correct'], (kind, negative)
        assert not score(case, '')['correct'] or not qa['correct_answer']
    return {'cases': len(cases), 'categories': sorted(seen)}


if __name__ == '__main__':
    print(json.dumps(validate(), indent=2))
