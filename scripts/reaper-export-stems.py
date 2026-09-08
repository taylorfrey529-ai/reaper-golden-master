#!/usr/bin/env python3
"""Verified native selected-track stem export using a disposable REAPER 7.79 Render dialog."""
from __future__ import annotations
import argparse, ctypes, hashlib, importlib.machinery, importlib.util, json, os, re, shutil, subprocess, sys, tempfile, time, wave
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]; CORE=ROOT/'bin'/'reaperctl-core'; BASE=ROOT/'BASELINE.json'
DIALOG=(714,752); MENU=(191,122); SRC=(164,24); STEM_ITEM=(93,33); RENDER=(499,724)

def load_core():
    l=importlib.machinery.SourceFileLoader('reaperctl_stems_core',str(CORE)); s=importlib.util.spec_from_loader(l.name,l)
    if s is None: raise RuntimeError(f'cannot load {CORE}')
    m=importlib.util.module_from_spec(s); sys.modules[l.name]=m; l.exec_module(m); return m
core=load_core()

def sha(path:Path)->str:
    h=hashlib.sha256()
    with path.open('rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''): h.update(b)
    return h.hexdigest()

def verify_wav(path:Path,allow_silent:bool)->dict:
    if not path.is_file() or path.stat().st_size<=44: raise RuntimeError(f'missing/truncated stem: {path}')
    try:
        with wave.open(str(path),'rb') as w:
            ch,rate,width,frames,comp=w.getnchannels(),w.getframerate(),w.getsampwidth(),w.getnframes(),w.getcomptype(); nonzero=False
            while True:
                b=w.readframes(65536)
                if not b: break
                if any(b): nonzero=True; break
    except (wave.Error,EOFError) as e: raise RuntimeError(f'unreadable PCM WAVE {path}: {e}') from e
    if ch!=2: raise RuntimeError(f'stem channel regression for {path.name}: {ch}')
    if rate!=48000: raise RuntimeError(f'stem sample-rate regression for {path.name}: {rate}')
    if width!=3: raise RuntimeError(f'stem sample-width regression for {path.name}: {width}')
    if comp!='NONE': raise RuntimeError(f'stem compression regression for {path.name}: {comp}')
    if frames<=0: raise RuntimeError(f'stem has no frames: {path.name}')
    if not allow_silent and not nonzero: raise RuntimeError(f'stem is digital silence: {path.name}')
    return {'path':str(path),'name':path.name,'size_bytes':path.stat().st_size,'sha256':sha(path),'channels':ch,'sample_rate_hz':rate,'sample_width_bytes':width,'frames':frames,'duration_seconds':frames/rate,'non_silent':nonzero}

def windows(display:str,title:str)->set[str]:
    env=os.environ.copy(); env['DISPLAY']=display
    try: r=subprocess.run(['xwininfo','-root','-tree'],text=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE,env=env,timeout=2)
    except (OSError,subprocess.TimeoutExpired): return set()
    if r.returncode: return set()
    pat=re.compile(r'^\s*(0x[0-9A-Fa-f]+)\s+"([^"]*)"')
    return {m.group(1) for line in r.stdout.splitlines() if (m:=pat.match(line)) and m.group(2)==title}

def geometry(display:str,wid:str)->tuple[int,int,int,int]:
    env=os.environ.copy(); env['DISPLAY']=display
    r=subprocess.run(['xwininfo','-id',wid],text=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE,env=env,timeout=2)
    if r.returncode: raise RuntimeError(f'xwininfo failed for {wid}: {r.stderr.strip()}')
    vals=[]
    for field in ('Absolute upper-left X:','Absolute upper-left Y:','Width:','Height:'):
        m=re.search(re.escape(field)+r'\s*(-?\d+)',r.stdout)
        if not m: raise RuntimeError(f'cannot parse {field} for {wid}')
        vals.append(int(m.group(1)))
    return tuple(vals)  # type: ignore[return-value]

def wait_window(display:str,title:str,before:set[str],timeout:float)->str:
    end=time.monotonic()+timeout
    while time.monotonic()<end:
        new=windows(display,title)-before
        if len(new)==1: return next(iter(new))
        if len(new)>1: raise RuntimeError(f'ambiguous new {title} windows: {sorted(new)}')
        time.sleep(.05)
    raise RuntimeError(f'timed out waiting for {title}')

class Clicker:
    def __init__(self,display:str):
        try: self.x=ctypes.CDLL('libX11.so.6'); self.t=ctypes.CDLL('libXtst.so.6')
        except OSError as e: raise RuntimeError(f'X11/XTest unavailable: {e}') from e
        self.x.XOpenDisplay.argtypes=[ctypes.c_char_p]; self.x.XOpenDisplay.restype=ctypes.c_void_p; self.x.XFlush.argtypes=[ctypes.c_void_p]
        self.t.XTestFakeMotionEvent.argtypes=[ctypes.c_void_p,ctypes.c_int,ctypes.c_int,ctypes.c_int,ctypes.c_ulong]
        self.t.XTestFakeButtonEvent.argtypes=[ctypes.c_void_p,ctypes.c_uint,ctypes.c_int,ctypes.c_ulong]
        self.d=self.x.XOpenDisplay(display.encode())
        if not self.d: raise RuntimeError(f'cannot open X11 display {display}')
    def click(self,x:int,y:int):
        self.t.XTestFakeMotionEvent(self.d,-1,x,y,0); self.x.XFlush(self.d); time.sleep(.08)
        self.t.XTestFakeButtonEvent(self.d,1,1,0); self.t.XTestFakeButtonEvent(self.d,1,0,0); self.x.XFlush(self.d)

def valid_names(names:list[str]):
    safe=re.compile(r'^[A-Za-z0-9][A-Za-z0-9 ._()-]*$')
    for n in names:
        if not safe.fullmatch(n) or n.endswith((' ','.')): raise ValueError(f'initial export-stems contract requires filename-safe track names: {n!r}')

def expected(names:list[str],out:Path)->list[Path]: valid_names(names); return [out/f'{n}.wav' for n in names]

def status(path:Path)->dict[str,str]:
    try: lines=path.read_text().splitlines()
    except OSError: return {}
    return {k:v for line in lines if '=' in line for k,v in [line.split('=',1)]}

def lua(names:list[str],out:Path,st:Path)->str:
    wanted=','.join(f'[{json.dumps(n)}]=true' for n in names); q=lambda x:json.dumps(str(x))
    return f'''local wanted={{{wanted}}}\nlocal st={q(st)}; local tmp={q(str(st)+'.tmp')}\nlocal function write(e) local f=io.open(tmp,'w'); if f then f:write('settings=',tostring(reaper.GetSetProjectInfo(0,'RENDER_SETTINGS',0,false)),'\\nerror=',e or '','\\n'); f:close(); os.rename(tmp,st) end end\nlocal found={{}}\nfor i=0,reaper.CountTracks(0)-1 do local tr=reaper.GetTrack(0,i); local _,n=reaper.GetTrackName(tr); local y=wanted[n]==true; reaper.SetMediaTrackInfo_Value(tr,'I_SELECTED',y and 1 or 0); if y then if found[n] then write('duplicate track: '..n); return end; found[n]=true end end\nfor n,_ in pairs(wanted) do if not found[n] then write('track not found: '..n); return end end\nreaper.GetSetProjectInfo(0,'RENDER_SETTINGS',2,true); reaper.GetSetProjectInfo(0,'RENDER_SRATE',48000,true); reaper.GetSetProjectInfo(0,'RENDER_CHANNELS',2,true); reaper.GetSetProjectInfo(0,'RENDER_BOUNDSFLAG',1,true)\nreaper.GetSetProjectInfo_String(0,'RENDER_FILE',{q(out)},true); reaper.GetSetProjectInfo_String(0,'RENDER_PATTERN','$track',true); reaper.Main_OnCommand(40015,0)\nlocal function loop() write(''); reaper.defer(loop) end; loop()\n'''

def isolated_config(resource:Path,root:Path)->Path:
    home=root/'config'; target=home/'REAPER'; shutil.copytree(resource,target); ini=target/'reaper.ini'
    if ini.is_file():
        lines=ini.read_text(errors='replace').splitlines(); lines=[x for x in lines if not re.match(r'^csurf_(?:cnt|\d+)=',x)]; lines.insert(lines.index('[reaper]')+1,'csurf_cnt=0'); ini.write_text('\n'.join(lines)+'\n')
    return home

def wait_stem_mode(st:Path,timeout:float):
    end=time.monotonic()+timeout; last={}
    while time.monotonic()<end:
        last=status(st)
        if last.get('error'): raise RuntimeError(last['error'])
        if last.get('settings','').startswith('2'): return
        time.sleep(.05)
    raise RuntimeError(f'timed out waiting for native stem mode; status={last}')

def stop(proc:subprocess.Popen):
    if proc.poll() is not None:return
    proc.terminate()
    try: proc.wait(2)
    except subprocess.TimeoutExpired: proc.kill(); proc.wait(2)

def export(data:dict,names:list[str],out:Path,timeout:float,allow_silent:bool)->dict:
    if not names: raise ValueError('at least one --track is required')
    if len(set(names))!=len(names): raise ValueError('duplicate --track values are not allowed')
    valid_names(names); p=core.workspace_paths(data); project,reaper_bin,resource,display=p['project'],p['reaper'],p['resource'],str(p['display'])
    if not project.is_file() or not reaper_bin.is_file() or not resource.is_dir(): raise ValueError('canonical REAPER project/runtime/resource path is incomplete')
    if shutil.which('xwininfo') is None: raise RuntimeError('xwininfo is required')
    out=out.expanduser().resolve()
    if out.exists() and any(out.iterdir()): raise ValueError(f'output directory must be absent or empty: {out}')
    out.mkdir(parents=True,exist_ok=True); before=sha(project); oldr=windows(display,'Render to File'); oldm=windows(display,'menu')
    sess=tempfile.TemporaryDirectory(prefix='reaperctl-stems-'); root=Path(sess.name); proc=None; tmpp=None
    try:
        cfg=isolated_config(resource,root); st=root/'status.txt'; script=root/'export.lua'; script.write_text(lua(names,out,st))
        with tempfile.NamedTemporaryFile(mode='wb',suffix='.RPP',prefix='.reaperctl-stems-',dir=project.parent,delete=False) as f: tmpp=Path(f.name); f.write(project.read_bytes())
        env=os.environ.copy(); env.update(HOME=str(root/'home'),XDG_CONFIG_HOME=str(cfg),DISPLAY=display); (root/'home').mkdir()
        proc=subprocess.Popen([str(reaper_bin),'-newinst','-nosplash',str(tmpp),str(script)],text=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE,env=env)
        rw=wait_window(display,'Render to File',oldr,min(timeout,10)); x,y,w,h=geometry(display,rw)
        if (w,h)!=DIALOG: raise RuntimeError(f'unexpected REAPER 7.79 Render dialog geometry {(w,h)}')
        c=Clicker(display); c.click(x+SRC[0],y+SRC[1]); mw=wait_window(display,'menu',oldm,2); mx,my,ww,hh=geometry(display,mw)
        if (ww,hh)!=MENU: raise RuntimeError(f'unexpected REAPER source menu geometry {(ww,hh)}')
        c.click(mx+STEM_ITEM[0],my+STEM_ITEM[1]); wait_stem_mode(st,3); targets=expected(names,out); c.click(x+RENDER[0],y+RENDER[1])
        end=time.monotonic()+timeout
        while time.monotonic()<end:
            if all(t.is_file() and t.stat().st_size>44 for t in targets): time.sleep(.25); break
            if proc.poll() is not None: raise RuntimeError(f'disposable REAPER exited early: {proc.returncode}')
            time.sleep(.05)
        else: raise RuntimeError(f'timed out waiting for stems: {targets}')
        actual=sorted(x.resolve() for x in out.glob('*.wav')); exp=sorted(x.resolve() for x in targets)
        if actual!=exp: raise RuntimeError(f'unexpected stem file set: expected={exp}, actual={actual}')
        artifacts=[verify_wav(x,allow_silent) for x in targets]
    finally:
        if proc is not None: stop(proc)
        if tmpp is not None: tmpp.unlink(missing_ok=True)
        sess.cleanup()
    after=sha(project)
    if after!=before: raise RuntimeError(f'canonical project changed during stem export: {before} -> {after}')
    return {'ok':True,'tracks':names,'canonical_project':str(project),'canonical_project_sha256_before':before,'canonical_project_sha256_after':after,'output_dir':str(out),'stems':artifacts}

def parser():
    p=argparse.ArgumentParser(prog='reaperctl export-stems',description=__doc__); p.add_argument('--baseline',type=Path,default=Path(os.environ.get('REAPERCTL_BASELINE',BASE))); p.add_argument('--track',action='append',dest='tracks',required=True); p.add_argument('--output-dir',type=Path,required=True); p.add_argument('--timeout',type=float,default=30); p.add_argument('--allow-silent',action='store_true'); p.add_argument('--json',action='store_true'); return p

def main(argv=None):
    a=parser().parse_args(argv)
    try: data=core.load_baseline(a.baseline)
    except ValueError as e: print(f'reaperctl: {e}',file=sys.stderr); return 2
    checks=core.static_checks(data)
    if not all(c.ok for c in checks): return int(core.render_checks(checks,a.json,'baseline'))
    try: r=export(data,a.tracks,a.output_dir,a.timeout,a.allow_silent)
    except ValueError as e: print(f'reaperctl: {e}',file=sys.stderr); return 2
    except RuntimeError as e: print(f'reaperctl: {e}',file=sys.stderr); return 4
    if a.json: print(json.dumps(r,indent=2))
    else:
        print(f"Stem export: VERIFIED ({len(r['stems'])} files)")
        for s in r['stems']: print(f"{s['name']}: {s['sample_rate_hz']} Hz / {s['channels']}ch / {s['sample_width_bytes']*8}-bit / {s['sha256']}")
        print(f"Canonical project unchanged: {r['canonical_project_sha256_before']}")
    return 0
if __name__=='__main__': raise SystemExit(main())
