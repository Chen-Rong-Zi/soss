#!/usr/bin/env python3
import os
import stat
import json
import uuid
import socket
import argparse
import threading
from   pathlib   import Path, PurePath

import oss2
from   oss2.credentials import EnvironmentVariableCredentialsProvider
from   oss2.utils       import content_md5
from   oss2.compat      import to_bytes

import returns.pointfree  as     pointfree
import returns.methods    as     methods
from   returns.pointfree  import map_,      bind, lash
from   returns.io         import IOResultE, impure,       impure_safe,   IOFailure,      IOSuccess, IOResult
from   returns.context    import Reader,    ReaderResult, ReaderResultE, ReaderIOResultE
from   returns.result     import safe,      ResultE,      Failure,       Result
from   returns.pipeline   import flow,      pipe
from   returns.iterables  import Fold
from   returns.curry      import curry
from   returns.converters import flatten
# from viztracer          import VizTracer

from   ListHelper         import lmap,      lfilter,   concat, ljoin
from   multivalue         import MIterator, MultiValue
from   md5                import calculate_md5 as get_local_md5

def ioresult_sequence(ioresult):
    if isinstance(ioresult, IOFailure):
        return ioresult
    return ioresult._inner_value._inner_value.map(IOSuccess)

# MIterator[IOResultE[]] -> IOResultE[MIterator[str]]
def miterator_ioresult(mi_io):
    def gen():
        for ior in mi_io:
            if isinstance(ior, IOSuccess):
                yield ior._inner_value._inner_value
    return IOSuccess(gen())

@curry
@safe
def safe_get(key, subscriptable):
    return subscriptable[key]

@impure_safe
# read_file :: str -> IOResultE[str]
def read_file(file_path):
    with open(file_path, 'r', encoding = 'utf-8') as f:
        return f.read()

@impure_safe
# read_data :: str -> IOResultE[byte]
def read_data(file_path):
    with open(file_path, 'rb') as f:
        return f.read()

@safe(exceptions=(json.decoder.JSONDecodeError,))
# parse_json :: str -> ResultE[dict]
def parse_json(string):
    return json.loads(string)

# parse_json_ioresult :: str -> IOResultE[dict]
def parse_json_ioresult(string):
    return pipe(parse_json, IOResultE.from_result)(string)

# str -> Reader[IOResultE[str], bucket]
def key_exists(key):
    @impure_safe
    # with_bucket bucket -> bool
    def with_bucket(bucket):
        # return False
        return bucket.object_exists(key)
    return Reader(with_bucket)

@curry
# upload_data :: (str, Union[str, byte]) -> Reader[IOResultE[Union[str, byte]]]
def upload_data(key, data):
    @impure_safe
    def with_bucket(bucket):
        put_result = bucket.put_object(key, data)
        print(f'{key} 上传成功')
        return f'{key} 上传成功'
    return Reader(with_bucket)

@impure_safe
# get_uuid :: () -> IOResultE[str]
def get_uuid():
    return str(uuid.UUID(int=uuid.getnode()))

@impure_safe
# get_hostname :: () -> IOResultE[str]
def get_hostname():
    return socket.gethostname()

@impure_safe
# get_username :: () -> IOResultE[str]
def get_username():
    return os.getlogin()

# get_identifier :: () -> IOResultE[dict]
def get_identifier():
    """
    return the uniq Identifier describe the object in the bucket,
    which contains the device uuid and absolute path in that's FileSystem
    """
    return IOResultE.do(
        {
            'uuid'     : uuid,
            'hostname' : hostname,
            'username' : username
        }
        for uuid     in get_uuid()     # () -> IOResultE[str]
        for hostname in get_hostname() # () -> IOResultE[str]
        for username in get_username() # () -> IOResultE[str]
    )

def trace(x):
    print(f'trace: {x}')
    return x

# posix_get_key :: Path -> Reader[str]
def posix_get_key(path):
    def with_identifier(identifier):
        return identifier['hostname'] + str(path)
    return Reader(with_identifier)

# nt_get_key :: Path -> Reader[str]
def nt_get_key(path):
    def with_identifier(identifier):
        validate_key = pipe(str, os.path.normcase, Path, lambda x : x.as_posix())
        return identifier['hostname'] + '/' + validate_key(path)
    return Reader(with_identifier)

# upload_one :: str -> Reader[IOResultE[str]]
def upload_one(file_path):
    # with_env :: dict -> IOResultE[str]
    def with_env(env):
        return get_file_handler(file_path).bind(
            lambda data : upload_data(env['key'])(data)(env['bucket'])
        )
    return Reader(with_env)

# get_file_handler :: str -> IOResultE[_io.BufferedReader]
@impure_safe
def get_file_handler(filepath, mode='rb'):
    return open(filepath, mode)

# get_remote_md5 :: str -> Reader[IOResultE(md5)]
def get_remote_md5(key):
    # with_bucket :: bucket -> IO[ResultE[str]]
    def with_bucket(bucket):
        header_result = bucket.head_object(key)
        return IOResultE.from_result(safe_get('Content-Md5')(header_result.resp.headers))
    return Reader(pipe(with_bucket, IOResultE.from_ioresult))

# check_md5_integrity :: str -> Reader[IOResultE[bool]]
def check_md5_integrity(filepath):
    def with_env(env):
        return IOResultE.do(
            local_md5 == remote_md5
            for fhandle    in get_file_handler(filepath)
            for local_md5  in get_local_md5(fhandle)
            for remote_md5 in get_remote_md5(env['key'])(env['bucket'])
        )
    return Reader(with_env)

# conditional_exit :: str -> Reader[IOResultE[str]]
def conditional_exit(filepath):
    return check_md5_integrity(filepath).map(
        bind(lambda pass_md5_verify : IOFailure(f'{filepath} 在oss中已存在!') if pass_md5_verify else IOSuccess(f'Did not Pass md5 verification'))
    )

# conditional_upload :: str -> Reader[IOResultE[str]]
def conditional_upload(filepath):
    # with_env :: dict -> IOResultE[str]
    def with_env(env):
        # env.update({'key' : get_key(filepath)(env['identifier'])})
        items   = list(env.items()) + [('key', get_key(filepath)(env['identifier']))]
        new_env = dict(items)
        return key_exists(new_env['key'])(env['bucket']).bind(
            lambda exists : conditional_exit(filepath)(new_env) if exists else IOSuccess("File Not Exists")
        ).bind(
            lambda _ : upload_one(filepath)(new_env)
        )
    return Reader(with_env)

# is_normal_file :: Path -> IOResultE[Path]
def is_normal_file(path):
    return IOSuccess(path.is_file())

# truey_value :: IOResultE[any] -> bool
def truey_value(ior_value):
    return ior_value == IOSuccess(True)

# str -> IOResultE[MIterator[Path]]
def collect_files(directory_path):

    # Tuple[str, str, List[str]] -> MIterator[str]
    def tu0_plus_tu2(tu):
        current_dir = Path(tu[0])
        return flow(
            MIterator(tu[2]),
            map_(current_dir.joinpath)
        )

    normal_file = pipe(is_normal_file, truey_value)

    return flow(
        IOSuccess(directory_path),
        bind(impure_safe(Path.absolute)),                             # IOResultE[Str]
        bind(impure_safe(Path.resolve)),                              # IOResultE[Str]
        bind(impure_safe(pipe(Path.walk, MIterator))),                # IOResultE[MIterator[Tuple[Str]]]
        map_(bind(tu0_plus_tu2)),                                     # IOResultE(MIterator[str])
        map_(lambda iterator : iterator.filter(normal_file)),              # IOResultE[MIterator[str]]
    )

# upload_dir :: str -> IOResultE[MIterator[ReaderIOResultE[str]]]
def upload_dir(directory):
    return IOSuccess(directory).map(
        pipe(os.path.normcase, os.path.normpath, Path)
    ).bind(
        lambda path : IOSuccess(path) if path.is_dir() else IOFailure(f'"{path}" is not exists, thus can not be collected') 
    ).bind(
        collect_files                                                                   # IOResultE[MIterator[Path]]
    ).map(
        map_(conditional_upload)                                                        # IOResultE[MIterator[Reader[IOResultE[str]]]]
    )

# oss_login :: dict -> IOResultE[oss2.Bucket]
def oss_login(env):
    return flow(
        IOSuccess(curry(oss2.Bucket)),
        IOResultE.from_ioresult(make_auth()).apply,
        IOSuccess(env['endpoint']).apply,
        IOSuccess(env['bucket']).apply
    )

# read_config :: str -> IOResultE[dict]
def read_config(config_path):
    return flow(
        config_path,
        read_file,
        bind(parse_json_ioresult)
    )

@impure_safe
# make_auth :: () -> IOResultE[oss2.Auth]
def make_auth():
    return oss2.ProviderAuth(EnvironmentVariableCredentialsProvider())

# make_env :: args -> IOResultE[dict]
def make_env(args):
    return IOResultE.do(
        {
            'config'     : config,
            'identifier' : identifier,
        }
        for config     in read_config(args.config)
        for identifier in get_identifier()
    )

# win_callback :: MIterator[IOResultE[str]]
def win_callback(iter_reader_ioresult):
    threads = []
    for task in iter_reader_ioresult:
        t = threading.Thread(target=task)
        t.start()
        threads.append(t)
        while len(threads) > 300:
            threads = [th for th in threads if not th.is_alive()]
    return IOSuccess(0)

# fail_callback :: Exception -> IOResultE[None]
def fail_callback(error):
    return  IOFailure(print(error))

# upload :: args -> IOResultE[MIterator[Callable[[], IOResultE[str]]]]
def upload(args):
    # return upload_dir(args.directory)
    new_env = lambda env, bucket : {
        'bucket'     : bucket,
        'identifier' : env['identifier']
    }
    return IOResultE.do(
        iter_reader_ioresult.map(
            map_(lash(fail_callback))
        ).map(
            lambda reader : lambda : reader(new_env(env, bucket))
        )
        for iter_reader_ioresult in upload_dir(args.directory)
        for env                  in make_env(args)
        for bucket               in oss_login(env['config'])
    )

# () -> IOResultE[argparse.NameSpace]
def main():
    parser        = argparse.ArgumentParser(description='SOSS: Secure Object Storage Service')
    subparsers    = parser.add_subparsers(required=True, dest='command')
    upload_parser = subparsers.add_parser('upload')
    upload_parser.add_argument('directory', help='directory to upload')
    upload_parser.add_argument('--config',  '-c', help='directory to upload', default='./config.json', required=True)

    update_meta_marser = subparsers.add_parser('update-meta')
    update_meta_marser.add_argument('--config',  '-c', help='directory to upload', default='./config.json', required=True)


    args = parser.parse_args()
    if args.command == 'upload':
        return upload(args)
    else:
        return IOFailure('未指定的的命令')

if __name__ == '__main__':
    # get_key :: Path -> Reader[str]
    if os.name == 'nt':
        get_key = nt_get_key
    else:
        get_key = posix_get_key

    try:
        main().lash(fail_callback).bind(win_callback)
    except KeyboardInterrupt:
        print('\nSoss Exit\n')
