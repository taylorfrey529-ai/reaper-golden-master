#!/usr/bin/env python3
"""Create a deterministic manifest of live mutable REAPER continuation state."""
from __future__ import annotations
import argparse, hashlib, importlib.machinery, importlib.util, json, os, re, stat, subprocess, sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]; CORE=ROOT/'bin'/'reaperctl-core'; BASE=ROOT/'BASELINE.json'
REPOSITORY='taylorfrey529-ai/reaper-golden-master'; BRANCH='development/reaperctl'
EXPECTED_REAPER_SHA='cee99a74fdd9fc87974c96ea334a50afff4ca8d3121591aed218057bb38185e4'
EXPECTED_PROJECT_SHA='2ea85263d6dc125bf7739264956a1ee1a8074c2b42f69b606b5e9d8b7e9771f1'


def load_core():
    loader=importlib.machinery.SourceFileLoader('reaperctl_snapshot_core',str(CORE)); spec=importlib.util.spec_from_loader(loader.name,loader)
    if spec is None: raise RuntimeError(f'cannot load {CORE}')
    module=importlib.util.module_from_spec(spec); sys.modules[loader.name]=module; loader.exec_module(module); return module
core=load_core()


def sha_bytes(data:bytes)->str:return hashlib.sha256(data).hexdigest()
def sha(path:Path)->str:
    digest=hashlib.sha256()
    with path.open('rb') as handle:
        for chunk in iter(lambda:handle.read(1024*1024),b''):digest.update(chunk)
    return digest.hexdigest()

def canonical_bytes(obj)->bytes:return json.dumps(obj,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode('utf-8')

def item(path:Path,archive_path:str,role:str)->dict:
    if not path.is_file():raise RuntimeError(f'required snapshot file missing: {path}')
    mode=stat.S_IMODE(path.stat().st_mode)
    return {'archive_path':archive_path,'source_path':str(path),'role':role,'bytes':path.stat().st_size,'sha256':sha(path),'mode':oct(mode)}

def referenced_media(project:Path)->list[Path]:
    media=[]
    for line in project.read_text(encoding='utf-8',errors='replace').splitlines():
        match=re.match(r'^\s*FILE "(.*)"$',line)
        if match:
            path=Path(match.group(1))
            if path not in media:media.append(path)
    return media

def x11_state(display:str)->dict:
    env=os.environ.copy();env['DISPLAY']=display
    try:
        info=subprocess.run(['xdpyinfo','-display',display],text=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE,env=env,timeout=3,check=False)
        tree=subprocess.run(['xwininfo','-root','-tree'],text=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE,env=env,timeout=3,check=False)
    except (OSError,subprocess.TimeoutExpired) as exc:raise RuntimeError(f'cannot inspect X11 state: {exc}') from exc
    if info.returncode or tree.returncode:raise RuntimeError(f'X11 display not ready: {display}')
    dim=re.search(r'dimensions:\s+(\d+)x(\d+)\s+pixels',info.stdout); resolution=[int(dim.group(1)),int(dim.group(2))] if dim else None
    titles=re.findall(r'0x[0-9a-fA-F]+\s+"([^"]+)"',tree.stdout)
    canonical=next((title for title in titles if 'ASIO-Routing-Project' in title and 'REAPER v7.79' in title),None)
    if not canonical or 'EVALUATION LICENSE' not in canonical:raise RuntimeError('canonical REAPER evaluation window is not mapped')
    about=next((title for title in titles if title.startswith('About REAPER v7.79/')),None)
    return {'display':display,'resolution':resolution,'canonical_window_title':canonical,'about_window_title':about,'license_state':'evaluation'}

def snapshot_inventory(paths:dict,screenshot:Path|None)->list[dict]:
    project=paths['project']; workspace=paths.get('workspace',project.parents[2]); resource=paths['resource']; apollo=Path(os.environ.get('REAPER_GM_VIRTUAL_APOLLO_ROOT','/mnt/data/virtual-apollo'))
    specs=[
        (project,'workspace/projects/ASIO-Routing-Project/ASIO-Routing-Project.RPP','canonical-project'),
        (workspace/'projects/ASIO-Routing-Project/ROUTING.txt','workspace/projects/ASIO-Routing-Project/ROUTING.txt','project-routing'),
        (workspace/'projects/ASIO-Routing-Project/reaper-linux-audio.ini','workspace/projects/ASIO-Routing-Project/reaper-linux-audio.ini','project-audio-config'),
        (workspace/'projects/ASIO-Routing-Project/create_project.lua','workspace/projects/ASIO-Routing-Project/create_project.lua','project-builder'),
        (workspace/'projects/ASIO-Routing-Project/fix_routing.lua','workspace/projects/ASIO-Routing-Project/fix_routing.lua','project-routing-repair'),
        (workspace/'start-desktop.sh','workspace/start-desktop.sh','desktop-launcher'),
        (workspace/'stop-desktop.sh','workspace/stop-desktop.sh','desktop-launcher'),
        (workspace/'verify-desktop.sh','workspace/verify-desktop.sh','desktop-verifier'),
        (workspace/'desktop_shell.py','workspace/desktop_shell.py','desktop-shell'),
        (workspace/'bin/launch-reaper.sh','workspace/bin/launch-reaper.sh','reaper-launcher'),
        (workspace/'home/.asoundrc','workspace/home/.asoundrc','alsa-config'),
        (workspace/'config/openbox/rc.xml','workspace/config/openbox/rc.xml','openbox-config'),
        (resource/'reaper.ini','workspace/config/REAPER/reaper.ini','reaper-config'),
        (resource/'reaper-midihw-alsa.ini','workspace/config/REAPER/reaper-midihw-alsa.ini','reaper-config'),
        (resource/'reaper-midihw-linux.ini','workspace/config/REAPER/reaper-midihw-linux.ini','reaper-config'),
        (resource/'reaper-mouse.ini','workspace/config/REAPER/reaper-mouse.ini','reaper-config'),
        (resource/'reaper-fxtags.ini','workspace/config/REAPER/reaper-fxtags.ini','reaper-config'),
        (resource/'reaper-jsfx.ini','workspace/config/REAPER/reaper-jsfx.ini','reaper-config'),
        (resource/'reaper-vstplugins64.ini','workspace/config/REAPER/reaper-vstplugins64.ini','reaper-config'),
        (apollo/'README.md','virtual-apollo/README.md','virtual-apollo-doc'),
        (apollo/'bin/apollo_ears.py','virtual-apollo/bin/apollo_ears.py','virtual-apollo-runtime'),
        (apollo/'bin/apollo_pipe_sink.py','virtual-apollo/bin/apollo_pipe_sink.py','virtual-apollo-runtime'),
        (apollo/'bin/start-apollo.sh','virtual-apollo/bin/start-apollo.sh','virtual-apollo-runtime'),
        (apollo/'bin/status-apollo.sh','virtual-apollo/bin/status-apollo.sh','virtual-apollo-runtime'),
        (apollo/'bin/stop-apollo.sh','virtual-apollo/bin/stop-apollo.sh','virtual-apollo-runtime'),
        (apollo/'bin/test-apollo.sh','virtual-apollo/bin/test-apollo.sh','virtual-apollo-test'),
        (apollo/'config/alsa-apollo.conf','virtual-apollo/config/alsa-apollo.conf','virtual-apollo-config'),
        (apollo/'config/asoundrc','virtual-apollo/config/asoundrc','virtual-apollo-config'),
        (apollo/'state/device.json','virtual-apollo/state/device.json','virtual-apollo-state'),
    ]
    inventory=[item(path,arc,role) for path,arc,role in specs]
    media_root=workspace/'audio/generated'
    for path in referenced_media(project):
        if not path.is_file():raise RuntimeError(f'project media missing: {path}')
        try:rel=path.relative_to(media_root)
        except ValueError:rel=Path(path.name)
        inventory.append(item(path,'workspace/audio/generated/'+rel.as_posix(),'project-media'))
    if screenshot is not None:inventory.append(item(screenshot,'evidence/reaper-live.png','live-screenshot'))
    inventory.sort(key=lambda value:value['archive_path'])
    return inventory

def build_snapshot(data:dict,paths:dict,screenshot:Path|None)->dict:
    project=paths['project']; reaper_bin=paths['reaper']; project_hash=sha(project); reaper_hash=sha(reaper_bin)
    if project_hash!=EXPECTED_PROJECT_SHA:raise RuntimeError(f'canonical project SHA mismatch: {project_hash}')
    if reaper_hash!=EXPECTED_REAPER_SHA:raise RuntimeError(f'REAPER binary SHA mismatch: {reaper_hash}')
    baseline=data.get('baseline',{})
    manifest={'schema_version':1,'kind':'reaper-continuation-snapshot','continuation':{'repository':REPOSITORY,'branch':BRANCH},'golden_master':{'name':baseline.get('golden_master','GM-2026-09-08'),'id':baseline.get('golden_master_id'),'recovery_authority':baseline.get('recovery_authority_repository','taylorfrey529-ai/reaper-is-free'),'proof_head':baseline.get('recovery_authority_proof_head')},'live_state':x11_state(str(paths['display'])),'runtime_binding':{'reaper_binary':str(reaper_bin),'sha256':reaper_hash,'bytes':reaper_bin.stat().st_size,'embedded_in_continuation_backup':False,'recovery_policy':'restore exact runtime from admitted Golden Master'},'inventory':snapshot_inventory(paths,screenshot),'exclusions':['workspace run/*.pid and run/display','workspace logs/*','Virtual Apollo rolling ears/latest.wav and ears/levels.json','REAPER runtime tree (bound by hash and Golden Master, not duplicated)','temporary renders/stems/disposable projects']}
    snapshot_id='sha256:'+sha_bytes(canonical_bytes(manifest));manifest['snapshot_id']=snapshot_id;return manifest

def verify_snapshot_id(manifest:dict)->bool:
    supplied=manifest.get('snapshot_id'); body=dict(manifest);body.pop('snapshot_id',None); return supplied=='sha256:'+sha_bytes(canonical_bytes(body))

def build_parser():
    parser=argparse.ArgumentParser(prog='reaperctl snapshot',description=__doc__);parser.add_argument('--baseline',type=Path,default=Path(os.environ.get('REAPERCTL_BASELINE',BASE)));parser.add_argument('--screenshot',type=Path);parser.add_argument('--output',type=Path,default=Path('/mnt/data/reaperctl-evidence/SNAPSHOT.json'));parser.add_argument('--overwrite',action='store_true');parser.add_argument('--json',action='store_true');return parser

def main(argv=None):
    args=build_parser().parse_args(argv)
    try:data=core.load_baseline(args.baseline)
    except ValueError as exc:print(f'reaperctl: {exc}',file=sys.stderr);return 2
    checks=core.static_checks(data)
    if not all(check.ok for check in checks):return int(core.render_checks(checks,args.json,'baseline'))
    try:
        output=args.output.expanduser().resolve(); screenshot=args.screenshot.expanduser().resolve() if args.screenshot else None
        if output.exists() and not args.overwrite:raise ValueError(f'output already exists; use --overwrite: {output}')
        if screenshot is not None and not screenshot.is_file():raise ValueError(f'screenshot not found: {screenshot}')
        manifest=build_snapshot(data,core.workspace_paths(data),screenshot)
        if not verify_snapshot_id(manifest):raise RuntimeError('snapshot self-verification failed')
        output.parent.mkdir(parents=True,exist_ok=True);payload=json.dumps(manifest,indent=2,sort_keys=True)+'\n';output.write_text(payload,encoding='utf-8')
        report={'ok':True,'output':str(output),'bytes':output.stat().st_size,'sha256':sha(output),'snapshot_id':manifest['snapshot_id'],'inventory_files':len(manifest['inventory']),'inventory_bytes':sum(value['bytes'] for value in manifest['inventory']),'runtime_embedded':False}
    except ValueError as exc:print(f'reaperctl: {exc}',file=sys.stderr);return 2
    except RuntimeError as exc:print(f'reaperctl: {exc}',file=sys.stderr);return 4
    if args.json:print(json.dumps(report,indent=2))
    else:print(f'Snapshot: VERIFIED\nID: {report["snapshot_id"]}\nOutput: {report["output"]}\nInventory: {report["inventory_files"]} files / {report["inventory_bytes"]} bytes')
    return 0
if __name__=='__main__':raise SystemExit(main())
