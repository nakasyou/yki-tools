import struct, collections

d=open('/home/nakasyou/Projects/youkaiwatch/yki/Ver7_U.yki','rb').read()
# u16 array from 0x834 (after offset table) — find where pattern breaks
u16=struct.unpack('<%dH'%((0x56000-0x834)//2), d[0x834:0x834+((0x56000-0x834)//2)*2])

# segment 1: 0x834..0x864 — values 0x40..0x4a + last
print('seg1 (0x834):', [hex(x) for x in u16[0:24]])

# find the big repeating-record region: scan for period-20u16 records
# print u16 values 0x864..0x1000 grouped
vals=list(u16[0x18:0x800])
# find all values != 0xffff and != 0 with positions
nonz=[(i,v) for i,v in enumerate(vals) if v!=0xffff]
print('non-ffff entries in first 0x800 u16:', len(nonz))
# show as (index,value)
for i in range(0,200,10):
    print(i, ' '.join('%04x'%v for v in vals[i:i+10]))
