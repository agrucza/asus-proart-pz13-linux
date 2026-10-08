#!/usr/bin/env python3
# Usage: tools/aeob-parse.py <file.bin>...  (files from the Windows DriverStore, qccam*_extension8380 packages)
"""Parse Qualcomm Windows camera 'AeoB' binaries (CAMx_RES_*.bin, SCFG_*.bin, CAMP_*.bin).
Format: 'AeoB' u32 total u32 1, then TLV entries: u16 type, u16 len, payload[len].
type 0 = integer (len 8: u32 value + u32 pad), 1 = NUL string, 3 = container."""
import struct,sys
def parse(d,off,end,depth,out):
    while off+4<=end:
        t,l=struct.unpack_from('<HH',d,off); body=d[off+4:off+4+l]
        if t==0:
            v=struct.unpack_from('<I',body)[0] if len(body)>=4 else int.from_bytes(body,'little')
            out.append((depth,f"{v}" if v<1000 else f"{v} (0x{v:x})"))
        elif t==1: out.append((depth,'"'+body.split(b'\0')[0].decode(errors='replace')+'"'))
        elif t==3:
            out.append((depth,'{')); parse(d,off+4,off+4+l,depth+1,out); out.append((depth,'}'))
        else: out.append((depth,f"?t{t}:{body.hex()}"))
        off+=4+l
for f in sys.argv[1:]:
    d=open(f,'rb').read(); out=[]; parse(d,12,len(d),0,out)
    print("#####",f.split('/')[-1],len(d),"bytes")
    line=''
    for depth,s in out:
        if s.startswith('"') and line and not line.rstrip().endswith('{'):
            print(line); line='  '*depth+s
        elif s=='{' or s=='}':
            if s=='}' and depth<=1: print(line); line=''; print('  '*depth+'}')
            else: line+=' '+s
        else: line+=' '+s
    if line: print(line)

