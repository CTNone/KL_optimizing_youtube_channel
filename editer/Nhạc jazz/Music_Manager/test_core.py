import json
import tempfile
import unittest
from pathlib import Path
from core import Catalog, STATUSES, identity

class CatalogTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.root=Path(self.tmp.name)
        for group in ('Cafe_Jazz','Romantic_Dinner'):
            p=self.root/group; p.mkdir(); (p/'001 - Song - Artist.mp3').write_bytes(b'original-audio')
        (self.root/'Cafe_Jazz'/'002 - Other - Artist.mp3').write_bytes(b'other-audio')
        cache=self.root/'.audio_cache'; cache.mkdir(); (cache/'cache.mp3').write_bytes(b'cache')
        self.c=Catalog(self.root); self.c.scan(); self.tid=identity('Song','Artist'); self.other=identity('Other','Artist')
        self.pid=self.c.new_project('My project')
    def tearDown(self):
        self.c.db.close(); self.tmp.cleanup()
    def test_duplicate_group_and_scan_preserve_manual_review(self):
        rows=self.c.tracks(); self.assertEqual(len(rows),2)
        song=next(r for r in rows if r['id']==self.tid); self.assertEqual(song['file_count'],2)
        self.c.save_review(self.tid,STATUSES[2],'Exact credit\nURL',notes='checked by me')
        self.c.scan(); self.assertEqual(self.c.get(self.tid)['credit'],'Exact credit\nURL')
    def test_user_credit_suffix_does_not_create_another_artist(self):
        (self.root/'Cafe_Jazz'/'001 - Song - Artist.mp3').rename(self.root/'Cafe_Jazz'/'001 - Song - Artist - GHI CÔNG.mp3')
        self.c.scan(); self.assertEqual(len(self.c.tracks()),2)
        self.assertEqual(self.c.get(self.tid)['status'],STATUSES[0])
        self.assertIn('GHI CÔNG',self.c.get(self.tid)['notes'])
    def test_unreviewed_blocked_and_draft_records_issues(self):
        self.c.add(self.pid,[self.tid,self.tid]); self.assertEqual(len(self.c.project_items(self.pid)),1)
        with self.assertRaises(ValueError): self.c.export(self.pid)
        path=self.c.export(self.pid,draft=True)
        self.assertIn('Chưa kiểm tra',(path/'CAN_KIEM_TRA.txt').read_text(encoding='utf-8-sig'))
        self.assertEqual(len(list((path/'Audio').iterdir())),1)
        self.c.scan(); self.assertEqual(len(self.c.tracks()),2)
    def test_credits_snapshot_order_and_original_preserved(self):
        self.c.save_review(self.tid,STATUSES[2],'EXACT CREDITS')
        self.c.save_review(self.other,STATUSES[1],'old unused credit')
        self.c.add(self.pid,[self.other,self.tid]); self.c.reorder(self.pid,[self.tid,self.other])
        path=self.c.export(self.pid)
        self.assertEqual((path/'GHI_CONG.txt').read_text(encoding='utf-8-sig'),'EXACT CREDITS')
        snap=json.loads((path/'project_snapshot.json').read_text(encoding='utf-8'))
        self.assertEqual(snap['tracks'][0]['id'],self.tid)
        self.c.save_review(self.tid,STATUSES[2],'NEW CREDITS')
        self.assertEqual((path/'GHI_CONG.txt').read_text(encoding='utf-8-sig'),'EXACT CREDITS')
        self.assertEqual((self.root/'Cafe_Jazz'/'001 - Song - Artist.mp3').read_bytes(),b'original-audio')
    def test_missing_source_blocks_even_draft(self):
        self.c.add(self.pid,[self.tid]); self.c.save_review(self.tid,STATUSES[1],'')
        for p in self.root.rglob('*Song*.mp3'): p.unlink()
        with self.assertRaises(ValueError): self.c.export(self.pid,draft=True)
    def test_empty_required_credit_rejected_and_backup_restores(self):
        with self.assertRaises(ValueError): self.c.save_review(self.tid,STATUSES[2],' ')
        self.c.save_review(self.tid,STATUSES[1],''); path=self.c.backup()
        import sqlite3
        from contextlib import closing
        with closing(sqlite3.connect(path)) as db:
            self.assertEqual(db.execute('SELECT status FROM tracks WHERE id=?',(self.tid,)).fetchone()[0],STATUSES[1])

if __name__=='__main__': unittest.main()
