"""Decode the 512-byte DAPHNE Ethernet frame with a format-4 payload."""
import numpy as np


def decode_frames(payload):
    if not payload or len(payload) % 512:
        raise ValueError('Expected complete 512-byte frames')
    raw = np.frombuffer(payload, dtype=np.uint8).reshape(-1, 512)
    header = raw[:, :24].copy().view('<u8')
    channel = (header[:, 2] >> 56).astype(np.uint8)
    if np.any((header[:, 2] >> 52 & 15) != 4):
        raise ValueError('Expected payload format 4')
    if np.any((header[:, 0] >> 52 & 4095) != 63):
        raise ValueError('Unexpected DAQ word count')
    if np.any(channel > 39):
        raise ValueError('Channel outside physical range 0..39')
    positions = np.arange(256) * 14
    word, shift = positions // 16, (positions % 16).astype(np.uint32)
    packed = np.pad(raw[:, 64:].copy().view('<u2').astype(np.uint32), ((0, 0), (0, 1)))
    adc = (((packed[:, word] >> shift) | (packed[:, word + 1] << (16 - shift))) & 16383).astype(np.uint16)
    return dict(adc=adc, channels=channel, timestamps=header[:, 1].copy(),
        stream_ids=(header[:, 0] >> 26 & 255).astype(np.uint8),
        timing_tags=(header[:, 2] >> 46 & 3).astype(np.uint8),
        continuation=(header[:, 2] >> 51 & 1).astype(bool))


def timestamp_audit(timestamps, expected_step):
    ticks = sorted(map(int, timestamps))
    if type(expected_step) is not int or expected_step <= 0:
        raise ValueError('Expected a positive integer timestamp step')
    from collections import Counter
    differences = [b - a for a, b in zip(ticks, ticks[1:])]
    return dict(frames=len(ticks), duplicate_timestamps=len(ticks)-len(set(ticks)),
        expected_step=expected_step, unexpected_steps=sum(d != expected_step for d in differences),
        common_steps=Counter(differences).most_common(8))


def observables(adc, baseline, signal, polarity=1):
    adc = np.asarray(adc)
    if adc.ndim != 2 or not len(adc) or not np.issubdtype(adc.dtype, np.number):
        raise ValueError('Expected event x sample ADC array')
    if not np.isfinite(adc).all() or np.any(adc < 0) or np.any(adc > 16383):
        raise ValueError('Invalid 14-bit ADC samples')
    for start, end in (baseline, signal):
        if not 0 <= start < end <= adc.shape[1]:
            raise ValueError('Window outside waveform')
    if max(baseline[0], signal[0]) < min(baseline[1], signal[1]):
        raise ValueError('Baseline and signal windows overlap')
    if polarity not in (-1, 1):
        raise ValueError('Polarity must be -1 or +1')
    a = adc.astype(float)
    b = a[:, baseline[0]:baseline[1]]
    mean = b.mean(axis=1)
    corrected = polarity * (a - mean[:, None])
    pulse = corrected[:, signal[0]:signal[1]]
    return dict(baseline=mean, baseline_rms=b.std(axis=1),
        charge=pulse.sum(axis=1), peak=pulse.max(axis=1),
        clipped=np.any((adc == 0) | (adc == 16383), axis=1),
        mean_waveform=corrected.mean(axis=0))
