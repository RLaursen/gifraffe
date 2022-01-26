from random import randint

from gifraffe.gifraffe import *
from gifraffe.gifraffe import __version__


def test_version():
    assert __version__ == '0.1.0'


def test_lzw():
    """Test that lzw encoder decodes into input"""
    test_bytes = bytes(randint(0, 255) for x in range(9999))
    assert test_bytes == bytes(decoder(encoder(test_bytes)))


def test_gif():
    """Test all Gif getters and setters, as many are transformative."""
    from copy import deepcopy
    with open('test.gif', 'rb') as tester:
        f = Gif(tester)
        to_test = {'trailer' if x == 'TRAIL' else 'header' if x == 'HEAD' else x.lower() for x in dir(Gif) if
                   x.isupper()}
        old_data = deepcopy(f.data)
        for i, _ in enumerate(f):
            for x in to_test:
                try:
                    cur = getattr(f, x)
                except KeyError as e:
                    ...
                if x not in {'pte', 'header', 'trailer'}:
                    setattr(f, x, cur)
            for key in {*old_data.keys()} & {*f.data.keys()}:
                if isinstance(old_data[key], dict):
                    for subkey in {*old_data[key].keys()} & {*f.data[key].keys()}:
                        assert old_data[key][subkey] == f.data[key][subkey]
                else:
                    assert old_data[key] == f.data[key]
    with open('testing.gif', 'rb') as tester:
        tester = b''.join([*tester])
    f = Gif(tester)
    assert f.raw == tester
    with open('test.gif', 'rb') as test:
        test = b''.join([*test])
    f.raw = test
    assert f.raw == test


if __name__ == '__main__':
    test_version()
    test_lzw()
    test_gif()