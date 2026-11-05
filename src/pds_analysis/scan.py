"""Import the existing calibration receipt and its extracted DAQ frames."""
import hashlib
import json
from pathlib import Path
import numpy as np
from .waveforms import decode_frames


def import_scan(source, output, data_dir=None):
    source, output = Path(source), Path(output)
    if source.suffix == '.jsonl':
        events = [json.loads(line) for line in source.read_text().splitlines() if line.strip()]
        receipts = [event['receipt'] for event in events if event.get('event') == 'step_complete']
    else:
        receipts = [json.loads(source.read_text())]
    if not receipts:
        raise ValueError('No completed steps in input')
    keys = [(r['scan_id'], r['step_id']) for r in receipts]
    if len(set(keys)) != len(keys):
        raise ValueError('Duplicate scan/step receipts')
    if len({r['scan_id'] for r in receipts}) != 1:
        raise ValueError('Import one scan at a time')
    output.mkdir(parents=True, exist_ok=False)
    for receipt in receipts:
        if receipt.get('schema') != 'pds.calibration.step.v1' or receipt.get('verified') is not True:
            raise ValueError('Expected a verified calibration step receipt')
        if receipt['frame_bytes'] != 512 or receipt['samples_per_frame'] != 256:
            raise ValueError('Unsupported waveform geometry')
        dataset = Path(receipt['dataset'])
        if data_dir is not None:
            dataset = Path(data_dir)/dataset.name
        elif not dataset.is_absolute():
            dataset = source.parent/dataset
        payload = dataset.read_bytes()
        if hashlib.sha256(payload).hexdigest() != receipt['sha256']:
            raise ValueError('Extracted dataset hash differs from receipt')
        frames = decode_frames(payload)
        channels = receipt['channels']
        if not channels or len(set(channels)) != len(channels):
            raise ValueError('Invalid receipt channel selection')
        if set(map(int, frames['channels'])) != set(channels):
            raise ValueError('Dataset channels differ from receipt')
        if np.any(frames['continuation']) or np.any(frames['timing_tags'] != receipt['timing_tag']):
            raise ValueError('Unexpected continuation or calibration tag')
        reference = None
        for ch in channels:
            ticks = np.sort(frames['timestamps'][frames['channels'] == ch])
            if len(ticks) != receipt['received_counts'][str(ch)] or len(np.unique(ticks)) != len(ticks):
                raise ValueError('Waveform count mismatch or duplicate timestamps')
            target = receipt.get('waveforms_per_channel')
            if target is not None and len(ticks) != target:
                raise ValueError('Requested waveform count not met')
            if reference is not None and not np.array_equal(ticks, reference):
                raise ValueError('Channels contain different timing events')
            reference = ticks
        name = f"step-{receipt['step_id']:03d}"
        with (output/(name+'.npz')).open('xb') as file:
            np.savez_compressed(file, **frames, receipt=json.dumps(receipt))
        (output/(name+'.json')).write_text(json.dumps(receipt, indent=2)+'\n')
    return len(receipts)
