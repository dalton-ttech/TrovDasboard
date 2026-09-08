"""Refresh, validate, publish, and verify the public Trov Dashboard snapshot."""
from __future__ import annotations

import argparse
import contextlib
import datetime as dt
import json
import os
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import tempfile
import time
from typing import Any, Iterator
import urllib.parse
import urllib.request
import uuid


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ADS_ROOT = ROOT.parent / 'Trov_ADS'
PUBLIC = ROOT / 'public'
DIST = ROOT / 'dist'
LOCK = ROOT / '.tmp' / 'daily-publish.lock'
LIVE_ROOT = 'https://trov-work.pages.dev'
ALLOWED_STAGED = ('public/data.js', 'public/runtime.js', 'public/_headers', 'public/reports/')


class PublishError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise PublishError(message)


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding='utf-8-sig'))
    require(isinstance(value, dict), f'Expected a JSON object: {path}')
    return value


def parse_timestamp(value: Any, label: str) -> dt.datetime:
    require(isinstance(value, str) and value, f'Missing {label}')
    parsed = dt.datetime.fromisoformat(value.replace('Z', '+00:00'))
    require(parsed.tzinfo is not None, f'{label} has no timezone')
    return parsed.astimezone(dt.timezone.utc)


def nth_sunday(year: int, month: int, occurrence: int) -> dt.date:
    first = dt.date(year, month, 1)
    return first + dt.timedelta(days=(6 - first.weekday()) % 7 + 7 * (occurrence - 1))


def pacific_now(value: dt.datetime | None = None) -> dt.datetime:
    """Convert UTC to US Pacific time without requiring the Windows tzdata wheel."""
    utc_value = value or dt.datetime.now(dt.timezone.utc)
    if utc_value.tzinfo is None:
        utc_value = utc_value.replace(tzinfo=dt.timezone.utc)
    utc_value = utc_value.astimezone(dt.timezone.utc)
    start = dt.datetime.combine(nth_sunday(utc_value.year, 3, 2), dt.time(10), tzinfo=dt.timezone.utc)
    end = dt.datetime.combine(nth_sunday(utc_value.year, 11, 1), dt.time(9), tzinfo=dt.timezone.utc)
    offset = -7 if start <= utc_value < end else -8
    return utc_value.astimezone(dt.timezone(dt.timedelta(hours=offset), name='PDT' if offset == -7 else 'PST'))


def latest_complete_pacific_date(value: dt.datetime | None = None) -> dt.date:
    return pacific_now(value).date() - dt.timedelta(days=1)


def latest_sunday(value: dt.date) -> dt.date:
    return value - dt.timedelta(days=(value.weekday() - 6) % 7)


def dates_after(start: dt.date | None, end: dt.date, *, limit: int) -> list[dt.date]:
    if start is None:
        return [end]
    require(start <= end, f'Published daily date {start} is ahead of complete Pacific date {end}')
    values = [start + dt.timedelta(days=offset) for offset in range(1, (end - start).days + 1)]
    require(len(values) <= limit, f'{len(values)} missing daily reports exceed the {limit}-day automatic backfill limit')
    return values


def path_from_manifest(folder: Path, value: Any, label: str) -> Path:
    require(isinstance(value, str) and value, f'Missing {label}')
    path = Path(value).resolve()
    require(path.is_relative_to(folder.resolve()), f'{label} escapes its report directory')
    require(path.is_file() and path.stat().st_size > 0, f'Missing or empty {label}')
    return path


def png_dimensions(path: Path) -> tuple[int, int]:
    with path.open('rb') as handle:
        header = handle.read(24)
    require(header[:8] == b'\x89PNG\r\n\x1a\n' and len(header) == 24, f'Invalid PNG: {path}')
    return struct.unpack('>II', header[16:24])


def validate_report_bundle(
    ads_root: Path,
    kind: str,
    end_date: dt.date,
    *,
    now_utc: dt.datetime,
    require_render: bool = True,
) -> dict[str, Any]:
    require(kind in {'daily', 'weekly'}, f'Unsupported report kind: {kind}')
    base = (ads_root / 'audits' / 'automation' / f'meta-shopify-{kind}').resolve()
    folder = (base / end_date.isoformat()).resolve()
    require(folder.is_relative_to(base), 'Report directory escapes its expected root')
    manifest = read_json(folder / 'run-manifest.json')
    data = read_json(folder / 'data.json')
    require(manifest.get('status') == 'ready', 'Report manifest is not ready')
    require(manifest.get('writes_performed') is False, 'Report manifest is not read-only')
    require(data.get('status') == 'ready', 'Report source data is not ready')
    require(data.get('writes_performed') is False, 'Report source data is not read-only')
    expected_type = f'trov_meta_shopify_{"daily" if kind == "daily" else "weekly_overview"}'
    require(manifest.get('report_type') == expected_type, 'Unexpected report type')
    expected_start = end_date if kind == 'daily' else end_date - dt.timedelta(days=6)
    end_key = 'report_date' if kind == 'daily' else 'period_end'
    require(manifest.get(end_key) == end_date.isoformat(), 'Report end date does not match its directory')
    if kind == 'weekly':
        require(manifest.get('period_start') == expected_start.isoformat(), 'Weekly report is not seven dates')
    window = manifest.get('window') or {}
    require(window.get('since') == expected_start.isoformat() and window.get('until') == end_date.isoformat(),
            'Report source window does not match the requested dates')
    end_exclusive = parse_timestamp(window.get('shopify_end_exclusive'), 'report window end')
    generated_at = parse_timestamp(data.get('generated_at_utc'), 'report generation time')
    require(end_exclusive <= now_utc.astimezone(dt.timezone.utc), 'Report source window is still open')
    require(generated_at >= end_exclusive, 'Report was collected before its source window ended')
    ads = ((data.get('meta') or {}).get('ads') or {})
    require(set(ads) == {'A02', 'A03'}, 'Report source must contain only A02/A03')
    html = path_from_manifest(folder, manifest.get('html'), 'report HTML')
    require(html.stat().st_size >= 1024, 'Report HTML is unexpectedly small')
    if require_render:
        pdf = path_from_manifest(folder, manifest.get('pdf'), 'report PDF')
        with pdf.open('rb') as handle:
            require(handle.read(4) == b'%PDF', 'Invalid report PDF')
        pages = manifest.get('pages')
        require(isinstance(pages, list) and pages, 'Report has no rendered pages')
        for index, page in enumerate(pages):
            path_from_manifest(folder, page, f'report page {index + 1}')
        if kind == 'daily':
            preview = path_from_manifest(folder, manifest.get('mobile_long_preview'), 'daily mobile preview')
            require(manifest.get('mobile_long_layout') == 'continuous-full-height', 'Unexpected daily preview layout')
            require(manifest.get('mobile_long_css_width') == 800, 'Unexpected daily preview CSS width')
            width, height = png_dimensions(preview)
            require(width == 1200 and height > width, 'Unexpected daily preview dimensions')
        else:
            preview = path_from_manifest(folder, manifest.get('portrait_preview'), 'weekly portrait preview')
            require(manifest.get('portrait_aspect_ratio') == '3:4', 'Unexpected weekly preview ratio')
            require(manifest.get('portrait_canvas_width') == 1200 and manifest.get('portrait_canvas_height') == 1600,
                    'Unexpected weekly preview canvas')
            require(png_dimensions(preview) == (1800, 2400), 'Unexpected weekly preview dimensions')
    return {
        'kind': kind,
        'date': end_date.isoformat(),
        'generatedAt': data['generated_at_utc'],
        'html': str(html),
        'reused': True,
    }


def command_output(
    command: list[str],
    *,
    cwd: Path,
    env: dict[str, str] | None = None,
    timeout: int = 1800,
) -> str:
    merged = os.environ.copy()
    merged['PYTHONDONTWRITEBYTECODE'] = '1'
    merged['PYTHONUTF8'] = '1'
    merged['GIT_TERMINAL_PROMPT'] = '0'
    if env:
        merged.update(env)
    completed = subprocess.run(
        command,
        cwd=cwd,
        env=merged,
        capture_output=True,
        text=True,
        encoding='utf-8',
        errors='replace',
        check=False,
        timeout=timeout,
        creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0),
    )
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout or 'no diagnostic output').strip()
        visible = ' '.join(command[:2])
        raise PublishError(f'Command failed ({completed.returncode}): {visible}; {detail[-1800:]}')
    return completed.stdout.strip()


def last_json_line(output: str) -> dict[str, Any]:
    lines = [line for line in output.splitlines() if line.strip()]
    require(lines, 'Command returned no JSON result')
    value = json.loads(lines[-1])
    require(isinstance(value, dict), 'Command result is not a JSON object')
    return value


def run_report(ads_root: Path, kind: str, end_date: dt.date, *, now_utc: dt.datetime) -> dict[str, Any]:
    script = 'run_trov_daily_heartbeat_report.py' if kind == 'daily' else 'run_trov_weekly_overview_report.py'
    flag = '--report-date' if kind == 'daily' else '--period-end'
    command_output([sys.executable, str(ads_root / 'scripts' / script), flag, end_date.isoformat()], cwd=ads_root)
    result = validate_report_bundle(ads_root, kind, end_date, now_utc=now_utc, require_render=True)
    result['reused'] = False
    return result


def ensure_report(ads_root: Path, kind: str, end_date: dt.date, *, now_utc: dt.datetime) -> dict[str, Any]:
    try:
        return validate_report_bundle(ads_root, kind, end_date, now_utc=now_utc, require_render=True)
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError, PublishError):
        return run_report(ads_root, kind, end_date, now_utc=now_utc)


def latest_published(catalog: dict[str, Any], kind: str) -> dt.date | None:
    values = []
    for report in catalog.get('reports', []):
        if report.get('kind') == kind and report.get('status') == 'ready':
            values.append(dt.date.fromisoformat(str(report.get('until'))))
    return max(values) if values else None


def run_dashboard_sources(ads_root: Path) -> dict[str, Any]:
    env = {'TROV_ADS_ROOT': str(ads_root)}
    results = {}
    for name in ('shopify_logistics.py', 'ads_overview.py', 'report_catalog.py'):
        payload = last_json_line(command_output([sys.executable, str(ROOT / 'scripts' / name)], cwd=ROOT, env=env))
        require(payload.get('status') == 'ready', f'{name} did not return ready')
        if 'writesPerformed' in payload:
            require(payload.get('writesPerformed') is False, f'{name} did not remain read-only')
        if 'writes_performed' in payload:
            require(payload.get('writes_performed') is False, f'{name} did not remain read-only')
        results[name] = payload
    export = last_json_line(command_output(
        [sys.executable, str(ROOT / 'scripts' / 'export_static.py'), '--ads-root', str(ads_root), '--output', str(DIST)],
        cwd=ROOT,
        env=env,
    ))
    require(export.get('status') == 'ready', 'Static export did not return ready')
    results['export_static.py'] = export
    return results


def copy_export_to_public() -> None:
    require(DIST.is_dir() and (DIST / '.trov-static-export.json').is_file(), 'Managed static export is missing')
    stage = Path(tempfile.mkdtemp(prefix='public-publish-', dir=ROOT / '.tmp')).resolve()
    backup = ROOT / '.tmp' / f'public-reports-backup-{uuid.uuid4().hex}'
    try:
        for name in ('data.js', 'runtime.js', '_headers'):
            shutil.copy2(DIST / name, stage / name)
        shutil.copytree(DIST / 'reports', stage / 'reports')
        for name in ('data.js', 'runtime.js', '_headers'):
            os.replace(stage / name, PUBLIC / name)
        reports = (PUBLIC / 'reports').resolve()
        require(reports.is_relative_to(PUBLIC.resolve()), 'Public report directory escaped the workspace')
        if reports.exists():
            reports.rename(backup)
        try:
            (stage / 'reports').rename(reports)
        except OSError:
            if backup.exists():
                backup.rename(reports)
            raise
    finally:
        for disposable in (stage, backup):
            if disposable.exists():
                require(disposable.resolve().is_relative_to((ROOT / '.tmp').resolve()), 'Cleanup path escaped .tmp')
                shutil.rmtree(disposable)


def git(args: list[str], *, check: bool = True) -> subprocess.CompletedProcess[str]:
    merged = os.environ.copy()
    merged['GIT_TERMINAL_PROMPT'] = '0'
    result = subprocess.run(
        ['git', *args],
        cwd=ROOT,
        env=merged,
        capture_output=True,
        text=True,
        check=False,
        timeout=300,
        creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0),
    )
    if check and result.returncode != 0:
        detail = (result.stderr or result.stdout or 'no diagnostic output').strip()
        raise PublishError(f'Git failed: {args[0]}; {detail[-1200:]}')
    return result


def require_clean_tracked_tree() -> None:
    require(git(['diff', '--quiet'], check=False).returncode == 0, 'Tracked working-tree changes exist')
    require(git(['diff', '--cached', '--quiet'], check=False).returncode == 0, 'Staged changes exist')


def prepare_git() -> None:
    require_clean_tracked_tree()
    git(['pull', '--ff-only', 'origin', 'main'])
    require_clean_tracked_tree()


def commit_and_push(target: dt.date) -> dict[str, Any]:
    git(['add', '--', 'public/data.js', 'public/runtime.js', 'public/_headers', 'public/reports'])
    names = [line.replace('\\', '/') for line in git(['diff', '--cached', '--name-only']).stdout.splitlines() if line]
    unexpected = [name for name in names if not any(name == allowed or name.startswith(allowed) for allowed in ALLOWED_STAGED)]
    require(not unexpected, 'Unexpected staged files: ' + ', '.join(unexpected))
    committed = bool(names)
    if committed:
        git(['commit', '-m', f'Daily dashboard snapshot {target.isoformat()}'])
    git(['-c', 'credential.username=dalton-ttech', '-c', 'credential.interactive=never',
         'push', 'origin', 'HEAD:main'])
    sha = git(['rev-parse', 'HEAD']).stdout.strip()
    return {'committed': committed, 'commit': sha, 'files': names}


def parse_js_assignment(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding='utf-8-sig').strip()
    prefix = 'window.TROV_RUNTIME = '
    require(text.startswith(prefix) and text.endswith(';'), f'Invalid runtime assignment: {path}')
    return json.loads(text[len(prefix):-1])


def fetch_text(url: str) -> str:
    request = urllib.request.Request(url, headers={'User-Agent': 'Trov-Dashboard-Publisher/1.0'})
    with urllib.request.urlopen(request, timeout=30) as response:
        require(200 <= response.status < 300, f'HTTP {response.status}: {url}')
        return response.read().decode('utf-8-sig')


def verify_live(*, daily_target: dt.date, weekly_target: dt.date, wait_seconds: int = 240) -> dict[str, Any]:
    local = parse_js_assignment(PUBLIC / 'runtime.js')
    deadline = time.monotonic() + wait_seconds
    last_error = 'deployment did not become visible'
    while True:
        try:
            query = urllib.parse.urlencode({'published': int(time.time())})
            text = fetch_text(f'{LIVE_ROOT}/runtime.js?{query}').strip()
            prefix = 'window.TROV_RUNTIME = '
            require(text.startswith(prefix) and text.endswith(';'), 'Live runtime.js is invalid')
            remote = json.loads(text[len(prefix):-1])
            require(remote['logistics']['syncedAt'] == local['logistics']['syncedAt'], 'Live logistics snapshot is stale')
            require(remote['adsOverview']['syncedAt'] == local['adsOverview']['syncedAt'], 'Live advertising snapshot is stale')
            require(remote['reports']['indexedAt'] == local['reports']['indexedAt'], 'Live report index is stale')
            report_ids = {item['id'] for item in remote['reports']['reports']}
            require(f'daily-{daily_target.isoformat()}' in report_ids, 'Latest daily report is absent from the live index')
            require(f'weekly-{weekly_target.isoformat()}' in report_ids, 'Latest weekly report is absent from the live index')
            fetch_text(f'{LIVE_ROOT}/reports/daily/{daily_target.isoformat()}/report.html?{query}')
            fetch_text(f'{LIVE_ROOT}/reports/weekly/{weekly_target.isoformat()}/report.html?{query}')
            return {
                'status': 'ready',
                'url': LIVE_ROOT,
                'daily': daily_target.isoformat(),
                'weekly': weekly_target.isoformat(),
                'reports': len(report_ids),
            }
        except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError, PublishError) as exc:
            last_error = str(exc)
        if time.monotonic() >= deadline:
            raise PublishError('Cloudflare verification timed out: ' + last_error)
        time.sleep(10)


@contextlib.contextmanager
def exclusive_lock(path: Path) -> Iterator[None]:
    path.parent.mkdir(parents=True, exist_ok=True)
    token = f'{os.getpid()}:{dt.datetime.now(dt.timezone.utc).isoformat()}'
    if path.exists() and time.time() - path.stat().st_mtime > 6 * 3600:
        path.unlink()
    try:
        descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError as exc:
        raise PublishError('Another dashboard publication is already running') from exc
    with os.fdopen(descriptor, 'w', encoding='utf-8') as handle:
        handle.write(token)
    try:
        yield
    finally:
        try:
            if path.read_text(encoding='utf-8') == token:
                path.unlink()
        except OSError:
            pass


def publish(
    ads_root: Path,
    *,
    now_utc: dt.datetime,
    max_backfill_days: int,
    live_wait_seconds: int,
) -> dict[str, Any]:
    ads_root = ads_root.resolve()
    require((ads_root / 'scripts' / 'run_trov_daily_heartbeat_report.py').is_file(), 'Trov_ADS daily entry is missing')
    require((ads_root / 'scripts' / 'run_trov_weekly_overview_report.py').is_file(), 'Trov_ADS weekly entry is missing')
    prepare_git()
    target = latest_complete_pacific_date(now_utc)
    catalog_path = ROOT / 'data' / 'reports.json'
    prior_catalog = read_json(catalog_path) if catalog_path.is_file() else {'reports': []}
    missing_daily = dates_after(latest_published(prior_catalog, 'daily'), target, limit=max_backfill_days)
    daily_results = [ensure_report(ads_root, 'daily', value, now_utc=now_utc) for value in missing_daily]
    if not daily_results:
        daily_results = [ensure_report(ads_root, 'daily', target, now_utc=now_utc)]
    weekly_target = latest_sunday(target)
    weekly_result = ensure_report(ads_root, 'weekly', weekly_target, now_utc=now_utc)
    sources = run_dashboard_sources(ads_root)
    copy_export_to_public()
    publication = commit_and_push(target)
    live = verify_live(daily_target=target, weekly_target=weekly_target, wait_seconds=live_wait_seconds)
    return {
        'status': 'ready',
        'timezone': 'America/Los_Angeles',
        'completePacificDate': target.isoformat(),
        'pacificMode': pacific_now(now_utc).tzname(),
        'dailyReports': daily_results,
        'weeklyReport': weekly_result,
        'sourceResults': sources,
        'publication': publication,
        'deployment': live,
        'sourceWritesPerformed': False,
        'gitWritePerformed': publication['committed'],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--ads-root', type=Path, default=Path(os.environ.get('TROV_ADS_ROOT', DEFAULT_ADS_ROOT)))
    parser.add_argument('--max-backfill-days', type=int, default=31)
    parser.add_argument('--live-wait-seconds', type=int, default=240)
    args = parser.parse_args()
    require(args.max_backfill_days >= 1, 'Backfill limit must be positive')
    require(args.live_wait_seconds >= 0, 'Live wait must not be negative')
    with exclusive_lock(LOCK):
        result = publish(
            args.ads_root,
            now_utc=dt.datetime.now(dt.timezone.utc),
            max_backfill_days=args.max_backfill_days,
            live_wait_seconds=args.live_wait_seconds,
        )
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (
        OSError,
        ValueError,
        KeyError,
        TypeError,
        json.JSONDecodeError,
        subprocess.TimeoutExpired,
        PublishError,
    ) as exc:
        print(json.dumps({
            'status': 'error',
            'stage': 'dashboard_daily_publish',
            'errorType': type(exc).__name__,
            'message': str(exc),
            'sourceWritesPerformed': False,
            'publicationState': 'inspect_git',
        }, ensure_ascii=False), file=sys.stderr)
        raise SystemExit(1)
