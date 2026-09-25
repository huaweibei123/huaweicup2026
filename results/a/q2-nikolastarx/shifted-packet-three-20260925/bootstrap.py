import subprocess
import sys

print({'python': sys.version, 'executable': sys.executable}, flush=True)
result = subprocess.run([sys.executable, '-B', '/content/q2_shifted_packet_pilot.py', 'run'], timeout=150)
if result.returncode:
    raise RuntimeError('Packet native worker failed; preserve zip and do not retry')
