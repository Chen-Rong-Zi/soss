#!/usr/bin/env python3
import os
import stat
import json
import uuid
import socket
import argparse

import oss2
from   oss2.credentials import EnvironmentVariableCredentialsProvider
from   oss2.utils       import content_md5
from   oss2.compat      import to_bytes

import returns.pointfree as pointfree
import returns.methods   as methods
from returns.pointfree  import map_,      bind
from returns.io         import IOResultE, impure,       impure_safe,   IOFailure, IOSuccess, IOResult
from returns.context    import Reader,    ReaderResult, ReaderResultE, ReaderIOResultE
from returns.result     import safe,      ResultE,      Failure, Result
from returns.pipeline   import flow,      pipe
from returns.iterables  import Fold
from returns.curry      import curry
from returns.converters import flatten
# from viztracer          import VizTracer

from ListHelper         import lmap,      lfilter,   concat, ljoin
from multivalue         import MIterator, MultiValue
from md5                import calculate_md5 as get_local_md5

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
    # print(f"{key = }, {data = }")
    @impure_safe
    def with_bucket(bucket):
        # if hasattr(a := bucket.head_object(key), 'resp'):
            # print(a.resp.headers)
        put_result = bucket.put_object(key, data)
        return f'{key} 上传成功'
        # return f'{key} 上传成功, etag = {put_result.etag}, crc = {put_result.crc}'
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
    print(f'{x = }')
    return x

# get_key :: str -> Reader[str]
def get_key(file_path):
    def with_identifier(identifier):
        return identifier['hostname'] + file_path
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

# check_md5_integrity :: (str, str) -> IOResultE(bool)
def check_md5_integrity(filepath, key):
    def with_env(env):
        return IOResultE.do(
            local_md5 == remote_md5
            for fhandle    in get_file_handler(filepath)
            for local_md5  in get_local_md5(fhandle)
            for remote_md5 in get_remote_md5(key)(env['bucket'])
        )
    return Reader(with_env)

# conditional_exit :: str -> IOResultE[str]
def conditional_exit(filepath):
    def with_env(env):
        return check_md5_integrity(filepath, env['key'])(env).bind(
            lambda pass_md5_verify : IOFailure(f'{filepath} 在oss中已存在!') if pass_md5_verify else IOSuccess(f'Did not Pass md5 verification')
        )
        return IOFailure(f"{filepath} already exitsts in the cloud!")
    return Reader(with_env)

# conditional_upload :: str -> Reader[IOResultE[str]]
def conditional_upload(filepath):
    # with_env :: dict -> IOResultE[str]
    def with_env(env):
        items   = list(env.items()) + [('key', get_key(filepath)(env['identifier']))]
        new_env = dict(items)
        return key_exists(new_env['key'])(env['bucket']).bind(
            lambda exists : IOFailure('File Exists') if exists else IOSuccess("File Not Exists")
        ).lash(
            lambda _ : conditional_exit(filepath)(new_env)
        ).bind(
            lambda _ : upload_one(filepath)(new_env)
        )
    return Reader(with_env)

# is_normal_file :: str -> IOResultE
def is_normal_file(filepath):
    stat_file   = impure_safe(lambda file      : os.stat(file))
    normal_file = impure_safe(lambda file_stat : stat.S_ISREG(file_stat.st_mode))
    return IOResultE.do(
        is_normal
        for filestat  in stat_file(filepath)
        for is_normal in normal_file(filestat)
    )

# truey_value :: IOResultE[any] -> bool
def truey_value(ior_value):
    return ior_value == IOResultE.from_value(True)

# str -> IOResultE[MIterator[str]]
def collect_files(directory):
    if not os.path.isdir(directory):
        return IOFailure(FileNotFoundError(f'"{directory}" is not exists, thus can not be collected'))
    if not os.path.isdir(directory):
        return IOFailure(IsADirectoryError(f'"{directory}" is not a directory, thus cant not be collected'))

    # Tuple[str, str, List[str]] -> MIterator[str]
    def tu0_plus_tu2(tu):
        return flow(
            MIterator(tu[2]),
            map_(concat(tu[0] + '/'))
        )
    # str -> bool
    normal_file = pipe(is_normal_file, truey_value)

    return flow(
        IOResultE.from_value(directory),                              # IOResultE[str]
        bind(impure_safe(os.path.abspath)),                           # IOResultE[Str]
        bind(impure_safe(pipe(os.walk, MIterator))),                  # IOResultE[MIterator[Tuple[Str]]]
        map_(bind(tu0_plus_tu2)),                                     # IOResultE(MIterator[str])
        map_(lambda iterator : iterator.filter(normal_file)),              # IOResultE[MIterator[str]]
    )

# upload_dir :: (str, ossbase) -> IOResultE[str]
def upload_dir(env, bucket):
    new_env = {
        'bucket'     : bucket,
        'identifier' : env['identifier']
    }
    print(env['directory'])
    return IOResultE.do(
        flow(
            files,                                                  # MIterator[str]
            map_(pipe(conditional_upload, ReaderIOResultE)),        # MIterator[ReaderIOResultE[str]]
            map_(lambda x : x(new_env)),                                 # MIterator[IOResultE[str]]
        )
        for files in collect_files(env['directory'])
    )

# oss_login :: dict -> IOResultE[oss2.Bucket]
def oss_login(env):
    # print(env)
    return flow(
        IOResultE.from_value(curry(oss2.Bucket)),
        IOResultE.from_ioresult(make_auth()).apply,
        IOResultE.from_value(env['endpoint']).apply,
        IOResultE.from_value(env['bucket']).apply
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
            'directory'  : args.directory,
        }
        for config     in read_config(args.config)
        for identifier in get_identifier()
    )

# win_callback :: List[IOResultE[str]] -> IOResultE[None]
def win_callback(lst):
    # return IOResultE.from_value(1)
    return IOResultE.from_value(
        lmap(lambda x : print(x._inner_value._inner_value))(lst)
    )

# win_callback :: Exception -> IOResultE[None]
def fail_callback(error):
    return  IOFailure(print(error))

# upload_dir_ :: args -> IOResultE[str]
def upload(args):
    a = flatten(IOResultE.do(
        upload_dir(env, bucket)            # IOResultE[str]
        for env    in make_env(args)
        for bucket in oss_login(env['config'])
    ))
    return a

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
        a = upload(args)
        return a
    elif args.command == 'update-meta':
        return IOResultE.from_value(0)
    else:
        return IOResultE.from_failure(Failure('未指定的的命令'))

if __name__ == '__main__':
    main().lash(fail_callback).bind(win_callback)
