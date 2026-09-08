#!/usr/bin/env python3
"""Analyze and non-destructively align simple close drum shells to stereo overhead arrivals."""
from __future__ import annotations
import argparse, hashlib, importlib.machinery, importlib.util, json, math, os, re, shutil, subprocess, sys, tempfile, wave
from pathlib import Path
from typing import Any

ROOT=Path(__file__).resolve().parents[1]; CORE=ROOT/'bin'/'reaperctl-core'; BASE=ROOT/'BASELINE.json'
SCAN_SR=2000; SCAN_BIN_SEC=.005; MAX_EVENTS=8; MIN_EVENT_GAP_SEC=.120
COARSE_SR=8000; COARSE_PRE_SEC=.006; COARSE_POST_SEC=.024; SEARCH_SEC=.025
FINE_SR=96000; FINE_PRE_SEC=.004; FINE_POST_SEC=.010; FINE_RADIUS_SEC=.0008
MAX_ABS_OFFSET_SEC=.050; MIN_ACCEPTED_SCORE=.035
JSFX_TEXT='''desc:AI Drum Shell Phase Align
// Non-destructive shell-to-overhead time alignment.
// Positive values delay this shell track. Negative values use PDC to advance it.
// Generated for the local REAPER 7.79 workspace.

slider1:0<-100,100,0.001>Shell alignment offset (ms)

in_pin:left input
in_pin:right input
out_pin:left output
out_pin:right output

@init
bpos = 0;
bufsize = max(1024, ceil(srate * 0.25));
pdc_top_ch = 2;
pdc_bot_ch = 0;
ext_tail_size = srate;

@slider
requested = slider1 * srate * 0.001;
requested >= 0 ? requested = floor(requested + 0.5) : requested = ceil(requested - 0.5);
requested < 0 ? (
  pdc_delay = -requested;
  delaylen = 0;
) : (
  pdc_delay = 0;
  delaylen = requested;
);

@sample
bpos[0] = spl0;
bpos[1] = spl1;

rdpos = bpos - delaylen * 2;
rdpos < 0 ? rdpos += bufsize * 2;

spl0 = rdpos[0];
spl1 = rdpos[1];

bpos += 2;
bpos >= bufsize * 2 ? bpos = 0;
'''

def load_core():
    loader=importlib.machinery.SourceFileLoader('reaperctl_align_core',str(CORE)); spec=importlib.util.spec_from_loader(loader.name,loader)
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
        if self.width!=3 or self.sr!=48000 or self.ch not in (1,2):
            raise ValueError(f'initial align-drums contract requires 48 kHz, 24-bit, mono/stereo WAVE: {path}')
        b=memoryview(raw); values=[]
        for i in range(0,len(raw),3):
            v=b[i]|(b[i+1]<<8)|(b[i+2]<<16); v=v-0x1000000 if v&0x800000 else v; values.append(v/8388608.0)
        self.data=[values[c::self.ch] for c in range(self.ch)]
    def sample(self,c:int,t:float)->float:
        x=t*self.sr
        if x<0 or x>self.frames-1: return 0.0
        i=int(math.floor(x)); frac=x-i; arr=self.data[min(c,self.ch-1)]
        if i>=self.frames-1: return arr[i]
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
def derivative_abs(x): return [0.]+[abs(x[i]-x[i-1]) for i in range(1,len(x))]
def derivative_signed(x): return [0.]+[x[i]-x[i-1] for i in range(1,len(x))]
def norm_corr(x,y,start):
    if len(x)<4 or start<0 or start+len(x)>len(y): return 0.0
    xy=xx=yy=0.0
    for i,a in enumerate(x):
        b=y[start+i]; xy+=a*b; xx+=a*a; yy+=b*b
    den=math.sqrt(xx*yy); return 0.0 if den<1e-20 else xy/den
def median(values):
    if not values: return None
    values=sorted(values); n=len(values); return values[n//2] if n%2 else .5*(values[n//2-1]+values[n//2])

def detect_events(audio:Audio):
    samples=mono(*audio.read(0,audio.frames/audio.sr,SCAN_SR)); bin_frames=max(1,int(SCAN_BIN_SEC*SCAN_SR+.5)); candidates=[]; i=0
    while i<len(samples):
        last=min(len(samples),i+bin_frames); segment=samples[i:last]
        if segment:
            j=max(range(len(segment)),key=lambda k:abs(segment[k])); amp=abs(segment[j])
            if amp>1e-6: candidates.append((amp,(i+j)/SCAN_SR))
        i=last
    candidates.sort(reverse=True); chosen=[]
    for amp,t in candidates:
        if all(abs(t-e[1])>=MIN_EVENT_GAP_SEC for e in chosen):
            chosen.append((amp,t))
            if len(chosen)>=MAX_EVENTS: break
    return sorted(chosen,key=lambda x:x[1])

def best_lag_for_hit(shell:Audio,overhead:Audio,hit:float):
    shell_start=hit-COARSE_PRE_SEC; duration=COARSE_PRE_SEC+COARSE_POST_SEC
    sx=derivative_abs(mono(*shell.read(shell_start,duration,COARSE_SR)))
    left,right=overhead.read(shell_start-SEARCH_SEC,duration+2*SEARCH_SEC,COARSE_SR); oh=[derivative_abs(left),derivative_abs(right)]
    search_n=int(SEARCH_SEC*COARSE_SR+.5); best_score=-1.0; best_lag=0; best_ch=0
    for lag in range(-search_n,search_n+1):
        start=search_n+lag
        for ch in range(2):
            score=norm_corr(sx,oh[ch],start)
            if score>best_score: best_score=score; best_lag=lag; best_ch=ch
    coarse=best_lag/COARSE_SR; fine_start=hit-FINE_PRE_SEC; fine_duration=FINE_PRE_SEC+FINE_POST_SEC
    fsx=derivative_signed(mono(*shell.read(fine_start,fine_duration,FINE_SR))); radius=int(FINE_RADIUS_SEC*FINE_SR+.5)
    center=int(coarse*FINE_SR+(.5 if coarse>=0 else -.5)); fine_search=abs(coarse)+FINE_RADIUS_SEC+2/FINE_SR
    left,right=overhead.read(fine_start-fine_search,fine_duration+2*fine_search,FINE_SR); foh=[derivative_signed(left),derivative_signed(right)]
    base=int(fine_search*FINE_SR+.5); best_abs=-1.0; result=(center,0.0,best_ch,1)
    for lag in range(center-radius,center+radius+1):
        start=base+lag
        for ch in range(2):
            score=norm_corr(fsx,foh[ch],start)
            if abs(score)>best_abs: best_abs=abs(score); result=(lag,best_abs,ch,-1 if score<0 else 1)
    return result[0]/FINE_SR,result[1],result[2]+1,result[3]

def estimate_offset(shell:Audio,overhead:Audio):
    events=detect_events(shell); measurements=[]
    for _,t in events:
        lag,score,ch,polarity=best_lag_for_hit(shell,overhead,t)
        if abs(lag)<=MAX_ABS_OFFSET_SEC and score>=MIN_ACCEPTED_SCORE:
            measurements.append({'lag':lag,'score':score,'ch':ch,'polarity':polarity,'time':t})
    if not measurements: return None,events,[]
    center=median([m['lag'] for m in measurements]); mad=median([abs(m['lag']-center) for m in measurements]) or 0.0; tolerance=max(.00035,3*mad)
    kept=[m for m in measurements if abs(m['lag']-center)<=tolerance] or measurements
    return median([m['lag'] for m in kept]),events,kept

def parse_tracks(project:Path)->dict[str,dict[str,Any]]:
    lines=project.read_text().splitlines(); tracks={}; i=0
    while i<len(lines):
        if not lines[i].startswith('  <TRACK'): i+=1; continue
        start=i; depth=0; j=i
        while j<len(lines):
            stripped=lines[j].lstrip()
            if stripped.startswith('<'): depth+=1
            if stripped=='>':
                depth-=1
                if depth==0: j+=1; break
            j+=1
        chunk=lines[start:j]; name=None; item=[]; in_item=False; item_depth=0
        for line in chunk[1:]:
            stripped=line.strip()
            if stripped.startswith('<ITEM'): in_item=True; item_depth=1; item=[line]; continue
            if in_item:
                item.append(line)
                if stripped.startswith('<'): item_depth+=1
                if stripped=='>':
                    item_depth-=1
                    if item_depth==0: in_item=False
                continue
            if name is None and stripped.startswith('NAME '): name=stripped[5:].strip('"')
        if name:
            matches=[re.match(r'^\s*FILE "(.*)"$',line) for line in chunk]; files=[m.group(1) for m in matches if m]
            item_state=[line.strip() for line in item if line.strip().startswith(('POSITION ','LENGTH ','SOFFS ','PLAYRATE '))]
            pans=[line.strip() for line in chunk if line.strip().startswith('VOLPAN ')]
            tracks[name]={'chunk':chunk,'file':Path(files[0]) if len(files)==1 else None,'files':files,'item_state':item_state,'pans':pans}
        i=j
    return tracks

def validate_contract(tracks,shell_names,overhead_name):
    for name in [overhead_name,*shell_names]:
        track=tracks[name]
        if track['file'] is None or not track['file'].is_file(): raise ValueError(f'initial align-drums contract requires exactly one existing WAVE source on {name}')
        state=' '.join(track['item_state'])
        if 'POSITION 0' not in state or 'SOFFS 0' not in state or 'PLAYRATE 1 ' not in state:
            raise ValueError(f'initial align-drums contract requires POSITION=0, SOFFS=0, PLAYRATE=1 on {name}')

def analyze(project:Path,selected:list[str]|None):
    tracks=parse_tracks(project); overheads=[name for name in tracks if is_overhead_name(name)]
    if len(overheads)!=1: raise ValueError(f'initial align-drums contract requires exactly one stereo OH track; found {overheads}')
    shells=selected or [name for name in tracks if is_shell_name(name)]
    if not shells: raise ValueError('no shell tracks found')
    for name in shells:
        if name not in tracks or not is_shell_name(name): raise ValueError(f'not an admitted shell track: {name}')
    validate_contract(tracks,shells,overheads[0]); overhead=Audio(tracks[overheads[0]]['file'])
    if overhead.ch!=2: raise ValueError('OH source must be stereo')
    results=[]
    for name in shells:
        offset,events,kept=estimate_offset(Audio(tracks[name]['file']),overhead)
        if offset is None: continue
        counts={1:0,2:0}; avg=0.0; polarity_votes=0
        for measurement in kept:
            counts[measurement['ch']]+=1; avg+=measurement['score']; polarity_votes+=measurement['polarity']
        avg=avg/len(kept) if kept else 0.0; dominant=2 if counts[2]>counts[1] else 1
        results.append({'track':name,'offset_ms':offset*1000,'accepted_hits':len(kept),'candidate_hits':len(events),'dominant_oh_channel':dominant,'average_score':avg,'inverse_polarity_dominant':polarity_votes<0,'tom1_self_anchor':is_tom1_name(name),'measurements':[{**m,'lag_ms':m['lag']*1000} for m in kept]})
    if not results: raise RuntimeError('no shell track produced a reliable shell->OH match')
    return overheads[0],results,tracks

def disposable_config(resource:Path,root:Path):
    config=root/'config'; target=config/'REAPER'; shutil.copytree(resource,target); ini=target/'reaper.ini'
    if ini.exists():
        lines=ini.read_text(errors='replace').splitlines(); lines=[line for line in lines if not re.match(r'^csurf_(?:cnt|\d+)=',line)]; lines.insert(lines.index('[reaper]')+1,'csurf_cnt=0'); ini.write_text('\n'.join(lines)+'\n')
    fx=target/'Effects'/'utility'; fx.mkdir(parents=True,exist_ok=True); (fx/'AI_Drum_Shell_Phase_Align').write_text(JSFX_TEXT)
    return config

def apply(project:Path,output:Path,resource:Path,reaper_bin:Path,display:str,results:list[dict],overwrite:bool,timeout:float):
    if output.exists() and not overwrite: raise ValueError(f'output project exists; use --overwrite: {output}')
    output.parent.mkdir(parents=True,exist_ok=True); shutil.copy2(project,output); canonical_before=sha(project); root=Path(tempfile.mkdtemp(prefix='reaperctl-align-'))
    try:
        config=disposable_config(resource,root); home=root/'home'; home.mkdir(); status=root/'status.txt'; lua=root/'apply.lua'
        rows=', '.join(f'[{json.dumps(r["track"])}]={r["offset_ms"]:.12f}' for r in results)
        lua.write_text(f'''local offsets={{{rows}}}\nlocal fx="JS: utility/AI_Drum_Shell_Phase_Align"\nlocal f=io.open({json.dumps(str(status))},'w'); local changed=0\nfor i=0,reaper.CountTracks(0)-1 do local tr=reaper.GetTrack(0,i); local _,n=reaper.GetTrackName(tr); local ms=offsets[n]; if ms~=nil then local idx=reaper.TrackFX_AddByName(tr,fx,false,-1); if idx<0 then idx=reaper.TrackFX_AddByName(tr,fx,false,0) end; if idx<0 then f:write('ERR ',n,' jsfx-not-found\\n') else reaper.TrackFX_SetParam(tr,idx,0,ms); reaper.TrackFX_SetEnabled(tr,idx,true); reaper.GetSetMediaTrackInfo_String(tr,'P_EXT:AI_DRUM_ALIGN_DELAY_MS',string.format('%.6f',ms),true); f:write('OK ',n,' ',string.format('%.6f',ms),'\\n'); changed=changed+1 end end end\nreaper.Main_SaveProject(0,false); f:write('CHANGED ',changed,'\\n'); f:close(); reaper.Main_OnCommand(40004,0)\n''')
        env=os.environ.copy(); env.update(HOME=str(home),XDG_CONFIG_HOME=str(config),DISPLAY=display)
        try: proc=subprocess.run([str(reaper_bin),'-newinst','-nosplash',str(output),str(lua)],text=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE,env=env,timeout=timeout)
        except subprocess.TimeoutExpired as exc: raise RuntimeError(f'disposable REAPER alignment timed out after {timeout}s') from exc
        if proc.returncode: raise RuntimeError(f'disposable REAPER alignment exited {proc.returncode}: {(proc.stderr or proc.stdout)[-1000:]}')
        text=status.read_text() if status.exists() else ''
        if f'CHANGED {len(results)}' not in text or 'ERR ' in text: raise RuntimeError(f'alignment apply status failed: {text!r}')
    finally: shutil.rmtree(root,ignore_errors=True)
    if sha(project)!=canonical_before: raise RuntimeError('canonical project changed during disposable alignment')

def verify_output(canonical:Path,output:Path,overhead_name:str,results:list[dict],base_tracks):
    aligned=parse_tracks(output); expected={r['track']:r for r in results}
    for name in [overhead_name,*expected]:
        if name not in aligned: raise RuntimeError(f'aligned project missing track {name}')
        if aligned[name]['item_state']!=base_tracks[name]['item_state'] or aligned[name]['files']!=base_tracks[name]['files'] or aligned[name]['pans']!=base_tracks[name]['pans']:
            raise RuntimeError(f'track media/pan continuity regression: {name}')
    if any('AI_Drum_Shell_Phase_Align' in line for line in aligned[overhead_name]['chunk']): raise RuntimeError('overhead reference received alignment FX')
    for name,result in expected.items():
        chunk='\n'.join(aligned[name]['chunk']); marker=f'AI_DRUM_ALIGN_DELAY_MS {result["offset_ms"]:.6f}'
        if 'AI_Drum_Shell_Phase_Align' not in chunk or marker not in chunk: raise RuntimeError(f'alignment FX/offset missing for {name}: expected {marker}')
    return {'output_project':str(output),'output_project_sha256':sha(output),'canonical_project_sha256':sha(canonical),'overhead_unchanged':True,'shell_media_and_pan_unchanged':True}

def build_parser():
    parser=argparse.ArgumentParser(prog='reaperctl align-drums',description=__doc__); parser.add_argument('--baseline',type=Path,default=Path(os.environ.get('REAPERCTL_BASELINE',BASE))); parser.add_argument('--track',action='append',dest='tracks'); parser.add_argument('--output-project',type=Path); parser.add_argument('--overwrite',action='store_true'); parser.add_argument('--analyze-only',action='store_true'); parser.add_argument('--timeout',type=float,default=20); parser.add_argument('--json',action='store_true'); return parser

def main(argv=None):
    args=build_parser().parse_args(argv)
    try: data=core.load_baseline(args.baseline)
    except ValueError as exc: print(f'reaperctl: {exc}',file=sys.stderr); return 2
    checks=core.static_checks(data)
    if not all(check.ok for check in checks): return int(core.render_checks(checks,args.json,'baseline'))
    paths=core.workspace_paths(data); project=paths['project']
    try:
        overhead,results,base_tracks=analyze(project,args.tracks)
        report={'ok':True,'mode':'analyze','overhead_reference':overhead,'canonical_project':str(project),'canonical_project_sha256':sha(project),'pan_policy':'unchanged','polarity_policy':'timing correlation only; no polarity flip','shells':results}
        if not args.analyze_only:
            if args.output_project is None: raise ValueError('--output-project is required unless --analyze-only')
            output=args.output_project.expanduser().resolve(); apply(project,output,paths['resource'],paths['reaper'],str(paths['display']),results,args.overwrite,args.timeout); report['mode']='applied'; report['verification']=verify_output(project,output,overhead,results,base_tracks)
    except ValueError as exc: print(f'reaperctl: {exc}',file=sys.stderr); return 2
    except RuntimeError as exc: print(f'reaperctl: {exc}',file=sys.stderr); return 4
    if args.json: print(json.dumps(report,indent=2))
    else:
        print(f'Drum alignment {report["mode"]}: VERIFIED'); print(f'OH reference: {overhead}')
        for result in results: print(f'{result["track"]}: {result["offset_ms"]:+.6f} ms | {result["accepted_hits"]} hit(s) | OH {result["dominant_oh_channel"]} | score {result["average_score"]:.3f}' + (' | Tom 1 self-anchor' if result['tom1_self_anchor'] else ''))
        if 'verification' in report: print(f'Output: {report["verification"]["output_project"]}')
    return 0
if __name__=='__main__': raise SystemExit(main())
