import functools


def wrapped(
    a: int,
    b: "tuple[int, int]" = (1, 2),
) -> int:
    return a


@functools.lru_cache(maxsize=None)
def cached(x):
    return x * 2


async def fetch(url, *, timeout=(3, 10)):
    async with session(url) as s:
        return await s.read()


def outer():
    def inner(y):
        return y + 1
    # A comment at the end of outer's body, then a blank line.

    return inner


def one_line(): return 1


class Shape:
    @property
    def area(self) -> float:
        return 0.0

    @staticmethod
    def make(
        kind,
    ):
        return {
            "kind": kind,
        }


square = lambda x: x * x


def tail():
    value = compute(
        1,
        2,
    )
# A comment at the margin, inside the body.
    return value
