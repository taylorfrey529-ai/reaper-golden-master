import hashlib, importlib.machinery, importlib.util, io, json, os, sys, tarfile, tempfile, unittest, zipfile
from pathlib import Path
PATH=Path(__file__).resolve().parents[1]/'scripts'/'reaper-restore.py'
loader=importlib.machinery.SourceFileLoader('reaper_restore_test',str(PATH));spec=importlib.util.spec_from_loader(loader.name,loader);mod=importlib.util.module_from_spec(spec);sys.modules[loader.name]=mod;loader.exec_module(mod)

def sha(data):return hashlib.sha256(data).hexdigest()
def snapshot_for(payload):
    base={'schema_version':1,'kind':'reaper-continuation-snapshot','golden_master':{'id':'gm:test'},'runtime_binding':{'sha256':sha(b'fake-reaper'),'bytes':len(b'fake-reaper')},'inventory':[{'archive_path':'workspace/start-desktop.sh','bytes':len(payload),'sha256':sha(payload),'mode':'0o755'}]}
    base['snapshot_id']='sha256:'+sha(mod.canonical_bytes(base));return base

def make_backup(path,snapshot,payload):
    meta={'snapshot_id':snapshot['snapshot_id'],'artifact_count':1,'golden_master_id':'gm:test'}
    with tarfile.open(path,'w:gz') as tar:
        for name,data,mode in [('SNAPSHOT.json',json.dumps(snapshot).encode(),0o644),('BACKUP-MANIFEST.json',json.dumps(meta).encode(),0o644),('payload/workspace/start-desktop.sh',payload,0o755)]:
            info=tarfile.TarInfo(name);info.size=len(data);info.mode=mode;tar.addfile(info,io.BytesIO(data))

def make_audio(path):
    with zipfile.ZipFile(path,'w') as z:
        info=zipfile.ZipInfo(mod.REAPER_PREFIX+'reaper');info.external_attr=0o755<<16;z.writestr(info,b'fake-reaper')
        info=zipfile.ZipInfo(mod.REAPER_PREFIX+'libSwell.so');info.external_attr=0o644<<16;z.writestr(info,b'lib')

class RestoreTests(unittest.TestCase):
    def test_rejects_traversal(self):
        with self.assertRaises(RuntimeError):mod.safe_relative('../escape')
        with self.assertRaises(RuntimeError):mod.safe_relative('/absolute')
    def test_snapshot_identity(self):
        snap=snapshot_for(b'x');self.assertTrue(mod.verify_snapshot_id(snap));snap['kind']='tampered';self.assertFalse(mod.verify_snapshot_id(snap))
    def test_restore_synthetic_payload(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);payload=b'#!/bin/sh\necho ok\n';snap=snapshot_for(payload);backup=root/'b.tar.gz';audio=root/'audio.zip';target=root/'target';make_backup(backup,snap,payload);make_audio(audio)
            report=mod.restore(backup,audio,target,False,expected_audio_sha=mod.sha(audio),expected_reaper_sha=sha(b'fake-reaper'))
            self.assertTrue(report['ok']);self.assertEqual((target/'workspace/start-desktop.sh').read_bytes(),payload);self.assertEqual(os.stat(target/'workspace/start-desktop.sh').st_mode & 0o777,0o755);self.assertEqual((target/'workspace/apps/REAPER/reaper').read_bytes(),b'fake-reaper')
    def test_backup_hash_tamper_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);payload=b'good';snap=snapshot_for(payload);backup=root/'b.tar.gz';make_backup(backup,snap,b'bad!')
            with self.assertRaises(RuntimeError):mod.load_and_verify_backup(backup)

if __name__=='__main__':unittest.main()
