import pytest

from qr2text import Canvas, Error, Path, PathParser, QR


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
    with pytest.raises(Error) as ctx:
        list(PathParser.tokenize(path))
    assert str(ctx.value) == (
        "SVG path syntax error at position 1: w"
    )


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


def test_Canvas_invert():
    canvas = Canvas(5, 3)
    canvas.horizontal_line(0, 0.5, 5)
    canvas.horizontal_line(1, 1.5, 3)
    canvas.horizontal_line(2, 2.5, 1)
    assert str(canvas.invert()) == '\n'.join([
        '.....',
        'X...X',
        'XX.XX',
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


def test_Canvas_unicode_small():
    canvas = Canvas(2, 2)
    canvas.horizontal_line(0, 0.5, 2)
    canvas.horizontal_line(0, 1.5, 1)
    assert canvas.to_unicode_blocks() == '\n'.join([
        '█▀',
    ])


def test_Canvas_to_bytes():
    canvas = Canvas(5, 3)
    canvas.horizontal_line(0, 0.5, 5)
    canvas.horizontal_line(1, 1.5, 3)
    canvas.horizontal_line(2, 2.5, 1)
    assert canvas.to_bytes() == b''.join([
        b'\x00\x00\x00\x00\x00',
        b'\xFF\x00\x00\x00\xFF',
        b'\xFF\xFF\x00\xFF\xFF',
    ])


def test_Canvas_to_bytes_scaled():
    canvas = Canvas(5, 3)
    canvas.horizontal_line(0, 0.5, 5)
    canvas.horizontal_line(1, 1.5, 3)
    canvas.horizontal_line(2, 2.5, 1)
    assert canvas.to_bytes(xscale=2, yscale=3) == b''.join([
        b'\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00',
        b'\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00',
        b'\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00',
        b'\xFF\xFF\x00\x00\x00\x00\x00\x00\xFF\xFF',
        b'\xFF\xFF\x00\x00\x00\x00\x00\x00\xFF\xFF',
        b'\xFF\xFF\x00\x00\x00\x00\x00\x00\xFF\xFF',
        b'\xFF\xFF\xFF\xFF\x00\x00\xFF\xFF\xFF\xFF',
        b'\xFF\xFF\xFF\xFF\x00\x00\xFF\xFF\xFF\xFF',
        b'\xFF\xFF\xFF\xFF\x00\x00\xFF\xFF\xFF\xFF',
    ])


def test_Path():
    canvas = Canvas(5, 3)
    path = Path(canvas)
    path.move_to(2, 1.5)
    path.horizontal_line_rel(6)
    path.move_by(-5, 1)
    path.horizontal_line_rel(-2)
    assert str(canvas) == '\n'.join([
        '.....',
        '..XXX',
        '.XX..',
    ])


def test_Path_draw():
    canvas = Canvas(5, 3)
    path = Path(canvas)
    path.draw([
        ('M', 2, 1.5),
        ('h', 6),
        ('m', -5, 1),
        ('h', -2),
    ])
    assert str(canvas) == '\n'.join([
        '.....',
        '..XXX',
        '.XX..',
    ])


def test_Path_draw_error():
    canvas = Canvas(5, 3)
    path = Path(canvas)
    with pytest.raises(Error) as ctx:
        path.draw([
            ('M', 2, 1.5, 4),
        ])
    assert str(ctx.value) == (
        'Did not expect drawing command M with 3 parameters'
    )


def test_QR_when_empty():
    qr = QR(29)
    assert qr.to_ascii_art(trim=True) == ''
    assert qr.to_ascii_art(trim=True, invert=True) == ''
    assert qr.to_ascii_art(trim=True, big=True) == ''
    assert qr.to_ascii_art(trim=True, big=True, pad=1) == '    \n    '
    assert qr.to_ascii_art(trim=True, pad=1) == '  '
    assert qr.to_ascii_art(trim=True, invert=True, pad=1) == '██'
    assert qr.to_ascii_art(trim=True, big=True, invert=True, pad=1) == (
        '████\n████')
