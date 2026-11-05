"""Run the reviewed apc_root peak model with the ROOT executable, without PyROOT."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

APC_COMMIT = 'b3ed8978a265070f1ed9d13db657bd6cc6893067'


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('charges', type=Path)
    p.add_argument('--apc-root', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--pedestal', type=float, required=True)
    p.add_argument('--spe', type=float, required=True)
    p.add_argument('--twope', type=float, required=True)
    args = p.parse_args()
    if not args.pedestal < args.spe < args.twope:
        p.error('Provide ordered pedestal, SPE and 2PE charge peak estimates')
    root = shutil.which('root')
    if root is None:
        raise RuntimeError('ROOT executable is required in the existing environment')
    commit = subprocess.check_output(['git', '-C', str(args.apc_root), 'rev-parse', 'HEAD'], text=True).strip()
    if commit != APC_COMMIT:
        raise ValueError('Review the upstream revision before changing the pinned APC commit')
    relative = 'cold_box_analysis/class/calibrationCodes.C'
    source = (args.apc_root/relative).read_bytes()
    original = subprocess.check_output(['git', '-C', str(args.apc_root), 'show', f'{APC_COMMIT}:{relative}'])
    if source != original:
        raise ValueError('Upstream model has uncommitted modifications')
    text = source.decode()
    model = text[text.index('class  MyFunctionObject'):text.index('class  MyFunctionFree')]
    args.output.mkdir(parents=True, exist_ok=False)
    # Keep the upstream model external to this repository; copy only into results.
    (args.output/'apc_model.hxx').write_text('#include <TMath.h>\n#include <cmath>\nusing std::abs;\n'+model)
    path = json.dumps(str(args.charges.resolve()))
    seeds = ','.join(map(repr, [args.pedestal, args.spe, args.twope]))
    macro = Path(__file__).with_name('fit.C.in').read_text().replace('CHARGE_PATH', path).replace('SEEDS', seeds)
    (args.output/'fit.C').write_text(macro)
    report = args.charges.parent/'report.json'
    scan_receipt = json.loads(report.read_text()).get('scan_receipt') if report.exists() else None
    provenance = dict(scan_receipt=scan_receipt, upstream='https://github.com/hvsouza/apc_root', commit=commit,
        source=relative, source_sha256=hashlib.sha256(source).hexdigest(),
        charges_sha256=hashlib.sha256(args.charges.read_bytes()).hexdigest(),
        model='MyFunctionObject, n_peaks=1; pedestal + SPE + 2PE; higher peaks excluded from fit range',
        note='Uses the upstream model, not the full Calibration interactive fitter. Fit validity alone does not establish an LED sweet spot.')
    (args.output/'provenance.json').write_text(json.dumps(provenance, indent=2)+'\n')
    with (args.output/'root.log').open('w') as log:
        run = subprocess.run([root, '-l', '-b', '-q', 'fit.C'], cwd=args.output,
            stdout=log, stderr=subprocess.STDOUT, timeout=180)
    if run.returncode:
        raise RuntimeError(f'Fit failed or was invalid (exit {run.returncode}); inspect {args.output}/root.log')
    print((args.output/'fit.json').read_text())


if __name__ == '__main__':
    main()
