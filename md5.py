import hashlib
import base64

from oss2.compat    import to_string

from returns.io        import IOResultE, IOFailure, IOSuccess
from returns.pointfree import map_
from returns.pipeline  import flow, pipe

# calculate_md5 :: _io.BufferedReader -> IOResult[str]
def calculate_md5(filehandler):
    md5_to_string = pipe(lambda x : x.digest(), base64.b64encode, to_string)
    return flow(
        IOResultE.from_value(filehandler), # IOResultE[_io.BufferedReader]
        update_to_md5,                     # IOResultE[hashlib.md5]
        map_(md5_to_string)                # IOResultE[str]
    )

# update_to_md5 :: IOResultE[_io.BufferedReader] -> IOResultE[hashlib.md5]
def update_to_md5(io_buffer_reader):
    def helper(io_buffer_reader, m):
        return io_buffer_reader.bind(
            lambda f : IOResultE.from_value(f.read(52428800)) # 50M
        ).bind(
            lambda buffer : IOSuccess(m.update(buffer)) if buffer else IOFailure("EOF")
        ).bind(
            lambda _ : helper(io_buffer_reader, m)
        ).lash(
            lambda err : IOResultE.from_value(m)
        )
    return helper(io_buffer_reader, hashlib.md5())
