import contextlib
import io
from unittest.mock import patch
import hashlib
import json
from pathlib import Path
import struct
import tempfile
import unittest
import numpy as np
from pds_analysis.scan import import_scan


class ScanTests(unittest.TestCase):
    def make_input(self, root):
        payload = b''.join(struct.pack('<3Q',63<<52,tick,(ch<<56)|(4<<52)|(2<<46))
            +bytes(40)+bytes(448) for tick in (100,1380,2660) for ch in (0,39))
        (root/'data.bin').write_bytes(payload)
        receipt=dict(schema='pds.calibration.step.v1',verified=True,scan_id='scan1',step_id=0,
            dataset='data.bin',sha256=hashlib.sha256(payload).hexdigest(),
            channels=[0,39],received_counts={'0':3,'39':3},waveforms_per_channel=3,
            frame_bytes=512,samples_per_frame=256,timing_tag=2,
            coordinates={'vgain':500},settings=[{'variable':'offset','value':2275,'target':0,'gain':False}],
            illumination={'settings':{'led_channel_mask':1,'led_bias_270nm':725}},
            file='raw.hdf5',record_id='(1,0)',window_begin=0,window_end=4000)
        (root/'receipt.json').write_text(json.dumps(receipt))
        return receipt

    def test_metadata_and_channel_stream_independence(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);receipt=self.make_input(root)
            self.assertEqual(import_scan(root/'receipt.json',root/'out'),1)
            with np.load(root/'out/step-000.npz',allow_pickle=False) as data:
                self.assertEqual(json.loads(str(data['receipt'])),receipt)
                self.assertEqual(data['adc'].shape,(6,256))
                self.assertTrue(np.all(data['stream_ids']==0))
            from pds_analysis.cli import main
            args=['analyse','fingerplot',str(root/'out/step-000.npz'),'--channel','39',
                '--baseline','0:32','--signal','112:176','--polarity','positive',
                '--expected-step','1280','--count','3','--output',str(root/'plot')]
            with patch('sys.argv',args),contextlib.redirect_stdout(io.StringIO()):main()
            self.assertEqual(json.loads((root/'plot/report.json').read_text())['scan_receipt'],receipt)

    def test_journal_imports_completed_steps_only(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);receipt=self.make_input(root)
            (root/'journal.jsonl').write_text('\n'.join(map(json.dumps,[
                {'event':'step_requested','step_id':1},
                {'event':'step_complete','receipt':receipt},
                {'event':'scan_failed','error':'later step failed'}])))
            self.assertEqual(import_scan(root/'journal.jsonl',root/'out'),1)

    def test_rejects_changed_data_unverified_and_wrong_counts(self):
        for bad in ('hash','verified','count'):
            with self.subTest(bad=bad),tempfile.TemporaryDirectory() as folder:
                root=Path(folder);r=self.make_input(root)
                if bad=='hash':r['sha256']='0'*64
                if bad=='verified':r['verified']=False
                if bad=='count':r['received_counts']['0']=4
                (root/'receipt.json').write_text(json.dumps(r))
                with self.assertRaises(ValueError):import_scan(root/'receipt.json',root/'out')
