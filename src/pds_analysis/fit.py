"""Fit pedestal, SPE and 2PE charge peaks with three Gaussians in ROOT."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import shutil
import subprocess


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('charges',type=Path)
    p.add_argument('--output',type=Path,required=True)
    for name in ('pedestal','spe','twope'):p.add_argument('--'+name,type=float,required=True)
    args=p.parse_args()
    seeds=[args.pedestal,args.spe,args.twope]
    if not all(map(math.isfinite,seeds)) or not seeds[0]<seeds[1]<seeds[2]:
        p.error('Provide finite, ordered pedestal/SPE/2PE charge estimates')
    root=shutil.which('root')
    if root is None:raise RuntimeError('ROOT executable is required')
    charges=args.charges.read_bytes()
    report=args.charges.parent/'report.json'
    receipt=json.loads(report.read_text()).get('scan_receipt') if report.exists() else None
    args.output.mkdir(parents=True,exist_ok=False)
    macro=Path(__file__).with_name('fit.C.in').read_text()
    macro=macro.replace('CHARGE_PATH',json.dumps(str(args.charges.resolve()))).replace('SEEDS',','.join(map(repr,seeds)))
    (args.output/'fit.C').write_text(macro)
    (args.output/'provenance.json').write_text(json.dumps(dict(
        scan_receipt=receipt,charges_sha256=hashlib.sha256(charges).hexdigest(),
        model='sum of three Gaussians with independent widths',seeds=seeds),indent=2)+'\n')
    with (args.output/'root.log').open('w') as log:
        result=subprocess.run([root,'-l','-b','-q','fit.C'],cwd=args.output,
            stdout=log,stderr=subprocess.STDOUT,timeout=180)
    if result.returncode:raise RuntimeError(f'Fit failed or invalid; inspect {args.output}/root.log')
    print((args.output/'fit.json').read_text())


if __name__=='__main__':main()
