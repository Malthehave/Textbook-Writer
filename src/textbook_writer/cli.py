"""Command-line interface for local book artifacts; never calls a model."""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
from pathlib import Path

from . import publishing, workflow


def read(path: Path) -> dict:
    return json.loads(path.read_text(encoding='utf-8'))


def write(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix('.tmp')
    temp.write_text(json.dumps(value, indent=2) + '\n', encoding='utf-8')
    temp.replace(path)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build(book: Path) -> dict:
    before = workflow.status(book)
    digest = before['hashes'].get('build')
    if not digest:
        raise ValueError(f"Build blocked at {before['next_action']}: {before['errors']}")
    report = publishing.build_pdf(book, read(book / 'plan.json'), read(book / 'research.json'),
                                  read(book / 'verification/answers.json'))
    after = workflow.status(book)
    if after['hashes'].get('build') != digest:
        raise ValueError('Inputs changed during compilation; rebuild the reviewed revision')
    report.update(input_hash=digest, pdf_path='build/book.pdf', pdf_sha256=sha(book / 'build/book.pdf'))
    if read(book / 'plan.json')['solution_mode'] == 'separate':
        report.update(solutions_pdf_path='build/book-solutions.pdf',
                      solutions_pdf_sha256=sha(book / 'build/book-solutions.pdf'))
    write(book / 'build/report.json', report)
    return report


def preview(book: Path) -> dict:
    report = read(book / 'build/report.json')
    state = workflow.status(book)
    if report.get('input_hash') != state['hashes'].get('build'):
        raise ValueError('Inputs changed; rebuild before previewing')
    pages = []
    for key, hash_key, folder in [('pdf_path', 'pdf_sha256', 'main'),
                                  ('solutions_pdf_path', 'solutions_pdf_sha256', 'solutions')]:
        if key in report:
            pdf = publishing.contained(book, report[key])
            if sha(pdf) != report[hash_key]:
                raise ValueError('PDF changed after compilation; rebuild')
            paths = publishing.preview_pdf(pdf, publishing.contained(book, f'build/previews/{folder}'))
            pages.extend(str(Path(path).relative_to(book)) for path in paths)
    report['previews'] = pages
    write(book / 'build/report.json', report)
    return workflow.status(book)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    commands.add_parser('doctor', help='Check local publishing dependencies')
    for name in ('init', 'status', 'validate', 'build', 'preview', 'render-figure',
                 'verification-packet', 'record-review'):
        sub = commands.add_parser(name)
        sub.add_argument('--book', type=Path, required=True)
        if name == 'render-figure':
            sub.add_argument('--id', required=True, help='Figure ID declared in plan.json')
        if name == 'verification-packet':
            sub.add_argument('--destination', type=Path, required=True)
        if name == 'record-review':
            sub.add_argument('--stage', choices=('reader', 'comparison', 'publication'), required=True)
            sub.add_argument('--review', type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == 'doctor':
            from playwright.sync_api import sync_playwright
            with sync_playwright() as pw:
                # A round-trip completes driver initialization before shutting it down.
                request = pw.request.new_context()
                request.dispose()
                chromium = Path(pw.chromium.executable_path).is_file()
            result = {'typst': shutil.which('typst'), 'pdftoppm': shutil.which('pdftoppm'),
                      'chromium_installed': chromium, 'model_calls': False}
            print(json.dumps(result, indent=2))
            return 0 if all(result[k] for k in ('typst', 'pdftoppm', 'chromium_installed')) else 1
        book = args.book.resolve()
        if args.command == 'init':
            result = {'book': str(workflow.init_book(book.parent, book.name))}
        elif args.command in ('status', 'validate'):
            result = workflow.status(book)
        elif args.command == 'build':
            result = build(book)
        elif args.command == 'preview':
            result = preview(book)
        elif args.command == 'record-review':
            result = workflow.record_review(book, args.stage, args.review)
        elif args.command == 'verification-packet':
            result = workflow.verification_packet(book, args.destination)
        else:
            figure = next((f for f in read(book / 'plan.json').get('figures', []) if f['id'] == args.id), None)
            if figure is None:
                raise ValueError('Unknown figure ID')
            publishing.render_figure(publishing.contained(book, figure['html']),
                                     publishing.contained(book, figure['png']))
            result = {'figure': args.id, 'png': figure['png']}
        print(json.dumps(result, indent=2))
        if args.command == 'build' and not result['quality_passed']:
            return 1
        if args.command == 'validate' and not result['ready']:
            return 1
        return 0
    except (ValueError, OSError, KeyError, TypeError, RuntimeError, subprocess.SubprocessError) as exc:
        detail = getattr(exc, 'stderr', None) or str(exc)
        print(json.dumps({'error': str(detail)}))
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
