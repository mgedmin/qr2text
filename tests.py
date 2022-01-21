import sys
from io import BytesIO

import pyqrcode
import pytest

import qr2text
from qr2text import QR, Canvas, Error, Path, PathParser, main


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
def test_PathParser_tokenize(path, expected):
    assert list(PathParser.tokenize(path)) == expected


def test_PathParser_tokenize_error():
    path = 'qwerty'
    with pytest.raises(Error) as ctx:
        list(PathParser.tokenize(path))
    assert str(ctx.value) == (
        "SVG path syntax error at position 1: w"
    )


@pytest.mark.parametrize("d, expected", [
    ('M 1, 2', [('M', (1, 2))]),
    ('M 1 2', [('M', (1, 2))]),
    ('M1-2', [('M', (1, -2))]),
    ('M+1-2', [('M', (+1, -2))]),
    ('h 42', [('h', (42,))]),
    ('h 1.5', [('h', (1.5,))]),
    ('h .5', [('h', (.5,))]),
    ('h 1e-4', [('h', (1e-4,))]),
    ('h 1 v 2', [('h', (1,)), ('v', (2,))]),
    ('h 1 v 2', [('h', (1,)), ('v', (2,))]),
    ('z', [('z', ())]),
    ('M 1 2 3 4', [('M', (1, 2, 3, 4))]),
    ('M 6,10\nA 6 4 10 1 0 14,10',
     [('M', (6, 10)), ('A', (6, 4, 10, 1, 0, 14, 10))]),
])
def test_PathParser_parse(d, expected):
    assert list(PathParser.parse(d)) == expected


def test_PathParser_parse_error():
    path = '42'
    with pytest.raises(Error) as ctx:
        list(PathParser.parse(path))
    assert str(ctx.value) == (
        "SVG path should start with a command: 42"
    )


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
        ('M', (2, 1.5)),
        ('h', (6,)),
        ('m', (-5, 1)),
        ('h', (-2,)),
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
            ('M', (2, 1.5, 4)),
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
    assert qr.decode() is None


@pytest.mark.parametrize("kwargs", [
    dict(),
    dict(scale=4),
    dict(background='#fff'),
    dict(omithw=True),
    dict(scale=3, omithw=True),
    dict(scale=3.5),
])
def test_QR_from_svg(kwargs):
    buffer = BytesIO()
    code = pyqrcode.create('A', error='L')
    code.svg(buffer, **kwargs)
    buffer.seek(0)
    qr = QR.from_svg(buffer)
    assert qr.to_ascii_art(trim=True) == '\n'.join([
        '█▀▀▀▀▀█  █▄█▀ █▀▀▀▀▀█',
        '█ ███ █ ▀█ █▀ █ ███ █',
        '█ ▀▀▀ █   ▀ █ █ ▀▀▀ █',
        '▀▀▀▀▀▀▀ █▄▀▄█ ▀▀▀▀▀▀▀',
        '▀██▄▀▀▀█▀▀█▀ ▀█   █▄ ',
        ' ▄ ▀▀█▀▄▄▄█ ▀ ▄ ▀ ▄▄▀',
        '▀▀▀ ▀▀▀ ██ ▄▀▄▀▄▀▄▀▀▀',
        '█▀▀▀▀▀█ █▄██▄█▀█▄█▀▄ ',
        '█ ███ █ ▀▄ ▀ ▀█▀ ▀█▄▀',
        '█ ▀▀▀ █ █▀█ ▀ ▄ ▀ ▄▄█',
        '▀▀▀▀▀▀▀ ▀▀▀ ▀ ▀ ▀ ▀ ▀',
    ])
    assert qr.decode() == b'A'


svg = 'svg xmlns="http://www.w3.org/2000/svg"'


@pytest.mark.parametrize("svg, error", [
    ('<html></html>',
     'This is not an SVG image: <html>'),
    (f'<{svg}></svg>',
     'The image was not generated by PyQRCode'),
    (f'<{svg} class="pyqrcode" viewBox="0 0"></svg>',
     "Couldn't parse viewbox: 0 0"),
    (f'<{svg} class="pyqrcode" viewBox="1 1 5 5"></svg>',
     "Unexpected viewbox origin: 1 1 5 5"),
    (f'<{svg} class="pyqrcode"></svg>',
     "Image width is not specified"),
    (f'<{svg} class="pyqrcode" width="5" height="6"></svg>',
     "Image is not square: 5.0 x 6.0"),
    (f'<{svg} class="pyqrcode" width="5mm" height="5mm"></svg>',
     "Couldn't parse width: 5mm"),
    (f'<{svg} class="pyqrcode" viewBox="0 0 5 5"></svg>',
     "Did not find the QR code in the image"),
    (f'<{svg} class="pyqrcode" viewBox="0 0 5 5">'
     '<path class="pyqrline" transform="translate(4.5)" />'
     '</svg>',
     "Couldn't parse transform: translate(4.5)"),
    (f'<{svg} class="pyqrcode" viewBox="0 0 5 5">'
     '<path class="pyqrline" />'
     '</svg>',
     "SVG <path> element has no 'd' attribute"),
])
def test_QR_from_svg_errors(svg, error):
    buffer = BytesIO(svg.encode())
    with pytest.raises(Error) as ctx:
        QR.from_svg(buffer)
    assert str(ctx.value) == error


def test_main_help(monkeypatch):
    monkeypatch.setattr(sys, 'argv', ['qr2text', '--help'])
    with pytest.raises(SystemExit):
        main()


def test_main(monkeypatch, tmp_path, capsys):
    filename = str(tmp_path / 'hello.svg')
    pyqrcode.create('hello').svg(filename)
    monkeypatch.setattr(sys, 'argv', ['qr2text', filename])
    with pytest.raises(SystemExit) as exc:
        main()
    assert exc.value.code == 0
    assert capsys.readouterr().out == '\n'.join([
        '█████████████████████████████',
        '█████████████████████████████',
        '████ ▄▄▄▄▄ █████▄█ ▄▄▄▄▄ ████',
        '████ █   █ █ ▄▀▄██ █   █ ████',
        '████ █▄▄▄█ ███ ▄▄█ █▄▄▄█ ████',
        '████▄▄▄▄▄▄▄█▄▀ ▀▄█▄▄▄▄▄▄▄████',
        '████▀█▀▄▄▀▄ █  ▄██▀▀▀  ██████',
        '████  █▄▀ ▄▀▄ █▄▀ █ ▀█ ▄▄████',
        '█████▄██▄▄▄▄ █▀█▀▀ ▄▄ █ █████',
        '████ ▄▄▄▄▄ █▄▀ ▀█▀▄██▀ ▀▀████',
        '████ █   █ █ █ ▀ ▀██ ▄█▄▄████',
        '████ █▄▄▄█ ██▀  ▀        ████',
        '████▄▄▄▄▄▄▄███▄██▄███████████',
        '█████████████████████████████',
        '▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀',
        'hello',
    ]) + '\n'


def test_main_encode_text(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(sys, 'argv', ['qr2text', '--encode', 'hello'])
    with pytest.raises(SystemExit) as exc:
        main()
    assert exc.value.code == 0
    assert capsys.readouterr().out == '\n'.join([
        '█████████████████████████████',
        '█████████████████████████████',
        '████ ▄▄▄▄▄ █████▄█ ▄▄▄▄▄ ████',
        '████ █   █ █ ▄▀▄██ █   █ ████',
        '████ █▄▄▄█ ███ ▄▄█ █▄▄▄█ ████',
        '████▄▄▄▄▄▄▄█▄▀ ▀▄█▄▄▄▄▄▄▄████',
        '████▀█▀▄▄▀▄ █  ▄██▀▀▀  ██████',
        '████  █▄▀ ▄▀▄ █▄▀ █ ▀█ ▄▄████',
        '█████▄██▄▄▄▄ █▀█▀▀ ▄▄ █ █████',
        '████ ▄▄▄▄▄ █▄▀ ▀█▀▄██▀ ▀▀████',
        '████ █   █ █ █ ▀ ▀██ ▄█▄▄████',
        '████ █▄▄▄█ ██▀  ▀        ████',
        '████▄▄▄▄▄▄▄███▄██▄███████████',
        '█████████████████████████████',
        '▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀',
        'hello',
    ]) + '\n'


def test_main_no_libzbar(monkeypatch, tmp_path, capsys):
    filename = str(tmp_path / 'hello.svg')
    pyqrcode.create('hello').svg(filename)
    monkeypatch.setattr(sys, 'argv', ['qr2text', '--decode', filename])
    monkeypatch.setattr(qr2text, 'pyzbar', None)
    with pytest.raises(SystemExit) as exc:
        main()
    assert exc.value.code == 0
    assert capsys.readouterr().err == '\n'.join([
        'libzbar is not available, --decode ignored',
    ]) + '\n'


def test_main_error(monkeypatch, tmp_path, capsys):
    hello_svg = tmp_path / 'hello.svg'
    hello_svg.write_text('this is not an SVG file\n')
    monkeypatch.setattr(sys, 'argv', ['qr2text', str(hello_svg)])
    with pytest.raises(SystemExit) as exc:
        main()
    assert exc.value.code == 1
    assert capsys.readouterr().err == '\n'.join([
        f"{hello_svg}: Couldn't parse SVG: syntax error: line 1, column 0",
    ]) + '\n'


def raise_keyboard_interrupt(*args, **kw):
    raise KeyboardInterrupt


def test_main_interrupt(monkeypatch, tmp_path, capsys):
    hello_svg = tmp_path / 'hello.svg'
    hello_svg.write_text('this is not an SVG file\n')
    monkeypatch.setattr(sys, 'argv', ['qr2text', str(hello_svg)])
    monkeypatch.setattr(QR, 'from_svg', raise_keyboard_interrupt)
    with pytest.raises(SystemExit) as exc:
        main()
    assert exc.value.code == 1
    assert capsys.readouterr().err == '\n'.join([
        "^C",
    ]) + '\n'
