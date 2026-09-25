import subprocess
import sys

print({'python': sys.version, 'executable': sys.executable}, flush=True)
result = subprocess.run([sys.executable, '-B', '/content/q2_rcx_fixed_e0_probe.py', 'run'], timeout=150)
if result.returncode:
    raise RuntimeError('RCX worker failed; preserve zip and do not retry')
