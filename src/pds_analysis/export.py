"""Export decoded ADC waveforms as little-endian float64 arrays."""
import argparse
import hashlib
import json
from pathlib import Path
import numpy as np
from .waveforms import timestamp_audit


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('input',type=Path)
    p.add_argument('--channel',type=int,required=True)
    p.add_argument('--count',type=int,default=10000)
    p.add_argument('--expected-step',type=int,required=True)
    p.add_argument('--output',type=Path,required=True)
    args=p.parse_args()
    if args.count<=0:p.error('Count must be positive')
    with np.load(args.input,allow_pickle=False) as data:
        receipt=json.loads(str(data['receipt'])) if 'receipt' in data else None
        adc,channels,ticks=data['adc'],data['channels'],data['timestamps']
        if adc.ndim==3:
            selected=np.flatnonzero(channels==args.channel)
            if len(selected)!=1:raise ValueError('Channel absent or ambiguous')
            adc=adc[:,selected[0],:]
        elif adc.ndim==2:
            selected=channels==args.channel
            adc,ticks=adc[selected],ticks[selected]
        else:raise ValueError('Expected event x sample or event x channel x sample')
        if len(adc)!=len(ticks) or len(adc)<args.count:
            raise ValueError('Incomplete waveform count or timestamps')
        if not np.isfinite(adc).all() or np.any(adc<0) or np.any(adc>16383):
            raise ValueError('Invalid raw 14-bit ADC values')
        order=np.argsort(ticks)[:args.count]
        adc,ticks=adc[order],ticks[order]
        audit=timestamp_audit(ticks,args.expected_step)
        if audit['duplicate_timestamps']:raise ValueError('Duplicate timestamps')
        args.output.mkdir(parents=True,exist_ok=False)
        adc.astype('<f8').tofile(args.output/'waveforms.dat')
        np.savetxt(args.output/'timestamps.txt',ticks,fmt='%d')
        metadata=dict(scan_receipt=receipt,
            dtype='little-endian float64, native doubles on the CERN x86 hosts',
            memorydepth=adc.shape[1],n_wf=len(adc),channel=args.channel,
            raw_ADC=True,baseline_subtracted=False,timestamp_audit=audit,
            input_sha256=hashlib.sha256(args.input.read_bytes()).hexdigest(),
            output_sha256=hashlib.sha256((args.output/'waveforms.dat').read_bytes()).hexdigest(),
            status='raw samples exported; baseline subtraction and integration not applied')
    (args.output/'metadata.json').write_text(json.dumps(metadata,indent=2)+'\n')
    print(json.dumps(metadata,indent=2))


if __name__=='__main__':main()
