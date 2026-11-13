"""Read-only resume dashboard. No scene, renderer, or narration-model imports."""
from __future__ import annotations

import argparse
from datetime import datetime
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shlex
import socket
import subprocess
import time

import yaml

from .paths import lesson_dir, rel

SIDECARS = ('captions.srt', 'transcript.md', 'chapters.txt', 'sources.md')
STATES = {'planned', 'writing', 'draft', 'rendering', 'review', 'ready', 'blocked'}


def read_yaml(path: Path, optional=False):
    if optional and not path.exists():
        return {}, None
    try:
        value = yaml.safe_load(path.read_text())
        if not isinstance(value, dict):
            raise ValueError('expected a YAML mapping')
        return value, None
    except (OSError, UnicodeError, ValueError, yaml.YAMLError) as exc:
        return {}, f'{rel(path)}: {exc}'


def resolve(root: Path, value) -> Path:
    if not isinstance(value, str) or not value:
        raise ValueError('expected a nonempty path string')
    path = Path(value).expanduser()
    return path if path.is_absolute() else root / path


def digest(path):
    hasher = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            hasher.update(block)
    return hasher.hexdigest()


def hashes(checkpoint):
    result = {}
    for key in ('deliverable_sha256', 'deliverable_hashes', 'deliverables'):
        values = checkpoint.get(key)
        if isinstance(values, dict):
            for name, value in values.items():
                if isinstance(value, dict):
                    value = value.get('sha256')
                if isinstance(value, str) and re.fullmatch(r'(sha256:)?[a-fA-F0-9]{64}', value):
                    result[str(name)] = value.removeprefix('sha256:').lower()
    return result


def validate_output(video, recorded, verify):
    result = {'path': rel(video), 'present': video.is_file(), 'valid': False,
              'duration': None, 'missing_sidecars': [], 'hashes_checked': 0,
              'hash_mismatches': [], 'errors': []}
    result['missing_sidecars'] = [name for name in SIDECARS if not (video.parent / name).is_file()]
    if result['present']:
        try:
            probe = subprocess.run(['ffprobe', '-v', 'error', '-show_entries',
                                    'format=duration:stream=codec_type', '-of', 'json', str(video)],
                                   capture_output=True, text=True, timeout=30, check=True)
            data = json.loads(probe.stdout)
            duration = float(data['format']['duration'])
            if not math.isfinite(duration) or duration <= 0:
                raise ValueError('nonpositive or invalid duration')
            if not any(s.get('codec_type') == 'video' for s in data.get('streams', [])):
                raise ValueError('no video stream')
            result['duration'] = duration
        except (OSError, subprocess.SubprocessError, ValueError, KeyError, TypeError) as exc:
            result['errors'].append(f'ffprobe: {exc}')
    if verify:
        for name, expected in recorded.items():
            path = resolve(video.parent, name)
            try:
                actual = digest(path)
                result['hashes_checked'] += 1
                if actual != expected:
                    result['hash_mismatches'].append(name)
            except OSError as exc:
                result['errors'].append(f'sha256 {name}: {exc}')
    result['valid'] = bool(result['present'] and result['duration'] is not None
                           and not result['missing_sidecars'] and not result['hash_mismatches']
                           and not result['errors'])
    return result


def cache_status(root):
    folder = root / 'build/media/voiceovers'
    result = {'entries': 0, 'audio_present': 0, 'warning': None}
    path = folder / 'cache.json'
    if not path.exists():
        return result
    try:
        entries = json.loads(path.read_text())
        if not isinstance(entries, list):
            raise ValueError('expected a JSON list')
        result['entries'] = len(entries)
        result['audio_present'] = sum(
            isinstance(item, dict) and isinstance(item.get('final_audio', item.get('original_audio')), str)
            and (folder / item.get('final_audio', item.get('original_audio'))).is_file()
            for item in entries)
    except (OSError, UnicodeError, ValueError, TypeError) as exc:
        result['warning'] = str(exc)
    return result


def section_status(root, section_id, verify, single=False):
    checkpoint, error = read_yaml(root / 'checkpoint.yaml', optional=True)
    lesson, lesson_error = read_yaml(root / 'lesson.yaml')
    result = {'id': str(section_id), 'path': rel(root), 'state': checkpoint.get('state', 'planned'),
              'completed': checkpoint.get('completed', []), 'quality': checkpoint.get('quality', lesson.get('quality')),
              'voice': checkpoint.get('voice', lesson.get('voice')), 'last_error': checkpoint.get('last_error'),
              'next_action': checkpoint.get('next_action'), 'stale_inputs': [],
              'cache': cache_status(root), 'errors': [x for x in (error, lesson_error) if x]}
    if not isinstance(result['state'], str) or result['state'] not in STATES:
        result['errors'].append(f'unknown checkpoint state: {result["state"]!r}')
    if not isinstance(result['completed'], list):
        result['errors'].append('checkpoint completed must be a list')
        result['completed'] = []
    try:
        stamp = root / 'checkpoint.yaml'
        if stamp.exists():
            result['stale_inputs'] = [name for name in ('scenes.py', 'notes.md', 'lesson.yaml')
                                      if (root / name).exists() and (root / name).stat().st_mtime_ns > stamp.stat().st_mtime_ns]
        if checkpoint.get('deliverables_dir'):
            folder = resolve(root, checkpoint['deliverables_dir'])
        elif single:
            folder = root / 'build'
        else:
            revisions = sorted((root / 'deliverables').glob('r*'))
            folder = revisions[-1] if revisions else root / 'deliverables/r001'
        video = folder / f'{section_id}.mp4'
        if not video.exists():
            candidates = sorted(folder.glob('*.mp4'))
            if len(candidates) == 1:
                video = candidates[0]
        recorded = hashes(checkpoint)
        if isinstance(checkpoint.get('video_sha256'), str):
            value = checkpoint['video_sha256'].removeprefix('sha256:')
            if re.fullmatch('[a-fA-F0-9]{64}', value):
                recorded[video.name] = value.lower()
        result['output'] = validate_output(video, recorded, verify)
        result['errors'].extend(result['output']['errors'])
    except (OSError, ValueError, TypeError) as exc:
        result['output'] = {'present': False, 'valid': False, 'duration': None}
        result['errors'].append(str(exc))
    # A single lesson with no checkpoint has no recorded acceptance, even if build exists.
    result['ready'] = (result['state'] == 'ready' and result['output']['valid']
                       and not result['stale_inputs'] and not result['errors'])
    return result


def held_locks(folder):
    result, errors = [], []
    if not folder.exists():
        return result, errors
    local_hosts = {socket.gethostname(), socket.getfqdn(), os.uname().nodename}
    try:
        for lock in sorted(folder.iterdir()):
            if not lock.is_dir():
                continue
            row = {'path': rel(lock), 'owner': None, 'pid': None, 'age_seconds': None,
                   'status': 'UNKNOWN', 'error': None}
            try:
                owner_file = lock / 'owner'
                text = owner_file.read_text().strip()
                fields = dict(re.findall(r'([\w-]+)=([^\s]+)', text))
                row['owner'] = text.split(' pid=', 1)[0]
                row['pid'] = int(fields['pid'])
                if row['pid'] <= 0:
                    raise ValueError('pid must be positive')
                try:
                    since = float(fields.get('since', ''))
                    if not math.isfinite(since):
                        raise ValueError('invalid time')
                except ValueError:
                    try:
                        since = datetime.fromisoformat(fields.get('since', '').replace('Z', '+00:00')).timestamp()
                    except ValueError:
                        since = owner_file.stat().st_mtime
                row['age_seconds'] = max(0, time.time() - since)
                host = fields.get('host', fields.get('hostname'))
                row['host'] = host
                if not host:
                    row['status'] = 'UNKNOWN'  # Legacy records cannot establish the PID's host.
                elif host not in local_hosts:
                    row['status'] = 'REMOTE'
                else:
                    try:
                        os.kill(row['pid'], 0)
                        row['status'] = 'LIVE'
                    except ProcessLookupError:
                        row['status'] = 'STALE'
                    except PermissionError:
                        row['status'] = 'LIVE'
            except (OSError, UnicodeError, ValueError, KeyError) as exc:
                row['error'] = str(exc)
            result.append(row)
    except OSError as exc:
        errors.append(f'{rel(folder)}: {exc}')
    return result, errors


def command(*args):
    return shlex.join(['study', *map(str, args)])


def config_matches(actual, expected):
    if isinstance(expected, dict):
        return isinstance(actual, dict) and all(config_matches(actual.get(k), v) for k, v in expected.items())
    return actual == expected


def dashboard(root, verify=False):
    report = {'path': rel(root), 'kind': 'lesson', 'sections': [], 'locks': [],
              'assembly': None, 'errors': [], 'next_steps': []}
    collection = root / 'collection.yaml'
    spec = {}
    if collection.exists():
        report['kind'] = 'collection'
        spec, error = read_yaml(collection)
        if error:
            report['errors'].append(error)
        report['title'] = spec.get('title', root.name)
        sections = spec.get('sections', [])
        if not isinstance(sections, list) or not sections:
            report['errors'].append('collection sections must be a nonempty list')
            sections = []
        seen = set()
        for item in sections:
            try:
                if not isinstance(item, dict) or not isinstance(item.get('id'), str):
                    raise ValueError(f'invalid section entry: {item!r}')
                if item['id'] in seen:
                    raise ValueError(f'duplicate section id: {item["id"]}')
                seen.add(item['id'])
                folder = resolve(root, item.get('path', f'sections/{item["id"]}')).resolve()
                report['sections'].append(section_status(folder, item['id'], verify))
            except (OSError, ValueError, TypeError) as exc:
                report['errors'].append(str(exc))
    else:
        report['title'] = root.name
        report['sections'].append(section_status(root, root.name, verify, single=True))
    try:
        folders = {root / 'locks'}
        if spec.get('locks'):
            folders.add(resolve(root, spec['locks']))
        for folder in sorted(folders):
            locks, errors = held_locks(folder)
            report['locks'].extend(locks)
            report['errors'].extend(errors)
    except (OSError, ValueError, TypeError) as exc:
        report['errors'].append(str(exc))
    for row in report['sections']:
        if report['kind'] == 'collection':
            for key in ('quality', 'voice'):
                if spec.get(key) is not None and not config_matches(row.get(key), spec[key]):
                    row['ready'] = False
                    row['configuration_warning'] = f'{key} differs from collection; reconcile before assembly'
        if not row['ready']:
            action = f'Reassign/review {row["id"]} from its checkpoint; '
            if row['errors']:
                action += f'fix YAML/output errors, then {command("status", row["path"], "--verify")}'
            else:
                action += command('review', row['path'], '--lint', '--sheet')
            report['next_steps'].append(action)
            report['next_steps'].append('Check narration without synthesis: ' + command('narrate', row['path'], '--check'))
    all_sections = bool(report['sections']) and all(row['ready'] for row in report['sections'])
    if report['kind'] == 'collection':
        checkpoint, error = read_yaml(root / 'assembly-checkpoint.yaml', optional=True)
        assembly = {'state': checkpoint.get('state', 'not started'), 'output': None, 'errors': [],
                    'last_error': checkpoint.get('last_error'), 'next_action': checkpoint.get('next_action')}
        if error:
            assembly['errors'].append(error)
        try:
            output = checkpoint.get('output', {})
            if isinstance(output, str):
                output = {'path': output}
            if not isinstance(output, dict):
                raise ValueError('assembly output must be a mapping or path')
            video = resolve(root, output.get('path', f'combined/build/combined.mp4'))
            recorded = hashes(checkpoint)
            if isinstance(output.get('sha256'), str):
                value = output['sha256'].removeprefix('sha256:')
                if re.fullmatch('[a-fA-F0-9]{64}', value):
                    recorded[video.name] = value.lower()
            assembly['output'] = validate_output(video, recorded, verify)
            assembly['errors'].extend(assembly['output']['errors'])
            assembly['stale'] = collection.stat().st_mtime_ns > (root / 'assembly-checkpoint.yaml').stat().st_mtime_ns if checkpoint else False
        except (OSError, ValueError, TypeError) as exc:
            assembly['errors'].append(str(exc))
        assembly['ready'] = bool(assembly['state'] == 'ready' and assembly['output']
                                 and assembly['output']['valid'] and not assembly['errors']
                                 and not assembly.get('stale'))
        report['assembly'] = assembly
        if not assembly['ready'] or not all_sections:
            if all_sections and not report['locks'] and not report['errors']:
                report['next_steps'].append('Assembly can run after coordinator preflight/restaging (references/parallel-sections.md); '
                                            + command('build', rel(root / 'combined'), '-q', str(spec.get('quality', 'h')), '--no-render', '--frames', '4'))
            else:
                report['next_steps'].append('Assembly waits for valid, unchanged ready sections and released locks.')
    for lock in report['locks']:
        report['next_steps'].append(f'{lock["status"]} lock {lock["path"]}: '
                                    + ('inspect owner and recover before reassignment (status removes nothing).'
                                       if lock['status'] == 'STALE' else 'check ownership before starting duplicate work.'))
    errors = report['errors'] + [e for row in report['sections'] for e in row['errors']]
    if report['assembly']:
        errors += report['assembly']['errors']
    ready = all_sections and not report['locks'] and (not report['assembly'] or report['assembly']['ready'])
    report['exit_code'] = 2 if errors else 0 if ready else 1
    if not report['next_steps']:
        report['next_steps'].append('All ready; reuse the accepted outputs.')
    return report


def output_summary(output):
    if not output:
        return 'missing'
    label = 'valid' if output['valid'] else 'INVALID' if output['present'] else 'missing'
    if output.get('duration') is not None:
        label += f' ({output["duration"]:.2f}s)'
    if output.get('missing_sidecars'):
        label += '; missing ' + ', '.join(output['missing_sidecars'])
    if output.get('hashes_checked'):
        label += f'; sha256 checked={output["hashes_checked"]}'
    if output.get('hash_mismatches'):
        label += '; SHA256 MISMATCH ' + ', '.join(output['hash_mismatches'])
    return label


def print_report(report):
    # Collapse embedded newlines/control characters from YAML into readable terminal lines.
    def line(value):
        text = str(value)
        indent = len(text) - len(text.lstrip(' '))
        print(' ' * indent + ' '.join(text.split()))
    line(f'Study status: {report["title"]} [{report["kind"]}]')
    line(report['path'])
    for row in report['sections']:
        line(f'  {row["id"]} | {row["state"]} | deliverable: {output_summary(row["output"])}')
        line('    completed: ' + (', '.join(map(str, row['completed'])) or 'none'))
        cache = row['cache']
        line(f'    narration cache: {cache["entries"]} entries, {cache["audio_present"]} audio present (not a current-text hit check)')
        if cache['warning']:
            line('    cache warning: ' + cache['warning'])
        if row['stale_inputs']:
            line('    stale: inputs changed since checkpoint: ' + ', '.join(row['stale_inputs']))
        for key in ('last_error', 'next_action', 'configuration_warning'):
            if row.get(key):
                line(f'    {key}: {row[key]}')
        for error in row['errors']:
            line('    ERROR: ' + error)
    line('Locks: ' + ('none' if not report['locks'] else ''))
    for lock in report['locks']:
        age = f'{lock["age_seconds"]:.0f}s' if lock['age_seconds'] is not None else '?'
        line(f'  {lock["status"]} {lock["path"]} owner={lock["owner"]} pid={lock["pid"]} age={age}'
             + (f' ({lock["error"]})' if lock['error'] else ''))
    if report['assembly']:
        assembly = report['assembly']
        line(f'Assembly: {assembly["state"]} | output: {output_summary(assembly["output"])}')
        if assembly.get('stale'):
            line('  stale: collection changed since assembly checkpoint')
        for key in ('last_error', 'next_action'):
            if assembly.get(key):
                line(f'  {key}: {assembly[key]}')
        for error in assembly['errors']:
            line('  ERROR: ' + error)
    for error in report['errors']:
        line('ERROR: ' + error)
    line('Next steps:')
    for step in report['next_steps']:
        line('  - ' + step)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('target', help='collection/lesson slug or path')
    parser.add_argument('--json', action='store_true', help='print machine-readable JSON')
    parser.add_argument('--verify', action='store_true', help='verify recorded deliverable SHA256 hashes (may read large videos)')
    parser.add_argument('--lessons-dir', help='override lesson slug search directory')
    args = parser.parse_args(argv)
    try:
        report = dashboard(lesson_dir(args.target, args.lessons_dir), args.verify)
    except (OSError, ValueError, TypeError) as exc:
        report = {'exit_code': 2, 'errors': [str(exc)]}
        if not args.json:
            print(f'study status: ERROR: {exc}')
    if args.json:
        print(json.dumps(report, indent=2, default=str))
    elif 'sections' in report:
        print_report(report)
    return report['exit_code']


if __name__ == '__main__':
    raise SystemExit(main())
