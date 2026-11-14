"""Explicit integration check: a tiny source-only say example, never a user lecture.

Run with bin/study python tests/smoke.py --work-dir /new/isolated/path.
This is separate from unittest discovery because it renders and uses macOS say.
"""
import argparse
import json
from pathlib import Path
import shutil
import subprocess


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--work-dir',type=Path,required=True)
    args=parser.parse_args()
    root=Path(__file__).resolve().parents[1]
    work=args.work_dir.expanduser().resolve()
    work.mkdir(parents=True,exist_ok=False)
    lesson=work/'hello'
    shutil.copytree(root/'examples/hello',lesson)
    study=str(root/'bin/study')
    subprocess.run([study,'build',str(lesson),'--engine','say','-q','l','--jobs','1','--frames','2'],check=True)
    subprocess.run([study,'review',str(lesson),'--lint','--sheet'],check=True)
    video=lesson/'build/draft/hello.mp4'
    probe=subprocess.run(['ffprobe','-v','error','-show_streams','-show_format','-of','json',str(video)],check=True,capture_output=True,text=True)
    data=json.loads(probe.stdout)
    duration=float(data['format']['duration'])
    streams={s['codec_type']:s for s in data['streams']}
    if not 0<duration<=120 or not {'audio','video'}<=streams.keys():
        raise RuntimeError('Smoke output must be a short video with real audio')
    if streams['video']['height']!=480:
        raise RuntimeError('Expected a 480p draft')
    subprocess.run(['ffmpeg','-v','error','-xerror','-i',str(video),'-f','null','-'],check=True)
    report={'video':str(video),'duration_seconds':duration,'height':streams['video']['height'],'audio_codec':streams['audio']['codec_name'],'decode':'passed','engine':'say'}
    (work/'smoke.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))


if __name__=='__main__':
    main()
