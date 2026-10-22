#!/usr/bin/env python3
import os, stat, struct, sys, time
from pathlib import Path

MAGIC=0x73717368
BLOCK_SIZE=1<<20
BLOCK_LOG=20
NO_FRAG=0xffffffff
UNCOMP_BLOCK=1<<24
UNCOMP_META=1<<15
INVALID=0xffffffffffffffff

class Node:
    def __init__(self,path,rel,parent=None):
        self.path=path; self.rel=rel; self.parent=parent; self.children=[]
        st=os.lstat(path); self.is_dir=stat.S_ISDIR(st.st_mode); self.is_file=stat.S_ISREG(st.st_mode)
        if not (self.is_dir or self.is_file): raise RuntimeError(f'unsupported {path}')
        self.mode=stat.S_IMODE(st.st_mode)&0o7777
        self.mtime=int(st.st_mtime)
        self.inum=0; self.inoff=0
        self.data_start=0; self.block_sizes=[]; self.file_size=st.st_size if self.is_file else 0
        self.dir_offset=0; self.dir_size=0

def walk(root):
    root=Path(root)
    r=Node(root,'.',None)
    nodes=[]
    def rec(n):
        nodes.append(n)
        if n.is_dir:
            for p in sorted(n.path.iterdir(), key=lambda x:x.name):
                c=Node(p, str(p.relative_to(root)), n); n.children.append(c); rec(c)
    rec(r)
    for i,n in enumerate(nodes,1): n.inum=i
    return r,nodes

def inode_len(n):
    if n.is_dir: return 32
    blocks=(n.file_size + BLOCK_SIZE - 1)//BLOCK_SIZE if n.file_size else 0
    return 32+4*blocks

def meta_block(payload):
    if len(payload)>0x7fff: raise ValueError('metadata too large')
    return struct.pack('<H',UNCOMP_META|len(payload))+payload

def make_sqfs(rootdir,outpath):
    root,nodes=walk(rootdir)
    # inode offsets: one metadata block, so offset is direct uncompressed offset
    off=0
    for n in nodes:
        n.inoff=off; off+=inode_len(n)
    if off>8192: raise RuntimeError(f'inode table too large {off}')

    # Build directory table streams now that inode offsets/numbers are known.
    dtab=bytearray()
    for n in nodes:
        if not n.is_dir: continue
        n.dir_offset=len(dtab)
        entries=n.children
        if entries:
            base=entries[0].inum
            # all inodes are in inode metadata block 0
            dtab += struct.pack('<III',len(entries)-1,0,base)
            for c in entries:
                name=c.path.name.encode('utf-8')
                delta=c.inum-base
                if not (-32768<=delta<=32767): raise RuntimeError('inode delta')
                typ=1 if c.is_dir else 2
                dtab += struct.pack('<HhHH',c.inoff,delta,typ,len(name)-1)
                dtab += name
        n.dir_size=len(dtab)-n.dir_offset
    if len(dtab)>8192: raise RuntimeError(f'directory table too large {len(dtab)}')

    # File data begins immediately after superblock.
    image=bytearray(b'\0'*96)
    for n in nodes:
        if not n.is_file: continue
        n.data_start=len(image)
        n.block_sizes=[]
        with open(n.path,'rb') as f:
            while True:
                b=f.read(BLOCK_SIZE)
                if not b: break
                image += b
                n.block_sizes.append(len(b)|UNCOMP_BLOCK)

    inode_table_start=len(image)
    ib=bytearray()
    total=len(nodes)
    for n in nodes:
        typ=1 if n.is_dir else 2
        ib += struct.pack('<HHHHII',typ,n.mode,0,0,n.mtime,n.inum)
        if n.is_dir:
            nlink=2+sum(1 for c in n.children if c.is_dir)
            parent=(n.parent.inum if n.parent else total+1)
            ib += struct.pack('<IIHHI',0,nlink,n.dir_size,n.dir_offset,parent)
        else:
            ib += struct.pack('<IIII',n.data_start,NO_FRAG,0,n.file_size)
            for s in n.block_sizes: ib += struct.pack('<I',s)
    assert len(ib)==off
    image += meta_block(ib)
    directory_table_start=len(image)
    image += meta_block(dtab)

    # Single uid/gid id-table entry: 0
    id_meta_start=len(image)
    image += meta_block(struct.pack('<I',0))
    id_table_start=len(image)
    image += struct.pack('<Q',id_meta_start)
    bytes_used=len(image)

    # compression=1 (gzip) but all data and metadata blocks are explicitly uncompressed.
    # flags=0: no fragments/export/xattrs are referenced; corresponding starts are INVALID.
    root_inode=(0<<16)|root.inoff
    sb=struct.pack('<5I6H8Q',
        MAGIC,len(nodes),int(time.time()),BLOCK_SIZE,0,
        1,BLOCK_LOG,0,1,4,0,
        root_inode,bytes_used,id_table_start,INVALID,
        inode_table_start,directory_table_start,INVALID,INVALID)
    assert len(sb)==96
    image[:96]=sb
    Path(outpath).write_bytes(image)
    print(f'wrote {outpath}: {len(image)} bytes, inodes={len(nodes)}, inode_meta={len(ib)}, dir_meta={len(dtab)}')

if __name__=='__main__': make_sqfs(sys.argv[1],sys.argv[2])
