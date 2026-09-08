#!/usr/bin/env python3
"""Derive close-shell pan from the fixed stereo overhead image without changing timing or media state."""
from __future__ import annotations
import argparse, hashlib, importlib.machinery, importlib.util, json, math, os, re, sys, wave
from pathlib import Path
from typing import Any

ROOT=Path(__file__).resolve().parents[1]; CORE=ROOT/'bin'/'reaperctl-core'; BASE=ROOT/'BASELINE.json'
SCAN_SR=2000; SCAN_BIN_SEC=.005; MAX_EVENTS=8; MIN_EVENT_GAP_SEC=.120
ARRIVAL_SEARCH_PRE_SEC=.005; ARRIVAL_SEARCH_POST_SEC=.025
PAN_PRE_SEC=.002; PAN_POST_SEC=.018
MIN_HITS=2; MIN_OH_ENERGY=1e-7; PAN_MAD_FLOOR=.04

def load_core():
    loader=importlib.machinery.SourceFileLoader('reaperctl_pan_core',str(CORE)); spec=importlib.util.spec_from_loader(loader.name,loader)
    if spec is None: raise RuntimeError(f'cannot load {CORE}')
    module=importlib.util.module_from_spec(spec); sys.modules[loader.name]=module; loader.exec_module(module); return module
core=load_core()

def sha(path:Path)->str:
    digest=hashlib.sha256()
    with path.open('rb') as handle:
        for chunk in iter(lambda:handle.read(1024*1024),b''): digest.update(chunk)
    return digest.hexdigest()

def is_overhead_name(name:str)->bool:
    n=name.lower(); return 'overhead' in n or n=='oh' or re.match(r'^oh[ _-]?',n) is not None or re.search(r'[ _-]oh[ _-]?',n) is not None

def is_excluded_non_shell(name:str)->bool:
    n=name.lower(); bad=['overhead','room','ambient','ambience','cymbal','hihat','hi-hat','hat ','ride','crash','china','splash','shaker','tamb','perc','drum bus','drumbus','drum master','parallel','crush','verb','reverb']
    return is_overhead_name(name) or any(token in n for token in bad)

def is_shell_name(name:str)->bool:
    if is_excluded_non_shell(name): return False
    n=name.lower(); rack=re.search(r'(^|[ _-])rack([ _-]|$)',n) is not None
    return any(token in n for token in ('kick','bass drum','snare','tom','floor')) or rack or n=='bd' or n=='sn' or re.match(r'^(bd|sn)[ _-]',n) is not None

def is_tom1_name(name:str)->bool: return re.search(r'(tom|rack)[ _-]*0*1([^0-9]?)',name.lower()) is not None

class Audio:
    def __init__(self,path:Path):
        self.path=path
        with wave.open(str(path),'rb') as w:
            self.ch=w.getnchannels(); self.sr=w.getframerate(); self.width=w.getsampwidth(); self.frames=w.getnframes(); raw=w.readframes(self.frames)
        if self.width!=3 or self.sr!=48000 or self.ch not in (1,2): raise ValueError(f'pan-drums requires 48 kHz, 24-bit mono/stereo WAVE: {path}')
        b=memoryview(raw); values=[]
        for i in range(0,len(raw),3):
            v=b[i]|(b[i+1]<<8)|(b[i+2]<<16); v=v-0x1000000 if v&0x800000 else v; values.append(v/8388608.0)
        self.data=[values[c::self.ch] for c in range(self.ch)]
    def sample(self,c:int,t:float)->float:
        x=t*self.sr
        if x<0 or x>self.frames-1:return 0.0
        i=int(math.floor(x)); frac=x-i; arr=self.data[min(c,self.ch-1)]
        if i>=self.frames-1:return arr[i]
        return arr[i]+(arr[i+1]-arr[i])*frac
    def read(self,start:float,duration:float,sr:int):
        frames=max(1,int(duration*sr+.5)); left=[]; right=[]
        for i in range(frames):
            t=start+i/sr
            if self.ch==1:
                v=self.sample(0,t); left.append(v); right.append(v)
            else:
                left.append(self.sample(0,t)); right.append(self.sample(1,t))
        return left,right

def mono(left,right): return [.5*(a+b) for a,b in zip(left,right)]
def median(values):
    if not values:return None
    values=sorted(values); n=len(values); return values[n//2] if n%2 else .5*(values[n//2-1]+values[n//2])

def detect_events(audio:Audio):
    duration=audio.frames/audio.sr; samples=mono(*audio.read(0,duration,SCAN_SR)); bin_frames=max(1,int(SCAN_BIN_SEC*SCAN_SR+.5)); candidates=[]; i=0
    while i<len(samples):
        last=min(len(samples),i+bin_frames); segment=samples[i:last]
        if segment:
            j=max(range(len(segment)),key=lambda k:abs(segment[k])); amp=abs(segment[j])
            if amp>1e-6:candidates.append((amp,(i+j)/SCAN_SR))
        i=last
    candidates.sort(reverse=True); chosen=[]
    for amp,t in candidates:
        if all(abs(t-e[1])>=MIN_EVENT_GAP_SEC for e in chosen):
            chosen.append((amp,t))
            if len(chosen)>=MAX_EVENTS:break
    return sorted(chosen,key=lambda x:x[1])

def find_oh_arrival(overhead:Audio,event_time:float)->float:
    start=max(0.0,event_time-ARRIVAL_SEARCH_PRE_SEC); end=min(overhead.frames/overhead.sr,event_time+ARRIVAL_SEARCH_POST_SEC)
    first=max(0,int(start*overhead.sr)); last=min(overhead.frames,int(end*overhead.sr)+1)
    if first>=last:return event_time
    best=first; best_value=-1.0
    for i in range(first,last):
        value=abs(overhead.data[0][i])+abs(overhead.data[1][i])
        if value>best_value:best_value=value; best=i
    return best/overhead.sr

def pan_measurement(overhead:Audio,event_time:float)->dict[str,float]|None:
    arrival=find_oh_arrival(overhead,event_time); first=max(0,int((arrival-PAN_PRE_SEC)*overhead.sr)); last=min(overhead.frames,int((arrival+PAN_POST_SEC)*overhead.sr))
    energies=[sum(v*v for v in overhead.data[ch][first:last]) for ch in (0,1)]; total=sum(energies)
    if total<MIN_OH_ENERGY:return None
    amplitudes=[math.sqrt(value) for value in energies]
    if amplitudes[0]+amplitudes[1]<=1e-15:return None
    pan=max(-1.0,min(1.0,4.0/math.pi*math.atan2(amplitudes[1],amplitudes[0])-1.0))
    contrast=(energies[1]-energies[0])/total
    return {'event_time':event_time,'arrival_time':arrival,'left_energy':energies[0],'right_energy':energies[1],'pan':pan,'energy_contrast':contrast}

def estimate_pan(shell:Audio,overhead:Audio):
    events=detect_events(shell); measurements=[]
    for _,event_time in events:
        measurement=pan_measurement(overhead,event_time)
        if measurement is not None:measurements.append(measurement)
    if len(measurements)<MIN_HITS:return None,events,measurements,[]
    center=median([m['pan'] for m in measurements]); mad=median([abs(m['pan']-center) for m in measurements]) or 0.0; tolerance=max(PAN_MAD_FLOOR,3*mad)
    kept=[m for m in measurements if abs(m['pan']-center)<=tolerance] or measurements
    return median([m['pan'] for m in kept]),events,measurements,kept

def parse_tracks(project:Path)->dict[str,dict[str,Any]]:
    lines=project.read_text().splitlines(); tracks={}; i=0
    while i<len(lines):
        if not lines[i].startswith('  <TRACK'):i+=1;continue
        start=i; depth=0; j=i
        while j<len(lines):
            stripped=lines[j].lstrip()
            if stripped.startswith('<'):depth+=1
            if stripped=='>':
                depth-=1
                if depth==0:j+=1;break
            j+=1
        chunk=lines[start:j]; name=None; files=[]; top_volpan=None; in_item=False; item_depth=0; item_state=[]
        for offset,line in enumerate(chunk[1:],1):
            stripped=line.strip()
            if stripped.startswith('<ITEM'):in_item=True;item_depth=1;continue
            if in_item:
                if stripped.startswith('<'):item_depth+=1
                if stripped=='>':
                    item_depth-=1
                    if item_depth==0:in_item=False
                if stripped.startswith(('POSITION ','LENGTH ','SOFFS ','PLAYRATE ')):item_state.append(stripped)
                continue
            if name is None and stripped.startswith('NAME '):name=stripped[5:].strip('"')
            if top_volpan is None and stripped.startswith('VOLPAN '):top_volpan=(offset,line)
            match=re.match(r'^FILE "(.*)"$',stripped)
            if match:files.append(match.group(1))
        files=[]
        for line in chunk:
            match=re.match(r'^\s*FILE "(.*)"$',line)
            if match:files.append(match.group(1))
        if name:tracks[name]={'start':start,'end':j,'chunk':chunk,'files':files,'file':Path(files[0]) if len(files)==1 else None,'top_volpan':top_volpan,'item_state':item_state}
        i=j
    return tracks

def validate_contract(tracks:dict[str,dict[str,Any]],shells:list[str],overhead_name:str):
    for name in [overhead_name,*shells]:
        track=tracks[name]
        if track['file'] is None or not track['file'].is_file():raise ValueError(f'pan-drums requires exactly one existing WAVE source on {name}')
        if track['top_volpan'] is None:raise ValueError(f'pan-drums requires a top-level VOLPAN on {name}')
        state=' '.join(track['item_state'])
        if 'POSITION 0' not in state or 'SOFFS 0' not in state or 'PLAYRATE 1 ' not in state:raise ValueError(f'pan-drums requires POSITION=0, SOFFS=0, PLAYRATE=1 on {name}')
    overhead=Audio(tracks[overhead_name]['file'])
    if overhead.ch!=2:raise ValueError('OH source must be stereo')
    for name in shells:
        if Audio(tracks[name]['file']).ch!=1:raise ValueError(f'initial pan-drums contract requires a mono close shell source: {name}')

def analyze(project:Path,selected:list[str]|None):
    tracks=parse_tracks(project); overheads=[name for name in tracks if is_overhead_name(name)]
    if len(overheads)!=1:raise ValueError(f'pan-drums requires exactly one stereo OH track; found {overheads}')
    shells=selected or [name for name in tracks if is_shell_name(name)]
    if not shells:raise ValueError('no shell tracks found')
    for name in shells:
        if name not in tracks or not is_shell_name(name):raise ValueError(f'not an admitted shell track: {name}')
    validate_contract(tracks,shells,overheads[0]); overhead=Audio(tracks[overheads[0]]['file']); results=[]
    for name in shells:
        pan,events,measurements,kept=estimate_pan(Audio(tracks[name]['file']),overhead)
        if pan is None:continue
        spread=median([abs(m['pan']-pan) for m in kept]) or 0.0
        results.append({'track':name,'pan':pan,'pan_percent':pan*100.0,'accepted_hits':len(kept),'candidate_hits':len(events),'pan_mad':spread,'tom1_self_anchor':is_tom1_name(name),'measurements':kept})
    if not results:raise RuntimeError('no shell track produced a reliable overhead stereo-image pan')
    return overheads[0],results,tracks

def rewrite_top_level_pans(project:Path,output:Path,results:list[dict],overwrite:bool):
    if output.resolve()==project.resolve():raise ValueError('pan-drums is non-destructive; output project must differ from input project')
    if output.exists() and not overwrite:raise ValueError(f'output project exists; use --overwrite: {output}')
    raw=project.read_bytes(); source=raw.decode('utf-8').splitlines(keepends=True); tracks=parse_tracks(project); expected={r['track']:r['pan'] for r in results}; changed=[]
    for name,pan in expected.items():
        info=tracks[name]; offset,line=info['top_volpan']; absolute=info['start']+offset; original=source[absolute]
        if original.endswith('\r\n'): newline='\r\n'
        elif original.endswith('\n'): newline='\n'
        elif original.endswith('\r'): newline='\r'
        else: newline=''
        body=original[:-len(newline)] if newline else original; indent=body[:len(body)-len(body.lstrip())]; fields=body.strip().split()
        if len(fields)<3 or fields[0]!='VOLPAN':raise RuntimeError(f'unexpected VOLPAN serialization on {name}: {source[absolute]!r}')
        before=body; fields[2]=f'{pan:.9f}'; after=indent+' '.join(fields)+newline; source[absolute]=after; changed.append({'track':name,'before':before.strip(),'after':after.strip()})
    output.parent.mkdir(parents=True,exist_ok=True); output.write_bytes(''.join(source).encode('utf-8')); return changed

def verify_pan_only(input_project:Path,output:Path,overhead_name:str,results:list[dict],before_tracks):
    after_tracks=parse_tracks(output); expected={r['track']:r for r in results}
    for name in [overhead_name,*expected]:
        if name not in after_tracks:raise RuntimeError(f'panned project missing track {name}')
        if after_tracks[name]['files']!=before_tracks[name]['files'] or after_tracks[name]['item_state']!=before_tracks[name]['item_state']:raise RuntimeError(f'media continuity regression: {name}')
    if before_tracks[overhead_name]['chunk']!=after_tracks[overhead_name]['chunk']:raise RuntimeError('overhead reference changed during pan-only transform')
    for name,result in expected.items():
        before=before_tracks[name]['chunk']; after=after_tracks[name]['chunk']; diffs=[(a,b) for a,b in zip(before,after) if a!=b]
        if len(diffs)!=1 or not diffs[0][0].strip().startswith('VOLPAN ') or not diffs[0][1].strip().startswith('VOLPAN '):raise RuntimeError(f'pan-only invariant failed for {name}: changed {len(diffs)} line(s)')
        actual=float(after_tracks[name]['top_volpan'][1].strip().split()[2])
        if abs(actual-result['pan'])>5e-9:raise RuntimeError(f'pan mismatch for {name}: expected {result["pan"]}, got {actual}')
    untouched=[name for name in before_tracks if name not in expected and name!=overhead_name]
    for name in untouched:
        if before_tracks[name]['chunk']!=after_tracks[name]['chunk']:raise RuntimeError(f'unrelated track changed during pan-only transform: {name}')
    before_raw=input_project.read_bytes().decode('utf-8').splitlines(keepends=True); after_raw=output.read_bytes().decode('utf-8').splitlines(keepends=True)
    raw_diffs=[(index,a,b) for index,(a,b) in enumerate(zip(before_raw,after_raw),1) if a!=b]
    if len(before_raw)!=len(after_raw) or len(raw_diffs)!=len(expected): raise RuntimeError(f'byte-line pan-only invariant failed: expected {len(expected)} changed lines, got {len(raw_diffs)}')
    if any(not a.lstrip().startswith('VOLPAN ') or not b.lstrip().startswith('VOLPAN ') for _,a,b in raw_diffs): raise RuntimeError('byte-line pan-only invariant changed a non-VOLPAN line')
    return {'input_project_sha256':sha(input_project),'output_project':str(output),'output_project_sha256':sha(output),'overhead_unchanged':True,'only_shell_volpan_changed':True,'changed_byte_lines':len(raw_diffs),'timing_fx_and_metadata_preserved':True}

def build_parser():
    parser=argparse.ArgumentParser(prog='reaperctl pan-drums',description=__doc__); parser.add_argument('--baseline',type=Path,default=Path(os.environ.get('REAPERCTL_BASELINE',BASE))); parser.add_argument('--project',type=Path); parser.add_argument('--track',action='append',dest='tracks'); parser.add_argument('--output-project',type=Path); parser.add_argument('--overwrite',action='store_true'); parser.add_argument('--analyze-only',action='store_true'); parser.add_argument('--json',action='store_true'); return parser

def main(argv=None):
    args=build_parser().parse_args(argv)
    try:data=core.load_baseline(args.baseline)
    except ValueError as exc:print(f'reaperctl: {exc}',file=sys.stderr);return 2
    checks=core.static_checks(data)
    if not all(check.ok for check in checks):return int(core.render_checks(checks,args.json,'baseline'))
    paths=core.workspace_paths(data); project=(args.project.expanduser().resolve() if args.project else paths['project'])
    try:
        overhead,results,base_tracks=analyze(project,args.tracks); report={'ok':True,'mode':'analyze','overhead_reference':overhead,'input_project':str(project),'input_project_sha256':sha(project),'timing_policy':'unchanged','polarity_policy':'unchanged','shells':results}
        if not args.analyze_only:
            if args.output_project is None:raise ValueError('--output-project is required unless --analyze-only')
            output=args.output_project.expanduser().resolve(); changes=rewrite_top_level_pans(project,output,results,args.overwrite); report['mode']='applied'; report['changes']=changes; report['verification']=verify_pan_only(project,output,overhead,results,base_tracks)
    except ValueError as exc:print(f'reaperctl: {exc}',file=sys.stderr);return 2
    except RuntimeError as exc:print(f'reaperctl: {exc}',file=sys.stderr);return 4
    if args.json:print(json.dumps(report,indent=2))
    else:
        print(f'Drum pan {report["mode"]}: VERIFIED'); print(f'OH reference: {overhead}')
        for result in results:print(f'{result["track"]}: {result["pan_percent"]:+.3f}% | {result["accepted_hits"]} hit(s) | spread {result["pan_mad"]:.4f}' + (' | Tom 1 anchor set' if result['tom1_self_anchor'] else ''))
        if 'verification' in report:print(f'Output: {report["verification"]["output_project"]}')
    return 0
if __name__=='__main__':raise SystemExit(main())
