import json
from pathlib import Path

from textbook_writer.cli import main


def test_init_status_and_build_gate(tmp_path, capsys):
    book = tmp_path / 'book'
    assert main(['init', '--book', str(book)]) == 0
    assert main(['status', '--book', str(book)]) == 0
    assert 'brief' in capsys.readouterr().out
    assert main(['build', '--book', str(book)]) == 1
    assert not (book / 'build/book.pdf').exists()
    assert main(['init', '--book', str(book)]) == 1


def test_validate_unfinished_and_bad_json(tmp_path, capsys):
    book = tmp_path / 'book'
    main(['init', '--book', str(book)])
    (book / 'brief.json').write_text('{')
    assert main(['validate', '--book', str(book)]) == 1
    output = capsys.readouterr().out
    assert 'errors' in output


def test_cli_real_build_preview_and_delivery(tmp_path, capsys):
    import shutil
    import pytest
    from textbook_writer.workflow import DIMENSIONS, status

    if not shutil.which('typst') or not shutil.which('pdftoppm'):
        pytest.skip('Typst and Poppler required')
    book = tmp_path / 'book'
    main(['init', '--book', str(book)])
    def put(name, data):
        (book / name).write_text(json.dumps(data))
    put('brief.json', dict(audience='Beginner', starting_point='Arithmetic', learning_goal='Add numbers', target_pages=1))
    put('research.json', {'sources': [{'id': 's1', 'url': 'https://example.org', 'title': 'Test source'}], 'claims': [{'id': 'c1', 'text': 'Fixture claim', 'source_refs': ['s1']}]})
    put('plan.json', dict(title='Arithmetic', target_pages=1, solution_mode='concise', figures=[], chapters=[dict(id='one', title='Addition', path='chapters/one.md')]))
    (book / 'chapters/one.md').write_text('Adding one more to one gives two. [@s1]')
    put('exercises.json', {'exercises': [{'id': 'e1', 'question': 'What is one plus one?'}], 'draft_answers': [{'id': 'e1', 'answer': 'NEVER PUBLISH THIS DRAFT'}]})
    def approve(stage, **extra):
        candidate = tmp_path / 'review.json'
        candidate.write_text(json.dumps(dict(input_hash=status(book)['hashes'][stage], decision='approve', **extra)))
        assert main(['record-review', '--book', str(book), '--stage', stage, '--review', str(candidate)]) == 0
    # Test fixtures exercise the gates; these are not human/model review claims.
    approve('reader', scores={d: 4 for d in DIMENSIONS})
    assert main(['verification-packet', '--book', str(book), '--destination', str(tmp_path / 'packet')]) == 0
    receipt = json.loads((book / 'verification/packet.json').read_text())
    put('verification/answers.json', dict(questions_sha256=receipt['questions_sha256'], answers=[dict(id='e1', answer='2', reasoning='Count one, then one more.')]))
    approve('comparison')
    assert main(['build', '--book', str(book)]) == 0
    assert main(['preview', '--book', str(book)]) == 0
    assert status(book)['next_action'] == 'publication'
    approve('publication', inspected_pages=[1])
    assert main(['validate', '--book', str(book)]) == 0
    from pypdf import PdfReader
    assert 'NEVER PUBLISH' not in PdfReader(book / 'build/book.pdf').pages[0].extract_text()
    (book / 'chapters/one.md').write_text('Changed content')
    assert main(['build', '--book', str(book)]) == 1
