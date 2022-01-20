import pytest

from qr2text import Canvas, Error, PathParser


@pytest.mark.parametrize("path, expected", [
    ('Z', [('command', 'Z')]),
    ('1', [('number', '1')]),
    ('12.3', [('number', '12.3')]),
    ('-12.3e4', [('number', '-12.3e4')]),
    ('+.3e-4', [('number', '+.3e-4')]),
    ('4e+2', [('number', '4e+2')]),
    ('  \n', []),
    ('1-2', [('number', '1'), ('number', '-2')]),
    ('1,2', [('number', '1'), ('comma', ','), ('number', '2')]),
])
def test_tokenize(path, expected):
    assert list(PathParser.tokenize(path)) == expected


@pytest.mark.parametrize("path", [
    'qwerty',
])
def test_tokenize_error(path):
    with pytest.raises(Error):
        list(PathParser.tokenize(path))


@pytest.mark.parametrize("d, expected", [
    ('M 1, 2', [('M', 1, 2)]),
    ('M 1 2', [('M', 1, 2)]),
    ('M1-2', [('M', 1, -2)]),
    ('M+1-2', [('M', +1, -2)]),
    ('h 42', [('h', 42)]),
    ('h 1.5', [('h', 1.5)]),
    ('h .5', [('h', .5)]),
    ('h 1e-4', [('h', 1e-4)]),
    ('h 1 v 2', [('h', 1), ('v', 2)]),
    ('h 1 v 2', [('h', 1), ('v', 2)]),
    ('z', [('z',)]),
    ('M 1 2 3 4', [('M', 1, 2, 3, 4)]),
    ('M 6,10\nA 6 4 10 1 0 14,10',
     [('M', 6, 10), ('A', 6, 4, 10, 1, 0, 14, 10)]),
])
def test_PathParser_parse(d, expected):
    assert list(PathParser.parse(d)) == expected


def test_Canvas():
    canvas = Canvas(5, 3)
    canvas.horizontal_line(0, 0.5, 5)
    canvas.horizontal_line(1, 1.5, 3)
    canvas.horizontal_line(2, 2.5, 1)
    assert str(canvas) == '\n'.join([
        'XXXXX',
        '.XXX.',
        '..X..',
    ])


def test_Canvas_trim():
    canvas = Canvas(5, 3)
    canvas.horizontal_line(1, 1.5, 3)
    assert str(canvas) == '\n'.join([
        '.....',
        '.XXX.',
        '.....',
    ])
    assert str(canvas.trim()) == '\n'.join([
        'XXX',
    ])


def test_Canvas_pad():
    canvas = Canvas(5, 3)
    canvas.horizontal_line(0, 0.5, 5)
    canvas.horizontal_line(1, 1.5, 3)
    canvas.horizontal_line(2, 2.5, 1)
    assert str(canvas.pad(1, 2, 3, 4)) == '\n'.join([
        '...........',
        '....XXXXX..',
        '.....XXX...',
        '......X....',
        '...........',
        '...........',
        '...........',
    ])


def test_Canvas_unicode():
    canvas = Canvas(5, 3)
    canvas.horizontal_line(0, 0.5, 5)
    canvas.horizontal_line(1, 1.5, 3)
    canvas.horizontal_line(2, 2.5, 1)
    assert canvas.to_unicode_blocks() == '\n'.join([
        '▀███▀',
        '  ▀  ',
    ])
