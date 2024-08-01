#!/usr/bin/env python3
import os
import stat
import json
import uuid
import socket
import argparse

import oss2
from   oss2.credentials import EnvironmentVariableCredentialsProvider
print('pass')

from returns.pointfree  import map_,      bind
from returns.io         import IOResultE, impure,       impure_safe,   IOFailure
from returns.context    import Reader,    ReaderResult, ReaderResultE, ReaderIOResultE
from returns.result     import safe,      ResultE,      Failure
from returns.pipeline   import flow,      pipe
from returns.iterables  import Fold
from returns.curry      import curry
from returns.converters import flatten

from ListHelper         import lmap,      lfilter,   concat, ljoin
from multivalue         import MIterator, MultiValue
# from viztracer          import VizTracer

@impure_safe
# read_file :: str -> IOResultE[str]
def read_file(file_path):
    with open(file_path, 'r', encoding = 'utf-8') as f:
        return f.read()

@impure_safe
# read_data :: str -> IOResultE[byte]
def read_data(file_path):
    with open(file_path, 'rb') as f:
        # print(f"read {file_path}")
        return f.read()

@safe(exceptions=(json.decoder.JSONDecodeError,))
# parse_json :: str -> ResultE[dict]
def parse_json(string):
    return json.loads(string)

# parse_json_ioresult :: str -> IOResultE[dict]
def parse_json_ioresult(string):
    return pipe(parse_json, IOResultE.from_result)(string)

@curry
# upload_data :: (str, Union[str, byte]) -> Reader[IOResultE[Union[str, byte]]]
def upload_data(key, data):
    @impure_safe
    def with_bucket(bucket):
        # bucket.put_object(key, data)
        return f'{key} Uploaded Successfully'
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

# get_key :: str -> Rprinieader[str]
def get_key(file_path):
    def with_identifier(identifier):
        return identifier['hostname'] + file_path
    return Reader(with_identifier)

# upload_one :: str -> Reader[IOResultE[str]]
def upload_one(file_path):
    # with_identifier :: dict -> IOResultE[str]
    def with_identifier(env):
        key = lambda filepath : get_key(filepath)(env['identifier'])
        return flow(
            Reader.from_value(upload_data), # IOResultE[Tuple[str, str|bytes], bucket], str]
            Reader(key).apply,              # ReaderIOResultE[str,  str]
            Reader(read_data).apply         # ReaderIOResultE[str,  str]
        )(file_path)(env['bucket'])
    return Reader(with_identifier)

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

# str -> IOResultE[MIterater[str]]
def collect_files(directory):
    if not os.path.isdir(directory):
        return IOFailure(FileNotFoundError(f'"{directory}" is not exists, thus can not be collected'))
    if not os.path.isdir(directory):
        return IOFailure(IsADirectoryError(f'"{directory}" is not a directory, thus cant not be collected'))

    # Tuple[str, str, List[str]] -> MIterater[str]
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
        bind(impure_safe(pipe(os.walk, MIterator))),                  # IOResultE[MIterater[Tuple[Str]]]
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
            files,                                                        # MIterator[str]
            map_(pipe(upload_one, ReaderIOResultE)),                      # MIterator[ReaderIOResultE[str]]
            map_(lambda x : x(new_env)),                                        # MIterator[IOResultE[str]]
        )
            # lambda lst : Fold.collect(lst, ReaderIOResultE.from_value(())),    # ReaderIOResultE[str]
        for files in collect_files(env['directory'])
    )

# oss_login :: dict -> IOResultE[oss2.Bucket]
def oss_login(env):
    # print(env)
    return flow(
        IOResultE.from_value(curry(oss2.Bucket)),
        # trace,
        IOResultE.from_ioresult(make_auth()).apply,
        # trace,
        IOResultE.from_value(env['endpoint']).apply,
        # trace,
        IOResultE.from_value(env['bucket']).apply
    )

# () -> IOResultE[argparse.NameSpace]
def parse():
    parser        = argparse.ArgumentParser(description='SOSS: Secure Object Storage Service')
    subparsers    = parser.add_subparsers(required=True, dest='command')
    upload_parser = subparsers.add_parser('upload')
    upload_parser.add_argument('directory', help='directory to upload')
    upload_parser.add_argument('--config',  '-c', help='directory to upload', default='./config.json', required=True)
    return IOResultE.from_value(parser.parse_args())

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

# make_env :: () -> IOResultE[dict]
def make_env():
    return IOResultE.do(
        {
            'config'     : config,
            'identifier' : identifier,
            'directory'  : cmd_input.directory,
        }
        for cmd_input  in parse()
        for config     in read_config(cmd_input.config)
        for identifier in get_identifier()
    )

# win_callback :: List -> IOResultE[None]
def win_callback(lst):
    return IOResultE.from_value(lmap(trace)(lst))

# win_callback :: Exception -> IOResultE[None]
def fail_callback(error):
    return  IOFailure(print(str(error)))

def main():
    return flatten(IOResultE.do(
        upload_dir(env, bucket)            # IOResultE[MIterator[str]]
        for env    in make_env()
        for bucket in oss_login(env['config'])
    ))

if __name__ == '__main__':
    a = main().lash(fail_callback).bind(win_callback)
