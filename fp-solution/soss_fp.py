import json

from returns.pointfree import map_, bind
from returns.io        import IOResultE, impure, impure_safe, IO, IOResult
from returns.result    import safe, ResultE
from returns.pipeline  import flow, pipe

@impure_safe
# read_config :: str -> IOResultE[str]
def read_file(config_path):
    with open(config_path, 'r') as f:
        return f.read()

@safe(exceptions=(json.decoder.JSONDecodeError,))
# parse_json :: str -> ResultE[dict]
def parse_json(string):
    return json.loads(string)

# parse_json_ioresult :: str -> IOResultE[dict]
def parse_json_ioresult(string):
    return pipe(parse_json, IOResultE.from_result)(string)

# read_config :: str -> IOResultE[dict]
def read_config(config_path):
    return flow(
        config_path,
        read_file,
        bind(parse_json_ioresult)
    )

def main():
    return read_config('../config.json')

if __name__ == '__main__':
    a = main()
