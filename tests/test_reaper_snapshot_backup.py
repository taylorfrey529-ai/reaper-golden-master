import importlib.machinery,importlib.util,json,sys,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

def load(name,path):
    loader=importlib.machinery.SourceFileLoader(name,str(path));spec=importlib.util.spec_from_loader(loader.name,loader);mod=importlib.util.module_from_spec(spec);sys.modules[name]=mod;loader.exec_module(mod);return mod

snapshot=load('reaper_snapshot_test',ROOT/'scripts/reaper-snapshot.py')
backup=load('reaper_backup_test',ROOT/'scripts/reaper-backup.py')

class SnapshotBackupTests(unittest.TestCase):
    def test_snapshot_id_detects_change(self):
        body={'schema_version':1,'inventory':[]}
        body['snapshot_id']='sha256:'+snapshot.sha_bytes(snapshot.canonical_bytes({'schema_version':1,'inventory':[]}))
        self.assertTrue(snapshot.verify_snapshot_id(body))
        body['schema_version']=2
        self.assertFalse(snapshot.verify_snapshot_id(body))

    def test_deterministic_backup(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);source=root/'a.txt';source.write_bytes(b'alpha\n')
            manifest={'schema_version':1,'kind':'x','golden_master':{'id':'gm'},'inventory':[{'archive_path':'workspace/a.txt','source_path':str(source),'role':'test','bytes':6,'sha256':backup.sha(source),'mode':'0o644'}]}
            manifest['snapshot_id']='sha256:'+backup.sha_bytes(backup.canonical_bytes(manifest))
            snap=root/'SNAPSHOT.json';snap.write_text(json.dumps(manifest,indent=2,sort_keys=True)+'\n')
            a=root/'a.tar.gz';b=root/'b.tar.gz'
            ra=backup.create_backup(snap,a,False);rb=backup.create_backup(snap,b,False)
            self.assertEqual(ra['sha256'],rb['sha256'])

if __name__=='__main__':unittest.main()
