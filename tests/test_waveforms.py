import struct
import unittest
import numpy as np
from pds_analysis.waveforms import decode_frames, observables, timestamp_audit


def frame(samples, channel=19, stream=2, tick=100):
    payload = sum(int(v) << (14*i) for i,v in enumerate(samples)).to_bytes(448,'little')
    daq=(63<<52)|(stream<<26)
    header=(channel<<56)|(4<<52)|(2<<46)
    return struct.pack('<3Q',daq,tick,header)+bytes(40)+payload


class AnalysisTests(unittest.TestCase):
    def test_adc_all_bit_boundaries_and_extremes(self):
        samples=np.array([0,1,16383,8192]*64,dtype=np.uint16)
        got=decode_frames(frame(samples))
        np.testing.assert_array_equal(got['adc'][0],samples)
        self.assertEqual(int(got['channels'][0]),19)
        self.assertEqual(int(got['stream_ids'][0]),2)
        self.assertEqual(int(got['timestamps'][0]),100)
        self.assertEqual(int(got['timing_tags'][0]),2)

    def test_stream_is_independent_of_channel(self):
        got=decode_frames(frame([8192]*256,channel=39,stream=0))
        self.assertEqual(int(got['channels'][0]),39)
        self.assertEqual(int(got['stream_ids'][0]),0)

    def test_truncated_and_wrong_format(self):
        with self.assertRaises(ValueError):decode_frames(bytes(511))
        with self.assertRaises(ValueError):decode_frames(bytes(512))

    def test_baseline_polarity_and_charge(self):
        a=np.full((3,256),8192,dtype=np.uint16);a[:,64:74]-=10
        got=observables(a,(0,32),(64,74),-1)
        np.testing.assert_array_equal(got['charge'],[100]*3)
        np.testing.assert_array_equal(got['baseline_rms'],[0]*3)
        self.assertFalse(got['clipped'].any())
        with self.assertRaises(ValueError):observables(a,(0,32),(16,64))

    def test_timestamp_audit_catches_gaps_and_duplicates(self):
        got=timestamp_audit([100,356,612,1124,1124],256)
        self.assertEqual(got['unexpected_steps'],2)
        self.assertEqual(got['duplicate_timestamps'],1)


if __name__=='__main__':unittest.main()
