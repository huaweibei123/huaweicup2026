import json, os, platform, subprocess, sys
from pathlib import Path
print(json.dumps({'python':sys.version,'executable':sys.executable,'platform':platform.platform(),'cpu_count':os.cpu_count(),'memory':next(x for x in Path('/proc/meminfo').read_text().splitlines() if x.startswith('MemTotal:')),'ps_supported':subprocess.run(['ps','-axo','pid=,ppid=,pgid=,rss=,lstart='],capture_output=True).returncode==0},sort_keys=True))
