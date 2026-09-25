import subprocess
import sys

print({'python': sys.version, 'executable': sys.executable}, flush=True)
result = subprocess.run([sys.executable, '-B', '/content/q2_receiver_contract_colab_probe.py', 'run'], timeout=150)
if result.returncode:
    raise RuntimeError('RCX worker failed; preserve zip and do not retry')
