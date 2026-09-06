"""Local, deterministic book gates. This module never calls a model or an API."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

DIMENSIONS = ('narrative_coherence', 'explanatory_depth', 'paragraph_flow', 'sentence_rhythm', 'concept_scaffolding', 'example_continuity', 'practice_progression', 'voice_consistency')


def _read(path: Path) -> dict:
    data = json.loads(path.read_text())
    if not isinstance(data, dict):
        raise ValueError(f'{path.name} must contain an object')
    return data


def _path(book: Path, name: str) -> Path:
    if not isinstance(name, str) or not name or Path(name).is_absolute():
        raise ValueError('Artifact paths must be relative')
    path = (book / name).resolve()
    if not path.is_relative_to(book.resolve()):
        raise ValueError(f'Path escapes book: {name}')
    return path


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _digest(book: Path, names: list[str]) -> str:
    entries = [(name, _sha(_path(book, name)) if _path(book, name).is_file() else None) for name in sorted(set(names))]
    return hashlib.sha256(json.dumps(entries, sort_keys=True).encode()).hexdigest()


def init_book(root: Path, book_id: str) -> Path:
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]*', book_id):
        raise ValueError('Use a simple book ID containing letters, numbers, hyphens or underscores')
    book = _path(root, book_id)
    book.mkdir(parents=True, exist_ok=False)
    for folder in ('chapters', 'figures', 'verification', 'reviews', 'build'):
        (book / folder).mkdir()
    return book


def _nonempty(data: dict, fields: tuple[str, ...]) -> None:
    for field in fields:
        if not isinstance(data.get(field), str) or not data[field].strip():
            raise ValueError(f'{field} must be nonempty text')


def _unique(items: list, label: str) -> set[str]:
    if not isinstance(items, list) or any(not isinstance(x, dict) for x in items):
        raise ValueError(f'{label} must be a list of objects')
    ids = [x.get('id') for x in items]
    if any(not isinstance(x, str) or not x for x in ids) or len(set(ids)) != len(ids):
        raise ValueError(f'{label} IDs must be unique nonempty strings')
    return set(ids)


def _review(book: Path, stage: str, digest: str, page_count: int = 0) -> None:
    review = _read(_path(book, f'reviews/{stage}.json'))
    if review.get('input_hash') != digest:
        raise ValueError(f'{stage} review is stale')
    if stage == 'reader':
        scores = review.get('scores', {})
        if not isinstance(scores, dict) or any(type(scores.get(d)) not in (int, float) or not 4 <= scores[d] <= 5 for d in DIMENSIONS):
            raise ValueError('Reader review requires all eight dimensions scored at least 4/5')
    if review.get('decision') != 'approve':
        raise ValueError(f'{stage} review must approve')
    if stage == 'publication' and review.get('inspected_pages') != list(range(1, page_count + 1)):
        raise ValueError('Publication review must inspect every page in order')


def status(book: Path) -> dict:
    book = Path(book)
    names = ['brief.json', 'research.json', 'plan.json', 'exercises.json']
    hashes: dict[str, str] = {}
    stage = 'brief'
    try:
        brief = _read(_path(book, 'brief.json'))
        _nonempty(brief, ('audience', 'starting_point', 'learning_goal'))
        if type(brief.get('target_pages')) is not int or brief['target_pages'] < 1:
            raise ValueError('target_pages must be a positive integer')
        stage = 'research'
        research = _read(_path(book, 'research.json'))
        sources = research['sources']
        if not sources:
            raise ValueError('Research needs sources')
        ids = _unique(sources, 'Source')
        from urllib.parse import urlparse
        for source in sources:
            _nonempty(source, ('title', 'url'))
            parsed = urlparse(source['url'])
            if parsed.scheme != 'https' or not parsed.netloc:
                raise ValueError('Sources require HTTPS URLs')
        if not research['claims']:
            raise ValueError('Research needs claims')
        _unique(research['claims'], 'Claim')
        for claim in research['claims']:
            _nonempty(claim, ('text',))
            refs = claim.get('source_refs')
            if not isinstance(refs, list) or not refs or any(not isinstance(ref, str) for ref in refs) or not set(refs) <= ids:
                raise ValueError('Every claim needs existing source references')
        stage = 'manuscript'
        plan = _read(_path(book, 'plan.json'))
        _nonempty(plan, ('title',))
        if plan.get('target_pages') != brief['target_pages']:
            raise ValueError('Plan target_pages must match brief')
        if plan.get('solution_mode') not in ('concise', 'separate'):
            raise ValueError('solution_mode must be concise or separate')
        if not plan['chapters']:
            raise ValueError('Plan needs chapters')
        _unique(plan['chapters'], 'Chapter')
        image_paths = set()
        for chapter in plan['chapters']:
            _nonempty(chapter, ('title', 'path'))
            path = _path(book, chapter['path'])
            if path.suffix != '.md' or not path.read_text().strip():
                raise ValueError('Chapters must be nonempty Markdown files')
            text = path.read_text()
            unknown_refs = set(re.findall(r'\[@([^\]]+)\]', text)) - ids
            if unknown_refs:
                raise ValueError(f'Unknown manuscript source references: {sorted(unknown_refs)}')
            for image_path in re.findall(r'!\[[^\]]*\]\(([^)]+)\)', text):
                _path(book, image_path)
                image_paths.add(image_path)
            names.append(chapter['path'])
        exercises = _read(_path(book, 'exercises.json'))['exercises']
        if not exercises:
            raise ValueError('Provide at least one exercise')
        exercise_ids = _unique(exercises, 'Exercise')
        for exercise in exercises:
            _nonempty(exercise, ('question',))
        stage = 'figures'
        _unique(plan.get('figures', []), 'Figure')
        for figure in plan.get('figures', []):
            _nonempty(figure, ('html', 'png', 'caption', 'alt'))
            for field, suffix in (('html', '.html'), ('png', '.png')):
                path = _path(book, figure[field])
                if path.suffix != suffix or not path.is_file() or not path.stat().st_size:
                    raise ValueError(f'Missing {field} figure: {figure[field]}')
                names.append(figure[field])
        declared_images = {figure['png'] for figure in plan.get('figures', [])}
        if image_paths != declared_images:
            raise ValueError('Every Markdown image must be declared in plan.figures and every declared figure must be used')
        hashes['reader'] = _digest(book, names)
        stage = 'reader'
        _review(book, stage, hashes[stage])
        stage = 'answers'
        answer_artifact = _read(_path(book, 'verification/answers.json'))
        expected_questions = hashlib.sha256(_question_bytes(exercises)).hexdigest()
        packet = _read(_path(book, 'verification/packet.json'))
        if packet.get('questions_sha256') != expected_questions or answer_artifact.get('questions_sha256') != expected_questions:
            raise ValueError('Independent answers or exported questions packet are stale; export and solve current questions')
        answers = answer_artifact['answers']
        if _unique(answers, 'Answer') != exercise_ids:
            raise ValueError('Independent answers must match all exercise IDs exactly')
        for answer in answers:
            _nonempty(answer, ('answer', 'reasoning'))
        names += ['verification/answers.json', 'verification/packet.json', 'reviews/reader.json']
        hashes['comparison'] = _digest(book, names)
        stage = 'comparison'
        _review(book, stage, hashes[stage])
        names.append('reviews/comparison.json')
        hashes['build'] = _digest(book, names)
        stage = 'build'
        report = _read(_path(book, 'build/report.json'))
        pdf_name = report.get('pdf_path', 'build/book.pdf')
        pdf = _path(book, pdf_name)
        if report.get('input_hash') != hashes['build'] or report.get('pdf_sha256') != _sha(pdf):
            raise ValueError('Build report is stale')
        pages = report.get('page_count')
        if type(pages) is not int or not 0.85 * brief['target_pages'] <= pages <= 1.15 * brief['target_pages']:
            raise ValueError('Measured page count must be within 15% of target')
        if report.get('quality_passed') is not True:
            raise ValueError('Build must pass deterministic quality checks')
        names += ['build/report.json', pdf_name]
        if plan['solution_mode'] == 'separate':
            companion = report['solutions_pdf_path']
            if report.get('solutions_pdf_sha256') != _sha(_path(book, companion)):
                raise ValueError('Companion PDF is stale')
            names.append(companion)
        previews = report.get('previews', [])
        if not isinstance(previews, list) or any(not isinstance(p, str) for p in previews) or len(previews) != pages or len(set(previews)) != pages:
            raise ValueError('Build requires a preview image for every page')
        for preview in previews:
            if not _path(book, preview).is_file():
                raise ValueError('Missing publication preview')
            names.append(preview)
        hashes['publication'] = _digest(book, names)
        stage = 'publication'
        _review(book, stage, hashes[stage], pages)
        return {'ready': True, 'next_action': 'complete', 'errors': [], 'hashes': hashes, 'input_hash': hashes['publication']}
    except (OSError, ValueError, KeyError, TypeError, AttributeError) as exc:
        return {'ready': False, 'next_action': stage, 'errors': [str(exc)], 'hashes': hashes, 'input_hash': hashes.get(stage)}


def validate_book(book: Path) -> dict:
    return status(book)


def record_review(book: Path, stage: str, review_path: Path) -> dict:
    if stage not in ('reader', 'comparison', 'publication'):
        raise ValueError('Unknown review stage')
    current = status(book)
    expected = current['hashes'].get(stage)
    review = _read(review_path)
    if not expected or review.get('input_hash') != expected:
        raise ValueError('Reviewer input_hash does not match current artifacts')
    # Validate before replacing any previous review.
    if review.get('decision') != 'approve':
        raise ValueError('Only approved reviews can pass a gate')
    if stage == 'reader':
        scores = review.get('scores', {})
        if not isinstance(scores, dict) or any(type(scores.get(d)) not in (int, float) or not 4 <= scores[d] <= 5 for d in DIMENSIONS):
            raise ValueError('Reader scores must all be at least 4/5')
    if stage == 'publication':
        count = _read(_path(book, 'build/report.json'))['page_count']
        if review.get('inspected_pages') != list(range(1, count + 1)):
            raise ValueError('Review must inspect every page')
    destination = _path(book, f'reviews/{stage}.json')
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(review, indent=2) + '\n')
    return status(book)


def _question_bytes(exercises: list) -> bytes:
    _unique(exercises, 'Exercise')
    if not exercises:
        raise ValueError('Provide at least one exercise')
    for exercise in exercises:
        _nonempty(exercise, ('question',))
    payload = {'exercises': [{'id': e['id'], 'question': e['question']} for e in exercises]}
    return (json.dumps(payload, indent=2) + '\n').encode()


def verification_packet(book: Path, destination: Path) -> dict:
    """Export questions only. Isolation of the solver's context is the caller's job."""
    book, destination = Path(book).resolve(), Path(destination).resolve()
    if destination.is_relative_to(book) or book.is_relative_to(destination):
        raise ValueError('Verification packet must be outside the book directory')
    exercises = _read(_path(book, 'exercises.json'))['exercises']
    packet_bytes = _question_bytes(exercises)
    destination.mkdir(parents=True, exist_ok=False)
    (destination / 'questions.json').write_bytes(packet_bytes)
    questions_sha256 = hashlib.sha256(packet_bytes).hexdigest()
    receipt = _path(book, 'verification/packet.json')
    receipt.parent.mkdir(parents=True, exist_ok=True)
    receipt.write_text(json.dumps({'questions_sha256': questions_sha256}, indent=2) + '\n')
    return {'path': str(destination), 'exercise_count': len(exercises), 'questions_sha256': questions_sha256}
