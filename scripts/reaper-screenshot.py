#!/usr/bin/env python3
"""Capture and verify the real X11 REAPER production desktop without altering project state."""
from __future__ import annotations
import argparse, hashlib, importlib.machinery, importlib.util, json, os, re, shutil, subprocess, sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]; CORE=ROOT/'bin'/'reaperctl-core'; BASE=ROOT/'BASELINE.json'
EXPECTED_REAPER_SHA='cee99a74fdd9fc87974c96ea334a50afff4ca8d3121591aed218057bb38185e4'
EXPECTED_SIZE=(1440,900)


def load_core():
    loader=importlib.machinery.SourceFileLoader('reaperctl_screenshot_core',str(CORE)); spec=importlib.util.spec_from_loader(loader.name,loader)
    if spec is None: raise RuntimeError(f'cannot load {CORE}')
    module=importlib.util.module_from_spec(spec); sys.modules[loader.name]=module; loader.exec_module(module); return module
core=load_core()


def sha(path:Path)->str:
    digest=hashlib.sha256()
    with path.open('rb') as handle:
        for chunk in iter(lambda:handle.read(1024*1024),b''): digest.update(chunk)
    return digest.hexdigest()


def run(command:list[str],env=None,timeout:float=5.0)->subprocess.CompletedProcess[str]:
    try:return subprocess.run(command,text=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE,env=env,timeout=timeout,check=False)
    except (OSError,subprocess.TimeoutExpired) as exc: raise RuntimeError(f'command failed: {command[0]}: {exc}') from exc


def parse_dimensions(text:str)->tuple[int,int]|None:
    match=re.search(r'dimensions:\s+(\d+)x(\d+)\s+pixels',text)
    return (int(match.group(1)),int(match.group(2))) if match else None


def parse_window_titles(text:str)->list[str]:
    titles=[]
    for line in text.splitlines():
        match=re.search(r'0x[0-9a-fA-F]+\s+"([^"]+)"',line)
        if match:titles.append(match.group(1))
    return titles


def classify_reaper_windows(titles:list[str])->dict[str,object]:
    canonical=next((title for title in titles if 'ASIO-Routing-Project' in title and 'REAPER v7.79' in title),None)
    evaluation=bool(canonical and 'EVALUATION LICENSE' in canonical)
    about=next((title for title in titles if title.startswith('About REAPER v7.79/')),None)
    return {'canonical_window_title':canonical,'evaluation_license_title':evaluation,'about_window_title':about,'about_window_present':about is not None}


def validate_png(path:Path,expected=EXPECTED_SIZE)->dict[str,object]:
    try:
        from PIL import Image,ImageStat
    except Exception as exc: raise RuntimeError(f'Pillow is required to validate screenshot bytes: {exc}') from exc
    try:
        image=Image.open(path).convert('RGB')
    except Exception as exc: raise RuntimeError(f'invalid PNG screenshot {path}: {exc}') from exc
    if image.size!=expected: raise RuntimeError(f'screenshot resolution mismatch: expected {expected[0]}x{expected[1]}, got {image.size[0]}x{image.size[1]}')
    sample=image.resize((180,112)); unique=len(set(sample.getdata())); stddev=[float(value) for value in ImageStat.Stat(sample).stddev]
    if unique<32 or sum(stddev)<3.0: raise RuntimeError(f'screenshot is blank/uniform: unique(sample)={unique}, stddev={stddev}')
    return {'width':image.size[0],'height':image.size[1],'unique_sample_colors':unique,'stddev':stddev}


def build_parser():
    parser=argparse.ArgumentParser(prog='reaperctl screenshot',description=__doc__)
    parser.add_argument('--baseline',type=Path,default=Path(os.environ.get('REAPERCTL_BASELINE',BASE)))
    parser.add_argument('--output',type=Path,default=Path('/mnt/data/reaperctl-evidence/reaper-live.png'))
    parser.add_argument('--overwrite',action='store_true')
    parser.add_argument('--json',action='store_true')
    return parser


def main(argv=None):
    args=build_parser().parse_args(argv)
    try:data=core.load_baseline(args.baseline)
    except ValueError as exc:print(f'reaperctl: {exc}',file=sys.stderr);return 2
    checks=core.static_checks(data)
    if not all(check.ok for check in checks):return int(core.render_checks(checks,args.json,'baseline'))
    paths=core.workspace_paths(data); display=str(paths['display']); output=args.output.expanduser().resolve(); project=paths['project']; reaper_bin=paths['reaper']
    try:
        if not project.is_file():raise RuntimeError(f'canonical project missing: {project}')
        if not reaper_bin.is_file():raise RuntimeError(f'REAPER binary missing: {reaper_bin}')
        reaper_sha=sha(reaper_bin)
        if reaper_sha!=EXPECTED_REAPER_SHA:raise RuntimeError(f'REAPER binary SHA mismatch: {reaper_sha}')
        if output.exists() and not args.overwrite:raise ValueError(f'output already exists; use --overwrite: {output}')
        if shutil.which('xdpyinfo') is None or shutil.which('xwininfo') is None or shutil.which('scrot') is None:raise RuntimeError('xdpyinfo, xwininfo, and scrot are required')
        env=os.environ.copy();env['DISPLAY']=display
        info=run(['xdpyinfo','-display',display],env=env)
        if info.returncode:raise RuntimeError(f'X11 display unavailable: {display}: {info.stderr.strip()}')
        dimensions=parse_dimensions(info.stdout)
        if dimensions!=EXPECTED_SIZE:raise RuntimeError(f'live display resolution mismatch: expected 1440x900, got {dimensions}')
        tree=run(['xwininfo','-root','-tree'],env=env)
        if tree.returncode:raise RuntimeError(f'cannot inspect X11 window tree: {tree.stderr.strip()}')
        titles=parse_window_titles(tree.stdout); windows=classify_reaper_windows(titles)
        if not windows['canonical_window_title']:raise RuntimeError('canonical REAPER 7.79 project window is not mapped')
        if not windows['evaluation_license_title']:raise RuntimeError('canonical REAPER window does not report EVALUATION LICENSE')
        project_before=sha(project); output.parent.mkdir(parents=True,exist_ok=True)
        if output.exists():output.unlink()
        captured=run(['scrot',str(output)],env=env,timeout=10.0)
        if captured.returncode or not output.is_file():raise RuntimeError(f'scrot capture failed: {(captured.stderr or captured.stdout).strip()}')
        validation=validate_png(output); project_after=sha(project)
        if project_after!=project_before:raise RuntimeError('canonical project changed during screenshot capture')
        report={'ok':True,'output':str(output),'bytes':output.stat().st_size,'sha256':sha(output),'display':display,'resolution':{'width':validation['width'],'height':validation['height']},'unique_sample_colors':validation['unique_sample_colors'],'stddev':validation['stddev'],'project':str(project),'project_sha256_before':project_before,'project_sha256_after':project_after,'reaper_binary_sha256':reaper_sha,'windows':windows,'license_state':'evaluation','capture_source':'real X11 root display'}
    except ValueError as exc:print(f'reaperctl: {exc}',file=sys.stderr);return 2
    except RuntimeError as exc:print(f'reaperctl: {exc}',file=sys.stderr);return 4
    if args.json:print(json.dumps(report,indent=2))
    else:
        print('REAPER screenshot: VERIFIED');print(f'Output: {report["output"]}');print(f'SHA-256: {report["sha256"]}');print(f'Resolution: {report["resolution"]["width"]}x{report["resolution"]["height"]}');print(f'License state: {report["license_state"]}')
    return 0
if __name__=='__main__':raise SystemExit(main())
