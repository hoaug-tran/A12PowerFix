import os, tarfile, gzip, io, struct, time

def build_ar_header(name, size, mtime=None, mode=0o100644, uid=0, gid=0):
    if mtime is None:
        mtime = int(time.time())
    name_field = f"{name:<16}"
    mtime_field = f"{mtime:<12}"
    uid_field = f"{uid:<6}"
    gid_field = f"{gid:<6}"
    mode_field = f"{oct(mode)[2:]:<8}"
    size_field = f"{size:<10}"
    magic = b"`\n"
    header = (name_field + mtime_field + uid_field + gid_field + mode_field + size_field).encode('ascii') + magic
    assert len(header) == 60, f"Header len {len(header)} != 60"
    return header

def create_deb(output_deb_path, control_files, data_files):
    # 1. debian-binary
    deb_binary = b"2.0\n"
    
    # 2. control.tar.gz
    control_buf = io.BytesIO()
    with gzip.GzipFile(fileobj=control_buf, mode="wb", mtime=0) as gz:
        with tarfile.open(fileobj=gz, mode="w:") as tar:
            for name, content, mode in control_files:
                ti = tarfile.TarInfo(name=name)
                ti.size = len(content)
                ti.mtime = 0
                ti.mode = mode
                ti.uid = 0
                ti.gid = 0
                ti.uname = "root"
                ti.gname = "wheel"
                tar.addfile(ti, io.BytesIO(content))
    control_data = control_buf.getvalue()

    # 3. data.tar.gz
    data_buf = io.BytesIO()
    with gzip.GzipFile(fileobj=data_buf, mode="wb", mtime=0) as gz:
        with tarfile.open(fileobj=gz, mode="w:") as tar:
            for item in data_files:
                # item can be: (tar_path, content_bytes, mode, type) or dir or symlink
                t_type = item.get('type', tarfile.REGTYPE)
                ti = tarfile.TarInfo(name=item['path'])
                ti.mtime = 0
                ti.mode = item.get('mode', 0o644)
                ti.uid = 0
                ti.gid = 0
                ti.uname = "root"
                ti.gname = "wheel"
                ti.type = t_type
                if t_type == tarfile.SYMTYPE:
                    ti.linkname = item['linkname']
                    tar.addfile(ti)
                elif t_type == tarfile.DIRTYPE:
                    tar.addfile(ti)
                else:
                    content = item['content']
                    ti.size = len(content)
                    tar.addfile(ti, io.BytesIO(content))
    data_data = data_buf.getvalue()

    # Assemble ar archive
    with open(output_deb_path, 'wb') as f:
        f.write(b"!<arch>\n")
        
        # debian-binary
        f.write(build_ar_header("debian-binary", len(deb_binary)))
        f.write(deb_binary)
        if len(deb_binary) % 2 != 0:
            f.write(b"\n")
            
        # control.tar.gz
        f.write(build_ar_header("control.tar.gz", len(control_data)))
        f.write(control_data)
        if len(control_data) % 2 != 0:
            f.write(b"\n")

        # data.tar.gz
        f.write(build_ar_header("data.tar.gz", len(data_data)))
        f.write(data_data)
        if len(data_data) % 2 != 0:
            f.write(b"\n")

    print(f"Successfully generated {output_deb_path} ({os.path.getsize(output_deb_path)} bytes)")

if __name__ == '__main__':
    print("Deb builder module ready.")

