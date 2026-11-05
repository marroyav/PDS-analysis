import argparse
import hashlib
import json
from pathlib import Path
import numpy as np
from .waveforms import decode_frames, observables, timestamp_audit


def window(text):
    try:
        a, b = map(int, text.split(':'))
        return a, b
    except ValueError as error:
        raise argparse.ArgumentTypeError('Use START:END sample indices, end exclusive') from error


def main():
    p = argparse.ArgumentParser(description='Offline DAPHNE checks and fingerplot charge preparation')
    sub = p.add_subparsers(dest='action', required=True)
    d = sub.add_parser('decode', help='Decode extracted DAQ frames; hardware identity remains external metadata')
    d.add_argument('input', type=Path)
    d.add_argument('output', type=Path)
    i = sub.add_parser('import-scan', help='Read existing step JSON or completed steps from a JSONL journal')
    i.add_argument('input', type=Path)
    i.add_argument('output', type=Path)
    i.add_argument('--data-dir', type=Path, help='Location of extracted .bin files if moved from CERN')
    f = sub.add_parser('fingerplot', help='Export baseline-subtracted charges and a histogram')
    f.add_argument('input', type=Path)
    f.add_argument('--channel', type=int, required=True)
    f.add_argument('--baseline', type=window, required=True)
    f.add_argument('--signal', type=window, required=True)
    f.add_argument('--polarity', choices=['positive', 'negative'], required=True)
    f.add_argument('--expected-step', type=int, required=True, help='Timestamp spacing in ADC sample ticks')
    f.add_argument('--count', type=int, default=10000)
    f.add_argument('--output', type=Path, required=True)
    args = p.parse_args()
    if args.action == 'import-scan':
        from .scan import import_scan
        print(f'Imported {import_scan(args.input, args.output, args.data_dir)} completed steps')
        return
    if args.action == 'decode':
        if args.output.suffix != '.npz':
            raise ValueError('Decoded output must use .npz extension')
        decoded = decode_frames(args.input.read_bytes())
        with args.output.open('xb') as output:
            np.savez_compressed(output, **decoded)
        return
    if args.count <= 0:
        p.error('Count must be positive')
    with np.load(args.input, allow_pickle=False) as data:
        receipt = json.loads(str(data['receipt'])) if 'receipt' in data else None
        a, channels, ticks = data['adc'], data['channels'], data['timestamps']
        if a.ndim == 3:  # campaign export: event x channel x sample
            idx = np.flatnonzero(channels == args.channel)
            if len(idx) != 1:
                raise ValueError('Channel absent or ambiguous')
            a = a[:, idx[0], :]
        elif a.ndim == 2:  # decoded frame collection
            selected = channels == args.channel
            a, ticks = a[selected], ticks[selected]
        else:
            raise ValueError('Unsupported ADC array shape')
        if len(a) < args.count:
            raise ValueError('Fewer than requested waveforms; point incomplete')
        order = np.argsort(ticks)[:args.count]
        a, ticks = a[order], ticks[order]
        audit = timestamp_audit(ticks, args.expected_step)
        if audit['duplicate_timestamps']:
            raise ValueError('Duplicate waveforms; deduplicate and audit upstream')
        values = observables(a, args.baseline, args.signal, 1 if args.polarity == 'positive' else -1)
    args.output.mkdir(parents=True, exist_ok=False)
    np.savetxt(args.output/'charges.txt', values['charge'], fmt='%.10g')
    counts, edges = np.histogram(values['charge'], bins='fd')
    np.savetxt(args.output/'histogram.csv', np.column_stack([edges[:-1], edges[1:], counts]),
        delimiter=',', header='low_adc_samples,high_adc_samples,count', comments='')
    np.savetxt(args.output/'mean-waveform.csv', values['mean_waveform'], delimiter=',')
    report = dict(input=str(args.input.resolve()), input_sha256=hashlib.sha256(args.input.read_bytes()).hexdigest(),
        channel=args.channel, count=len(a), baseline_window=args.baseline, signal_window=args.signal,
        polarity=args.polarity, charge_unit='ADC sample sum', timestamp_audit=audit,
        baseline_mean=float(values['baseline'].mean()),
        baseline_population_rms=float(values['baseline'].std()),
        mean_waveform_baseline_rms=float(values['baseline_rms'].mean()),
        clipped_waveform_fraction=float(values['clipped'].mean()),
        scan_receipt=receipt,
        qualification='Histogram prepared; no SPE fit or sweet spot claimed')
    (args.output/'report.json').write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
