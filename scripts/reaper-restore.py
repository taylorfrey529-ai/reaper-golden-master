#!/usr/bin/env python3
"""Restore and verify a continuation backup into an isolated target tree."""
from __future__ import annotations
import argparse, hashlib, json, os, shutil, stat, sys, tarfile, zipfile
from pathlib import Path, PurePosixPath

EXPECTED_AUDIO_ZIP_SHA='093f590ba02b0284dc676d7f8ae499ead6fd93316524f7872cfa3c6fda0660bd'
EXPECTED_REAPER_SHA='cee99a74fdd9fc87974c96ea334a50afff4ca8d3121591aed218057bb38185e4'
REAPER_PREFIX='audio/REAPER/7.79/linux-x86_64/pristine/reaper_linux_x86_64/REAPER/'


def sha_bytes(data:bytes)->str:return hashlib.sha256(data).hexdigest()
def sha(path:Path)->str:
    digest=hashlib.sha256()
    with path.open('rb') as handle:
        for chunk in iter(lambda:handle.read(1024*1024),b''):digest.update(chunk)
    return digest.hexdigest()
def canonical_bytes(obj)->bytes:return json.dumps(obj,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode('utf-8')
def verify_snapshot_id(manifest:dict)->bool:
    supplied=manifest.get('snapshot_id');body=dict(manifest);body.pop('snapshot_id',None);return supplied=='sha256:'+sha_bytes(canonical_bytes(body))

def safe_relative(value:str)->PurePosixPath:
    path=PurePosixPath(value)
    if path.is_absolute() or not path.parts or any(part in ('','.', '..') for part in path.parts):raise RuntimeError(f'unsafe archive path: {value!r}')
    return path

def target_path(target:Path,archive_path:str)->Path:
    rel=safe_relative(archive_path)
    if rel.parts[0] not in {'workspace','virtual-apollo','evidence'}:raise RuntimeError(f'unsupported continuation path: {archive_path}')
    return target.joinpath(*rel.parts)

def load_and_verify_backup(backup:Path)->tuple[dict,dict]:
    if not backup.is_file():raise ValueError(f'backup not found: {backup}')
    with tarfile.open(backup,'r:gz') as tar:
        members={member.name:member for member in tar.getmembers()}
        if 'SNAPSHOT.json' not in members or 'BACKUP-MANIFEST.json' not in members:raise RuntimeError('backup metadata members missing')
        snapshot_member=tar.extractfile(members['SNAPSHOT.json']); manifest_member=tar.extractfile(members['BACKUP-MANIFEST.json'])
        if snapshot_member is None or manifest_member is None:raise RuntimeError('backup metadata members unreadable')
        snapshot=json.loads(snapshot_member.read().decode('utf-8')); backup_meta=json.loads(manifest_member.read().decode('utf-8'))
        if not verify_snapshot_id(snapshot):raise RuntimeError('embedded snapshot ID verification failed')
        inventory=snapshot.get('inventory')
        if not isinstance(inventory,list):raise RuntimeError('snapshot inventory is invalid')
        expected={'SNAPSHOT.json','BACKUP-MANIFEST.json'}|{'payload/'+str(safe_relative(entry['archive_path'])) for entry in inventory}
        if set(members)!=expected:raise RuntimeError(f'backup inventory mismatch: missing={sorted(expected-set(members))}, extra={sorted(set(members)-expected)}')
        if backup_meta.get('snapshot_id')!=snapshot.get('snapshot_id'):raise RuntimeError('backup/snapshot identity mismatch')
        if backup_meta.get('artifact_count')!=len(inventory):raise RuntimeError('backup artifact count mismatch')
        if backup_meta.get('golden_master_id')!=snapshot.get('golden_master',{}).get('id'):raise RuntimeError('backup Golden Master binding mismatch')
        for entry in inventory:
            name='payload/'+entry['archive_path']; member=members[name]
            if not member.isfile():raise RuntimeError(f'backup payload is not a regular file: {name}')
            handle=tar.extractfile(member)
            if handle is None:raise RuntimeError(f'backup member unreadable: {name}')
            data=handle.read(); expected_mode=int(str(entry.get('mode','0o644')),8)
            if len(data)!=entry['bytes'] or sha_bytes(data)!=entry['sha256']:raise RuntimeError(f'backup member hash mismatch: {entry["archive_path"]}')
            if stat.S_IMODE(member.mode)!=expected_mode:raise RuntimeError(f'backup member mode mismatch: {entry["archive_path"]}')
    return snapshot,backup_meta

def write_payload(backup:Path,target:Path,snapshot:dict)->None:
    with tarfile.open(backup,'r:gz') as tar:
        for entry in snapshot['inventory']:
            out=target_path(target,entry['archive_path']);out.parent.mkdir(parents=True,exist_ok=True)
            member=tar.extractfile('payload/'+entry['archive_path'])
            if member is None:raise RuntimeError(f'backup member unreadable: {entry["archive_path"]}')
            data=member.read();out.write_bytes(data);os.chmod(out,int(str(entry.get('mode','0o644')),8))

def extract_reaper_runtime(audio_zip:Path,target:Path)->None:
    reaper_root=target/'workspace'/'apps'/'REAPER';reaper_root.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(audio_zip,'r') as archive:
        matched=0
        for info in archive.infolist():
            if not info.filename.startswith(REAPER_PREFIX) or info.is_dir():continue
            relative=info.filename[len(REAPER_PREFIX):]
            rel=safe_relative(relative);out=reaper_root.joinpath(*rel.parts);out.parent.mkdir(parents=True,exist_ok=True)
            out.write_bytes(archive.read(info));mode=(info.external_attr>>16)&0o777
            if mode:os.chmod(out,mode)
            matched+=1
        if matched==0:raise RuntimeError('Golden Master audio payload contains no REAPER runtime files')

def verify_restored_target(target:Path,snapshot:dict,expected_reaper_sha:str)->dict:
    count=0;total=0
    for entry in snapshot['inventory']:
        path=target_path(target,entry['archive_path'])
        if not path.is_file():raise RuntimeError(f'restored file missing: {entry["archive_path"]}')
        if path.stat().st_size!=entry['bytes'] or sha(path)!=entry['sha256']:raise RuntimeError(f'restored file hash mismatch: {entry["archive_path"]}')
        if stat.S_IMODE(path.stat().st_mode)!=int(str(entry.get('mode','0o644')),8):raise RuntimeError(f'restored file mode mismatch: {entry["archive_path"]}')
        count+=1;total+=path.stat().st_size
    binary=target/'workspace'/'apps'/'REAPER'/'reaper'
    if not binary.is_file():raise RuntimeError('restored REAPER binary missing')
    binary_sha=sha(binary); binding=snapshot.get('runtime_binding',{})
    if binary_sha!=expected_reaper_sha or binary_sha!=binding.get('sha256'):raise RuntimeError(f'restored REAPER binary hash mismatch: {binary_sha}')
    if binary.stat().st_size!=binding.get('bytes'):raise RuntimeError('restored REAPER binary byte-size mismatch')
    return {'artifact_count':count,'artifact_bytes':total,'reaper_binary':str(binary),'reaper_binary_sha256':binary_sha}

def restore(backup:Path,audio_zip:Path,target:Path,overwrite:bool,expected_audio_sha:str=EXPECTED_AUDIO_ZIP_SHA,expected_reaper_sha:str=EXPECTED_REAPER_SHA)->dict:
    snapshot,backup_meta=load_and_verify_backup(backup)
    if not audio_zip.is_file():raise ValueError(f'Golden Master audio payload not found: {audio_zip}')
    audio_sha=sha(audio_zip)
    if audio_sha!=expected_audio_sha:raise RuntimeError(f'Golden Master audio payload SHA mismatch: {audio_sha}')
    if target.exists():
        if not overwrite:raise ValueError(f'target exists; use --overwrite: {target}')
        shutil.rmtree(target)
    target.mkdir(parents=True)
    try:
        write_payload(backup,target,snapshot);extract_reaper_runtime(audio_zip,target);verified=verify_restored_target(target,snapshot,expected_reaper_sha)
        recovery=target/'recovery';recovery.mkdir();(recovery/'SNAPSHOT.json').write_text(json.dumps(snapshot,indent=2,sort_keys=True)+'\n',encoding='utf-8');(recovery/'BACKUP-MANIFEST.json').write_text(json.dumps(backup_meta,indent=2,sort_keys=True)+'\n',encoding='utf-8')
    except Exception:
        shutil.rmtree(target,ignore_errors=True);raise
    return {'ok':True,'target':str(target),'snapshot_id':snapshot['snapshot_id'],'golden_master_id':snapshot.get('golden_master',{}).get('id'),'continuation_backup_sha256':sha(backup),'golden_master_audio_zip_sha256':audio_sha,**verified}

def build_parser():
    parser=argparse.ArgumentParser(prog='reaperctl restore',description=__doc__);parser.add_argument('--backup',type=Path,required=True);parser.add_argument('--audio-zip',type=Path,required=True);parser.add_argument('--target',type=Path,required=True);parser.add_argument('--overwrite',action='store_true');parser.add_argument('--json',action='store_true');return parser

def main(argv=None):
    args=build_parser().parse_args(argv)
    try:report=restore(args.backup.expanduser().resolve(),args.audio_zip.expanduser().resolve(),args.target.expanduser().resolve(),args.overwrite)
    except ValueError as exc:print(f'reaperctl: {exc}',file=sys.stderr);return 2
    except (RuntimeError,json.JSONDecodeError,tarfile.TarError,zipfile.BadZipFile,OSError) as exc:print(f'reaperctl: {exc}',file=sys.stderr);return 4
    if args.json:print(json.dumps(report,indent=2))
    else:print(f'Restore target: VERIFIED\nTarget: {report["target"]}\nSnapshot: {report["snapshot_id"]}\nREAPER: {report["reaper_binary_sha256"]}')
    return 0
if __name__=='__main__':raise SystemExit(main())
