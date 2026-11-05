import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import numpy as np
from pds_analysis.export import main


class ExportTests(unittest.TestCase):
    def test_export_preserves_samples_and_64bit_timestamps(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            adc=np.arange(3*2*256,dtype=np.uint16).reshape(3,2,256)
            ticks=np.array([2**60+i*1280 for i in range(3)],dtype=np.uint64)
            np.savez(root/'input.npz',adc=adc,channels=[2,24],timestamps=ticks)
            args=['export',str(root/'input.npz'),'--channel','24','--count','3',
                '--expected-step','1280','--output',str(root/'output')]
            with patch('sys.argv',args),contextlib.redirect_stdout(io.StringIO()):main()
            read=np.fromfile(root/'output/waveforms.dat',dtype='<f8').reshape(3,256)
            np.testing.assert_array_equal(read,adc[:,1,:])
            np.testing.assert_array_equal(np.loadtxt(root/'output/timestamps.txt',dtype=np.uint64),ticks)
            meta=json.loads((root/'output/metadata.json').read_text())
            self.assertEqual(meta['timestamp_audit']['unexpected_steps'],0)
            self.assertEqual(meta['memorydepth'],256)
