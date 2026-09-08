#!/usr/bin/env python3
"""Create and verify a deterministic continuation backup from a verified snapshot manifest."""
from __future__ import annotations
import argparse, gzip, hashlib, io, json, sys, tarfile
from pathlib import Path


def sha_bytes(data:bytes)->str:return hashlib.sha256(data).hexdigest()
def sha(path:Path)->str:
    digest=hashlib.sha256()
    with path.open('rb') as handle:
        for chunk in iter(lambda:handle.read(1024*1024),b''):digest.update(chunk)
    return digest.hexdigest()
def canonical_bytes(obj)->bytes:return json.dumps(obj,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode('utf-8')
def verify_snapshot_id(manifest:dict)->bool:
    supplied=manifest.get('snapshot_id');body=dict(manifest);body.pop('snapshot_id',None);return supplied=='sha256:'+sha_bytes(canonical_bytes(body))

def tar_info(name:str,data:bytes,mode:int=0o644)->tarfile.TarInfo:
    info=tarfile.TarInfo(name);info.size=len(data);info.mode=mode;info.uid=0;info.gid=0;info.uname='root';info.gname='root';info.mtime=0;return info

def file_mode(value)->int:
    try:return int(str(value),8)
    except Exception:return 0o644

def backup_manifest(snapshot:dict,snapshot_path:Path)->dict:
    return {'schema_version':1,'kind':'reaper-continuation-backup','snapshot_id':snapshot['snapshot_id'],'snapshot_file_sha256':sha(snapshot_path),'golden_master_id':snapshot.get('golden_master',{}).get('id'),'artifact_count':len(snapshot['inventory']),'artifact_bytes':sum(item['bytes'] for item in snapshot['inventory']),'runtime_embedded':False,'runtime_recovery_policy':'restore exact REAPER runtime from admitted Golden Master; apply this archive for mutable continuation state','archive_format':'deterministic tar.gz; sorted members; uid/gid/mtime normalized'}

def verify_backup(archive:Path,snapshot:dict)->None:
    expected={'BACKUP-MANIFEST.json','SNAPSHOT.json'}|{'payload/'+entry['archive_path'] for entry in snapshot['inventory']}
    with tarfile.open(archive,'r:gz') as tar:
        names=set(tar.getnames())
        if names!=expected:raise RuntimeError(f'backup inventory mismatch: missing={sorted(expected-names)}, extra={sorted(names-expected)}')
        snap_member=tar.extractfile('SNAPSHOT.json')
        if snap_member is None:raise RuntimeError('embedded SNAPSHOT.json missing')
        embedded=json.loads(snap_member.read().decode('utf-8'))
        if embedded.get('snapshot_id')!=snapshot.get('snapshot_id') or not verify_snapshot_id(embedded):raise RuntimeError('embedded snapshot identity mismatch')
        manifest_member=tar.extractfile('BACKUP-MANIFEST.json')
        if manifest_member is None:raise RuntimeError('embedded BACKUP-MANIFEST.json missing')
        backup_meta=json.loads(manifest_member.read().decode('utf-8'))
        if backup_meta.get('snapshot_id')!=snapshot.get('snapshot_id') or backup_meta.get('artifact_count')!=len(snapshot['inventory']):raise RuntimeError('backup manifest identity/count mismatch')
        for entry in snapshot['inventory']:
            member=tar.extractfile('payload/'+entry['archive_path'])
            if member is None:raise RuntimeError(f'backup member missing: {entry["archive_path"]}')
            data=member.read()
            if len(data)!=entry['bytes'] or sha_bytes(data)!=entry['sha256']:raise RuntimeError(f'backup member hash mismatch: {entry["archive_path"]}')

def create_backup(snapshot_path:Path,output:Path,overwrite:bool)->dict:
    if output.exists() and not overwrite:raise ValueError(f'output already exists; use --overwrite: {output}')
    snapshot=json.loads(snapshot_path.read_text(encoding='utf-8'))
    if not verify_snapshot_id(snapshot):raise RuntimeError('snapshot ID verification failed')
    for entry in snapshot.get('inventory',[]):
        source=Path(entry['source_path'])
        if not source.is_file():raise RuntimeError(f'snapshot source missing: {source}')
        if source.stat().st_size!=entry['bytes'] or sha(source)!=entry['sha256']:raise RuntimeError(f'snapshot source drifted: {source}')
    snapshot_bytes=snapshot_path.read_bytes();manifest=backup_manifest(snapshot,snapshot_path);manifest_bytes=(json.dumps(manifest,indent=2,sort_keys=True)+'\n').encode('utf-8')
    output.parent.mkdir(parents=True,exist_ok=True)
    with output.open('wb') as raw:
        with gzip.GzipFile(filename='',mode='wb',fileobj=raw,compresslevel=9,mtime=0) as gz:
            with tarfile.open(fileobj=gz,mode='w',format=tarfile.PAX_FORMAT) as tar:
                tar.addfile(tar_info('BACKUP-MANIFEST.json',manifest_bytes),io.BytesIO(manifest_bytes))
                tar.addfile(tar_info('SNAPSHOT.json',snapshot_bytes),io.BytesIO(snapshot_bytes))
                for entry in sorted(snapshot['inventory'],key=lambda value:value['archive_path']):
                    data=Path(entry['source_path']).read_bytes();tar.addfile(tar_info('payload/'+entry['archive_path'],data,file_mode(entry.get('mode'))),io.BytesIO(data))
    verify_backup(output,snapshot)
    return {'ok':True,'output':str(output),'bytes':output.stat().st_size,'sha256':sha(output),'snapshot_id':snapshot['snapshot_id'],'artifact_count':len(snapshot['inventory']),'artifact_bytes':sum(item['bytes'] for item in snapshot['inventory']),'runtime_embedded':False}

def build_parser():
    parser=argparse.ArgumentParser(prog='reaperctl backup',description=__doc__);parser.add_argument('--snapshot',type=Path,required=True);parser.add_argument('--output',type=Path,default=Path('/mnt/data/reaperctl-evidence/reaper-continuation-backup.tar.gz'));parser.add_argument('--overwrite',action='store_true');parser.add_argument('--json',action='store_true');return parser

def main(argv=None):
    args=build_parser().parse_args(argv)
    try:
        snapshot=args.snapshot.expanduser().resolve();output=args.output.expanduser().resolve()
        if not snapshot.is_file():raise ValueError(f'snapshot not found: {snapshot}')
        report=create_backup(snapshot,output,args.overwrite)
    except ValueError as exc:print(f'reaperctl: {exc}',file=sys.stderr);return 2
    except (RuntimeError,json.JSONDecodeError,tarfile.TarError,OSError) as exc:print(f'reaperctl: {exc}',file=sys.stderr);return 4
    if args.json:print(json.dumps(report,indent=2))
    else:print(f'Continuation backup: VERIFIED\nOutput: {report["output"]}\nSHA-256: {report["sha256"]}\nSnapshot: {report["snapshot_id"]}')
    return 0
if __name__=='__main__':raise SystemExit(main())
