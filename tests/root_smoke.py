"""Optional ROOT integration check using synthetic charges, not detector data."""
import json
from pathlib import Path
import subprocess
import sys
import numpy as np

output=Path(sys.argv[1]); upstream=Path(sys.argv[2])
output.mkdir(parents=True,exist_ok=False)
rng=np.random.default_rng(20261105)
pe=rng.choice(3,size=20000,p=[.6,.33,.07])
charges=100*pe+rng.normal(0,np.sqrt(10**2+pe*8**2))
np.savetxt(output/'synthetic-charges.txt',charges)
subprocess.run([sys.executable,'-m','pds_analysis.apc',str(output/'synthetic-charges.txt'),
    '--apc-root',str(upstream),'--pedestal','0','--spe','100','--twope','200',
    '--output',str(output/'fit')],check=True)
fit=json.loads((output/'fit/fit.json').read_text())
assert fit['fit_valid'] and abs(fit['spe_separation']-100)<5,fit
print('Synthetic ROOT/APC integration check passed; this is not a detector result.')
