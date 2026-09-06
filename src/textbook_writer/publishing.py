"""Local-only Markdown → Typst publishing and HTML diagram rendering."""
from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path
from urllib.parse import urlparse

from md2typst import convert
from pypdf import PdfReader


def contained(root: Path, relative: str) -> Path:
    """Resolve a book path, rejecting absolute paths, traversal and escaping symlinks."""
    root = root.resolve()
    path = Path(relative)
    if path.is_absolute() or '..' in path.parts:
        raise ValueError(f"Path must be relative and contained: {relative}")
    resolved = (root / path).resolve()
    if not resolved.is_relative_to(root):
        raise ValueError(f"Path escapes book: {relative}")
    return resolved


def render_figure(html_path: Path, png_path: Path) -> None:
    """Render exactly one #diagram; disallow network and local resource requests."""
    from playwright.sync_api import sync_playwright

    html = html_path.read_text(encoding='utf-8')
    png_path.parent.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        try:
            context = browser.new_context(viewport={'width': 1000, 'height': 1400}, device_scale_factor=2,
                                          service_workers='block')
            context.route('**/*', lambda route: route.abort())
            page = context.new_page()
            page.set_content(html, wait_until='load')
            diagram = page.locator('#diagram')
            if diagram.count() != 1:
                raise ValueError('Figure HTML requires exactly one #diagram element')
            page.evaluate('document.fonts.ready')
            diagram.screenshot(path=str(png_path), animations='disabled', timeout=15000)
        finally:
            browser.close()


def preview_pdf(pdf_path: Path, output_dir: Path) -> list[str]:
    if not shutil.which('pdftoppm'):
        raise RuntimeError('Install Poppler (pdftoppm) to preview PDFs')
    output_dir.mkdir(parents=True, exist_ok=True)
    for old in output_dir.glob('page-*.png'):
        old.unlink()
    subprocess.run(['pdftoppm', '-png', '-r', '110', str(pdf_path), str(output_dir / 'page')],
                   check=True, capture_output=True, timeout=180)
    return [str(p) for p in sorted(output_dir.glob('page-*.png'), key=lambda p: int(p.stem.split('-')[-1]))]


def _compile(source: str, book: Path, stem: str) -> Path:
    if not shutil.which('typst'):
        raise RuntimeError('Install Typst before building a textbook')
    typ = contained(book, f'build/{stem}.typ')
    pdf = contained(book, f'build/{stem}.pdf')
    typ.write_text(source, encoding='utf-8')
    subprocess.run(['typst', 'compile', '--root', str(book.resolve()), str(typ), str(pdf)],
                   check=True, capture_output=True, text=True, timeout=180)
    return pdf


def _inspection(pdf: Path) -> dict:
    reader = PdfReader(pdf)
    blank = []
    for index, page in enumerate(reader.pages, 1):
        # A footer alone does not constitute a page; image-only pages are legitimate.
        text = re.sub(r'\d+', '', page.extract_text() or '').strip()
        if not text and not len(page.images):
            blank.append(index)
    return {'page_count': len(reader.pages), 'blank_pages': blank}


def build_pdf(book: Path, manifest: dict, research: dict, answers: dict) -> dict:
    """Build reviewed inputs; caller owns review/provenance gates, this checks output fit."""
    book = book.resolve()
    build = contained(book, 'build')
    build.mkdir(parents=True, exist_ok=True)
    mode = manifest.get('solution_mode', 'concise')
    if mode not in ('concise', 'separate'):
        raise ValueError('Unknown solution_mode')
    target = manifest['target_pages']
    if not isinstance(target, (float, int)) or isinstance(target, bool) or target <= 0:
        raise ValueError('target_pages must be positive')
    title = manifest['title'].strip()
    if not title or '\n' in title:
        raise ValueError('A nonempty single-line title is required')
    sources = research.get('sources', [])
    source_map = {source['id']: source for source in sources}
    if len(source_map) != len(sources):
        raise ValueError('Duplicate source IDs')
    for source in sources:
        if urlparse(source['url']).scheme != 'https' or not urlparse(source['url']).netloc:
            raise ValueError('Source URLs must be HTTPS')
    figures = {figure['png']: figure for figure in manifest.get('figures', [])}
    if len(figures) != len(manifest.get('figures', [])):
        raise ValueError('Duplicate figure PNG paths')
    for figure in figures.values():
        for field in ('html', 'png'):
            if not contained(book, figure[field]).is_file():
                raise ValueError(f"Missing figure {field}: {figure[field]}")
    imports: set[str] = set()
    used_sources: list[str] = []
    used_figures: set[str] = set()
    raw_text: list[str] = [title, *[f.get('caption', '') for f in figures.values()]]

    def markdown(text: str) -> str:
        raw_text.append(text)
        def citation(match):
            key = match.group(1)
            if key not in source_map:
                raise ValueError(f'Unknown source reference: {key}')
            if key not in used_sources:
                used_sources.append(key)
            return f'[{used_sources.index(key) + 1}]'
        text = re.sub(r'\[@([\w-]+)\]', citation, text)
        # Images are handled explicitly to enforce containment and capture captions.
        blocks = []
        def picture(match):
            caption, relative = match.groups()
            if relative not in figures or not contained(book, relative).is_file():
                raise ValueError(f'Unknown or missing figure: {relative}')
            used_figures.add(relative)
            figure = figures[relative]
            marker = f'BOOKFIGURETOKEN{len(blocks)}END'
            blocks.append('#figure(image(' + json.dumps('/' + relative) + ', width: 95%, alt: ' +
                          json.dumps(figure.get('alt', caption)) + '), caption: ' +
                          json.dumps(figure.get('caption', caption)) + ')')
            return '\n\n' + marker + '\n\n'
        text = re.sub(r'!\[([^\]]*)\]\(([^)]+)\)', picture, text)
        converted = convert(text, parser='markdown-it')
        body = []
        for line in converted.splitlines():
            if line.startswith('#import '):
                imports.add(line)
            else:
                body.append(line)
        result = '\n'.join(body)
        if '#image(' in result:
            raise ValueError('Images must use registered inline Markdown figure syntax')
        for i, block in enumerate(blocks):
            result = result.replace(f'BOOKFIGURETOKEN{i}END', block)
        return result

    chapter_content = []
    for chapter in manifest['chapters']:
        path = contained(book, chapter['path'])
        raw_text.append(chapter['title'])
        chapter_content.append('#heading(level: 1, ' + json.dumps(chapter['title']) + ')\n' + markdown(path.read_text()))
    exercises_path = contained(book, 'exercises.json')
    exercises = json.loads(exercises_path.read_text())['exercises']
    solved = answers['answers']
    question_ids = [exercise['id'] for exercise in exercises]
    answer_map = {answer['id']: answer for answer in solved}
    if len(set(question_ids)) != len(question_ids) or len(answer_map) != len(solved):
        raise ValueError('Duplicate exercise or answer IDs')
    if set(question_ids) != set(answer_map):
        raise ValueError('Independently solved answers must exactly match exercises')
    questions = ['= Exercises'] if exercises else []
    solutions = ['= Answers'] if exercises else []
    for index, exercise in enumerate(exercises, 1):
        questions.append(markdown(f"### Exercise {index}\n\n{exercise['question']}"))
        answer = answer_map[exercise['id']]
        if not answer['answer'].strip() or not answer['reasoning'].strip():
            raise ValueError('Answers and reasoning cannot be empty')
        solutions.append(markdown(f"### Exercise {index}\n\n{answer['answer']}\n\n{answer['reasoning']}"))
    if set(figures) != used_figures:
        raise ValueError('Every planned figure must appear in the manuscript')
    bibliography = ['= References'] if used_sources else []
    for index, key in enumerate(used_sources, 1):
        source = source_map[key]
        bibliography.append(f'{index}. #link({json.dumps(source["url"])})[{markdown(source["title"])}]')
    preamble = '\n'.join(sorted(imports)) + '\n' + '''#set page(paper: "a5", margin: (x: 17mm, y: 18mm), numbering: "1")
#set text(size: 10pt)
#set par(justify: false, leading: 0.65em)
#set heading(numbering: none)
'''
    heading = '#text(size: 22pt, weight: "bold", ' + json.dumps(title) + ')\n\n'
    main = [preamble, heading, *chapter_content, *questions]
    if mode == 'concise':
        main += solutions
    main += bibliography
    pdf = _compile('\n\n'.join(main), book, 'book')
    documents = {'book': _inspection(pdf)}
    if mode == 'separate':
        companion = _compile('\n\n'.join([preamble, heading, *solutions, *bibliography]), book, 'book-solutions')
        documents['solutions'] = _inspection(companion)
    measured = sum(document['page_count'] for document in documents.values())
    placeholders = sorted(set(re.findall(r'\b(?:TODO|TBD|FIXME)\b|\[INSERT[^\]]*\]', '\n'.join(raw_text))))
    fit = target * .85 <= measured <= target * 1.15
    report = {'pdf': str(pdf), 'documents': documents, 'page_count': measured,
              'target_pages': target, 'page_fit': fit, 'placeholders': placeholders,
              'quality_passed': fit and not placeholders and not any(d['blank_pages'] for d in documents.values())}
    contained(book, 'build/publication-report.json').write_text(json.dumps(report, indent=2) + '\n')
    return report
