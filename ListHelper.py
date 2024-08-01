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

# lmap :: (a -> b) -> List[a] -> Iterator[List[b]]
def imap(fn):
    def inner(lst):
        return map(fn, lst)
    return inner

#  # lfilter :: (a -> bool) -> List[a] -> Iterator[List[a]]
#  def ifilter(fn):
#      def inner(lst):
#          return filter(fn, lst)
#      return inner
#  
#  # ljoin ::  List[List[a]] -> List[a]
#  def ijoin(lst):
#      yield sum(lst, [])

# iunit :: a -> Iterator[a]
def iunit(*args):
    for i in args:
        yield i

# imap :: (a -> b) -> Iterator[a] -> Iterable[b]
def imap(fn):
    def inner(iter):
        for it in iter:
            yield fn(it)
    return inner

# ijoin :: Iterable[Iterable[a]] -> Iterator[a]
def ijoin(iter_iter):
    for it0 in iter_iter:
        for it1 in it0:
            yield it1

# ibind :: Iterator[a] -> (a -> Iterator[b]) -> Iterator[b]
def ibind(iter):
    def inner(fn):
        return ijoin(imap(fn)(iter))
    return inner

# concat :: str -> str -> str
def concat(a):
    def inner(b):
        return a + b
    return inner

# ap :: Iterator[Callable[[a], b]] -> Iterator[a] -> Iterator[b]
def ap(mf):
    def inner(mx):
        for f in mf:
            for x in mx:
                yield f(x)
    return inner


def laws():
    def f(n):
        yield n
        yield n + 1
        yield n + 2
    def g(n):
        return
        yield

    # left identity
    left  = ibind(iunit(0))(f)
    right = f(0)
    assert list(left) == list(right)

    # right identity
    make_data = lambda  : iunit(*range(1, 100, 10))
    left  = ibind(make_data())(iunit)
    right = make_data()
    assert list(left) == list(right)

    # Associative law
    left  = ibind(ibind(iunit(10))(f))(g)
    right = ibind(iunit(10))(lambda x : ibind(ibind(x)(f))(g))
    assert list(left) == list(right)
