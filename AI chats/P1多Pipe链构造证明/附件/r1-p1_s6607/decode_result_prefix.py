#!/usr/bin/env python3
"""Decode a fetched gzip prefix. Deliberately NOT a full gzip/CRC/SHA verifier."""
import base64,zlib
from pathlib import Path
root=Path(__file__).parent
raw=base64.b64decode((root/'original/result_gz_prefix.b64').read_text())
d=zlib.decompressobj(16+zlib.MAX_WBITS);prefix=d.decompress(raw)
assert prefix==(root/'original/result_prefix.json.partial').read_bytes()
print({'compressed_prefix_bytes':len(raw),'decoded_prefix_bytes':len(prefix),'reached_gzip_eof':d.eof,'full_integrity_verified':False})
