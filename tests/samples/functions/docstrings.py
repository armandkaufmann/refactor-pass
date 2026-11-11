"""The module's docstring,
over two lines."""

import os


class Shelf:
    """A class docstring on one line."""

    def __init__(self, books):
        """One line."""
        self.books = books

    def describe(self):
        """Several lines.

        With a blank line inside, and "quotes".
        """
        text = """Assigned, so code:
a second line
"""
        print("""Passed, so code:
also code""")
        return text

    def report(self):
        r'''A raw docstring.'''
        # A comment.
        "A string on its own, after the docstring: documentation too."
        return """Returned,
so code."""


def outside(x):
    '''Single quotes.'''
    return os.path.join(x, f"{x}")
