# lmap :: (a -> b) -> List[a] -> List[b]
def lmap(fn):
    def inner(lst):
        return list(map(fn, lst))
    return inner

# lfilter :: (a -> bool) -> List[a] -> List[a]
def lfilter(fn):
    def inner(lst):
        return list(filter(fn, lst))
    return inner


# ljoin :: List[List[a]] -> List[a]
def ljoin(lst):
    return sum(lst, [])

# concat :: str -> str -> str
def concat(a):
    def inner(b):
        return a + b
    return inner
