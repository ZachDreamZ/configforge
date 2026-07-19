import struct, os
path = r"D:\workspace\configforge\hyperframes\terminal-preview.png"
with open(path, 'rb') as f:
    f.read(8)
    while True:
        chunk_len = struct.unpack('>I', f.read(4))[0]
        chunk_type = f.read(4)
        data = f.read(chunk_len)
        if chunk_type == b'IHDR':
            w, h = struct.unpack('>II', data[:8])
            print(f"Size: {w}x{h}")
            break
        f.read(4)
print(f"File size: {os.path.getsize(path):,} bytes")
