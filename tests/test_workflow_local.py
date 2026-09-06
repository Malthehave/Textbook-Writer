import hashlib
import json
from pathlib import Path

import pytest

from textbook_writer.workflow import DIMENSIONS, init_book, record_review, status, verification_packet


def write(book, name, value):
    if name == 'verification/answers.json':
        value.setdefault('questions_sha256', json.loads((book / 'verification/packet.json').read_text())['questions_sha256'])
    path = book / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value))
    return path


@pytest.fixture
def book(tmp_path):
    book = init_book(tmp_path / 'books', 'pilot')
    write(book, 'brief.json', dict(audience='Beginner', starting_point='Arithmetic', learning_goal='Understand bits', target_pages=5))
    write(book, 'research.json', {'sources': [{'id': 's1', 'url': 'https://example.org/source', 'title': 'Source'}], 'claims': [{'id': 'c1', 'text': 'A supported claim', 'source_refs': ['s1']}]})
    write(book, 'plan.json', {'title': 'Bits', 'target_pages': 5, 'chapters': [{'id': 'one', 'title': 'Bits', 'path': 'chapters/one.md'}], 'figures': [], 'solution_mode': 'concise'})
    (book / 'chapters/one.md').write_text('An explanation of labelled binary places.')
    write(book, 'exercises.json', {'exercises': [{'id': 'e1', 'question': 'What is 1 + 1?', 'answer': 'DO NOT EXPORT'}], 'draft_answers': [{'id': 'e1', 'answer': 'SECRET'}]})
    verification_packet(book, tmp_path / 'initial-packet')
    return book


def approve(book, stage, **extra):
    current = status(book)
    review = {'decision': 'approve', 'input_hash': current['hashes'][stage], **extra}
    path = write(book, 'candidate.json', review)
    return record_review(book, stage, path)


def test_lifecycle_and_freshness(book):
    assert status(book)['next_action'] == 'reader'
    assert approve(book, 'reader', scores={d: 4 for d in DIMENSIONS})['next_action'] == 'answers'
    write(book, 'verification/answers.json', {'answers': [{'id': 'e1', 'answer': '2', 'reasoning': 'Adding one and one gives two.'}]})
    assert approve(book, 'comparison')['next_action'] == 'build'
    pdf = book / 'build/book.pdf'
    pdf.write_bytes(b'%PDF-fixture')
    previews = []
    for n in range(1, 6):
        name = f'build/page-{n}.png'
        (book / name).write_bytes(b'preview')
        previews.append(name)
    write(book, 'build/report.json', {'input_hash': status(book)['hashes']['build'], 'pdf_sha256': hashlib.sha256(pdf.read_bytes()).hexdigest(), 'page_count': 5, 'quality_passed': True, 'previews': previews})
    assert status(book)['next_action'] == 'publication'
    assert approve(book, 'publication', inspected_pages=list(range(1, 6)))['ready']
    (book / previews[0]).write_bytes(b'changed preview')
    assert status(book)['next_action'] == 'publication'
    assert 'stale' in status(book)['errors'][0]
    (book / 'chapters/one.md').write_text('A revised explanation.')
    assert status(book)['next_action'] == 'reader'


def test_packet_omits_answers_and_requires_new_external_directory(book, tmp_path):
    destination = tmp_path / 'solver'
    result = verification_packet(book, destination)
    assert result['exercise_count'] == 1
    assert json.loads((destination / 'questions.json').read_text()) == {'exercises': [{'id': 'e1', 'question': 'What is 1 + 1?'}]}
    with pytest.raises(FileExistsError):
        verification_packet(book, destination)
    with pytest.raises(ValueError):
        verification_packet(book, book / 'solver')


def test_review_cannot_stamp_stale_input(book):
    old_hash = status(book)['hashes']['reader']
    (book / 'chapters/one.md').write_text('Changed')
    path = write(book, 'candidate.json', {'input_hash': old_hash, 'decision': 'approve', 'scores': {d: 5 for d in DIMENSIONS}})
    with pytest.raises(ValueError, match='input_hash'):
        record_review(book, 'reader', path)
    assert not (book / 'reviews/reader.json').exists()


def test_escape_path_is_rejected(book, tmp_path):
    plan = json.loads((book / 'plan.json').read_text())
    plan['chapters'][0]['path'] = '../../outside.md'
    write(book, 'plan.json', plan)
    assert status(book)['next_action'] == 'manuscript'
    assert 'escapes' in status(book)['errors'][0]
    with pytest.raises(ValueError):
        init_book(tmp_path, '../escape')


def test_missing_source_and_missing_answer_rejected(book):
    research = json.loads((book / 'research.json').read_text())
    research['claims'][0]['source_refs'] = ['absent']
    write(book, 'research.json', research)
    assert status(book)['next_action'] == 'research'
    research['claims'][0]['source_refs'] = ['s1']
    write(book, 'research.json', research)
    approve(book, 'reader', scores={d: 4 for d in DIMENSIONS})
    write(book, 'verification/answers.json', {'answers': []})
    assert status(book)['next_action'] == 'answers'
    assert 'match' in status(book)['errors'][0]


@pytest.mark.parametrize('name,key,bad', [
    ('research.json', 'sources', 'text'),
    ('research.json', 'claims', [None]),
    ('plan.json', 'chapters', {}),
    ('plan.json', 'figures', [1]),
    ('exercises.json', 'exercises', 'text'),
])
def test_malformed_containers_report_errors(book, name, key, bad):
    artifact = json.loads((book / name).read_text())
    artifact[key] = bad
    write(book, name, artifact)
    assert status(book)['errors']


def test_manuscript_references_and_figures(book):
    chapter = book / 'chapters/one.md'
    chapter.write_text('Supported [@s1] and missing [@absent].')
    assert 'Unknown manuscript' in status(book)['errors'][0]
    chapter.write_text('Supported [@s1].\n![Example](figures/example.png)')
    assert status(book)['next_action'] == 'figures'
    plan = json.loads((book / 'plan.json').read_text())
    plan['figures'] = [{'id': 'fig1', 'html': 'figures/example.html', 'png': 'figures/example.png', 'caption': 'Example', 'alt': 'Example'}]
    write(book, 'plan.json', plan)
    (book / 'figures/example.html').write_text('<p>Example</p>')
    (book / 'figures/example.png').write_bytes(b'PNG fixture')
    assert status(book)['next_action'] == 'reader'
    chapter.write_text('Supported [@s1].')
    assert status(book)['next_action'] == 'figures'


def test_answers_bind_to_exported_questions(book, tmp_path):
    approve(book, 'reader', scores={d: 4 for d in DIMENSIONS})
    write(book, 'verification/answers.json', {'answers': [{'id': 'e1', 'answer': '2', 'reasoning': 'One plus one.'}]})
    assert status(book)['next_action'] == 'comparison'
    questions = json.loads((book / 'exercises.json').read_text())
    questions['exercises'][0]['question'] = 'What is 2 + 2?'
    write(book, 'exercises.json', questions)
    approve(book, 'reader', scores={d: 4 for d in DIMENSIONS})
    assert status(book)['next_action'] == 'answers'
    assert 'stale' in status(book)['errors'][0]
    verification_packet(book, tmp_path / 'new-packet')
    assert status(book)['next_action'] == 'answers'
    assert 'stale' in status(book)['errors'][0]
    write(book, 'verification/answers.json', {'answers': [{'id': 'e1', 'answer': '4', 'reasoning': 'Two plus two.'}]})
    assert status(book)['next_action'] == 'comparison'
