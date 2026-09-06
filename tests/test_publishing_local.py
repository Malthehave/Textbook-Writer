"""Publishing boundary checks and real local compiler smoke coverage."""
import json
import shutil
from pathlib import Path

import pytest
from pypdf import PdfReader

from textbook_writer.publishing import build_pdf, contained, preview_pdf


@pytest.fixture
def inputs(tmp_path):
    (tmp_path / 'chapter.md').write_text('A number has a ones place. For example, three is 011. [@primary]\n')
    (tmp_path / 'exercises.json').write_text(json.dumps({'exercises': [{'id': 'one', 'question': 'What is 1 + 1?'}]}))
    return tmp_path, {'title': 'A Small Book', 'target_pages': 1,
                      'chapters': [{'id': 'intro', 'title': 'Numbers', 'path': 'chapter.md'}],
                      'figures': [], 'solution_mode': 'concise'}, {'sources': [
                          {'id': 'primary', 'title': 'Number reference', 'url': 'https://example.com/numbers'}]}, {
                              'answers': [{'id': 'one', 'answer': '2', 'reasoning': 'One and one make two.'}]}


def test_containment_rejects_absolute_traversal_and_symlinks(tmp_path):
    for path in ('../secret', '/etc/passwd'):
        with pytest.raises(ValueError):
            contained(tmp_path, path)
    (tmp_path / 'outside').symlink_to(tmp_path.parent, target_is_directory=True)
    with pytest.raises(ValueError):
        contained(tmp_path, 'outside/file')


def test_missing_blind_answer_prevents_compile(inputs):
    book, manifest, research, _ = inputs
    with pytest.raises(ValueError, match='exactly match'):
        build_pdf(book, manifest, research, {'answers': []})
    assert not (book / 'build/book.pdf').exists()


def test_unknown_source_prevents_compile(inputs):
    book, manifest, _, answers = inputs
    with pytest.raises(ValueError, match='Unknown source'):
        build_pdf(book, manifest, {'sources': []}, answers)


def test_external_figure_prevents_compile(inputs):
    book, manifest, research, answers = inputs
    (book / 'chapter.md').write_text('![bad](https://example.com/picture.png)')
    with pytest.raises(ValueError, match='Unknown or missing figure'):
        build_pdf(book, manifest, research, answers)


@pytest.mark.skipif(not shutil.which('typst'), reason='Typst is not installed')
def test_real_pdf_and_companion(inputs):
    book, manifest, research, answers = inputs
    report = build_pdf(*inputs)
    assert report['quality_passed']
    text = '\n'.join(p.extract_text() for p in PdfReader(book / 'build/book.pdf').pages)
    assert 'One and one make two' in text
    assert 'Number reference' in text
    manifest.update(solution_mode='separate', target_pages=2)
    report = build_pdf(book, manifest, research, answers)
    assert report['quality_passed']
    text = '\n'.join(p.extract_text() for p in PdfReader(book / 'build/book.pdf').pages)
    assert 'One and one make two' not in text
    companion = '\n'.join(p.extract_text() for p in PdfReader(book / 'build/book-solutions.pdf').pages)
    assert 'One and one make two' in companion
    if shutil.which('pdftoppm'):
        assert len(preview_pdf(book / 'build/book.pdf', book / 'build/preview')) == 1


@pytest.mark.skipif(not shutil.which('typst'), reason='Typst is not installed')
def test_measured_fit_and_placeholder_gate(inputs):
    book, manifest, research, answers = inputs
    manifest['target_pages'] = 5
    assert not build_pdf(*inputs)['quality_passed']
    manifest['target_pages'] = 1
    (book / 'chapter.md').write_text('TODO: explain this number.')
    report = build_pdf(*inputs)
    assert report['placeholders'] == ['TODO']
    assert not report['quality_passed']


@pytest.mark.skipif(not shutil.which('typst'), reason='Typst is not installed')
@pytest.mark.parametrize('pages,passed', [(17, True), (23, True), (16, False), (24, False)])
def test_page_tolerance_is_inclusive(inputs, monkeypatch, pages, passed):
    import textbook_writer.publishing as publishing
    inputs[1]['target_pages'] = 20
    monkeypatch.setattr(publishing, '_inspection', lambda _: {'page_count': pages, 'blank_pages': []})
    assert build_pdf(*inputs)['quality_passed'] is passed


@pytest.mark.skipif(not shutil.which('typst'), reason='Typst is not installed')
def test_real_math_and_source_title_conversion(inputs):
    book, manifest, research, answers = inputs
    (book / 'chapter.md').write_text('The result is $y=7$.\n\n$$y = 2 \\times 3 + 1$$\n\nA source [@primary].')
    research['sources'][0]['title'] = 'Numbers & **notation** [explained]'
    report = build_pdf(*inputs)
    assert report['quality_passed']
    source = (book / 'build/book.typ').read_text()
    assert source.count('#import "@preview/mitex:0.2.6"') == 1
    assert '1. #link' in source
    assert '2. #link' not in source
    text = '\n'.join(p.extract_text() for p in PdfReader(book / 'build/book.pdf').pages)
    assert 'notation' in text


def _chromium_installed():
    from playwright.sync_api import sync_playwright
    with sync_playwright() as playwright:
        return Path(playwright.chromium.executable_path).is_file()


@pytest.mark.skipif(not _chromium_installed(), reason='Playwright Chromium is not installed')
def test_self_contained_html_figure_and_pdf(inputs):
    from textbook_writer.publishing import render_figure
    book, manifest, research, answers = inputs
    (book / 'figures').mkdir()
    html = book / 'figures/bits.html'
    png = book / 'figures/bits.png'
    html.write_text('<html><body><div id="diagram" style="width:500px;height:160px;background:white;font:24px sans-serif">'
                    '<p>Place values: 4 | 2 | 1</p><p>Three: 0 | 1 | 1</p></div></body></html>')
    render_figure(html, png)
    assert png.read_bytes().startswith(b'\x89PNG\r\n\x1a\n')
    manifest['figures'] = [{'id': 'bits', 'html': 'figures/bits.html', 'png': 'figures/bits.png',
                            'caption': 'Labelled binary places', 'alt': 'Four, two and one label the columns.'}]
    (book / 'chapter.md').write_text('Three is shown below.\n\n![Binary places](figures/bits.png)\n')
    if shutil.which('typst'):
        build_pdf(*inputs)
        assert any(len(page.images) for page in PdfReader(book / 'build/book.pdf').pages)


@pytest.mark.skipif(not shutil.which('typst'), reason='Typst is not installed')
def test_title_placeholder_fails_quality(inputs):
    inputs[1]['title'] = 'TODO Book'
    report = build_pdf(*inputs)
    assert report['placeholders'] == ['TODO']
    assert not report['quality_passed']
