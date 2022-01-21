#!/usr/bin/env python3
"""
Convert SVG images containing QR codes generated by PyQRCode to ASCII art,
for displaying in a terminal.
"""

import argparse
import os
import re
import sys
import xml.etree.ElementTree
from typing import BinaryIO, Iterable, List, Optional, Tuple, Union


try:
    from pyzbar import pyzbar
except ImportError:  # pragma: nocover
    pyzbar = None


__version__ = '1.0.2.dev0'


class Error(Exception):
    pass


FULL_CHARS = ' \u2588'
HALF_CHARS = ' \u2580\u2584\u2588'  # blank, upper, lower, full block


SVG_NS = '{http://www.w3.org/2000/svg}'

FLOAT_REGEX = r'[-+]?(?:\d*\.\d+|\d+)(?:[eE][-+]?\d+)?'
TRANSFORM_SCALE_RX = re.compile(f'^scale[(]({FLOAT_REGEX})[)]$')


Token = Tuple[str, str]
PathCommand = Tuple[str, Tuple[float, ...]]
FileNameOrFileObject = Union[os.PathLike, BinaryIO]


class PathParser:

    # https://svgwg.org/svg2-draft/paths.html#PathDataBNF

    TOKEN_RX = re.compile(
        '|'.join([
            r'(?P<wsp>\s+)',
            r'(?P<comma>,)',
            f'(?P<number>{FLOAT_REGEX})',
            r'(?P<command>[MmZzLlHhVvCcSsQqTtAa])',
            r'(?P<error>.)',  # must be last
        ])
    )

    @classmethod
    def tokenize(cls, path: str) -> Iterable[Tuple[str, str]]:
        for m in cls.TOKEN_RX.finditer(path):
            kind = m.lastgroup
            value = m.group()
            if kind == 'wsp':
                continue
            if kind == 'error':
                pos = m.start()
                raise Error(
                    f'SVG path syntax error at position {pos}: {value}')
            assert kind is not None  # for mypy
            yield (kind, value)

    @classmethod
    def parse(cls, path: str) -> Iterable[PathCommand]:
        command = None
        args: List[float] = []
        for kind, value in cls.tokenize(path):
            if kind == 'command':
                if command:
                    yield (command, tuple(args))
                command, args = value, []
            elif kind == 'number':
                if command is None:
                    raise Error(
                        f'SVG path should start with a command: {value}')
                args.append(float(value))
            elif kind == 'comma':
                # let's just skip these
                continue
            else:  # pragma: nocover
                assert False, f'did not expect {kind}'
        if command:
            yield (command, tuple(args))


class Canvas:

    def __init__(self, width: int, height: int,
                 pixels: Optional[List[List[int]]] = None) -> None:
        assert width >= 0
        assert height >= 0
        self.width = width
        self.height = height
        if pixels is None:
            self.pixels = [[0] * width for _ in range(height)]
        else:
            assert len(pixels) == height
            if height > 0:
                assert len(pixels[0]) == width
            self.pixels = pixels

    def horizontal_line(self, x: float, y: float, width: float) -> None:
        assert width > 0
        # PyQRCode draws 1-pixel thick horizontal lines, which means the
        # x coordinates are whole numbers, and the y coordinate is shifted by
        # 0.5 to point to the middle of the pixel
        y = int(y - 0.5)
        if 0 <= y < self.height:
            for x in range(int(x), int(x + width)):
                if 0 <= x < self.width:
                    self.pixels[y][x] = 1

    def to_bytes(self, values: Tuple[bytes, bytes] = (b'\xFF', b'\0'),
                 xscale: int = 1, yscale: int = 1) -> bytes:
        return b''.join(
            b''.join(values[px] * xscale for px in row) * yscale
            for row in self.pixels
        )

    def to_ascii_art(self, chars: str = FULL_CHARS, xscale: int = 1) -> str:
        return '\n'.join(
            ''.join(chars[px] * xscale for px in row) for row in self.pixels)

    def to_unicode_blocks(self, chars: str = HALF_CHARS) -> str:
        pixels = self.pixels
        if self.height % 2 == 1:
            pixels = pixels + [[0] * self.width]
        return '\n'.join(
            ''.join(chars[pixels[y+1][x] * 2 + pixels[y][x]]
                    for x in range(self.width))
            for y in range(0, self.height, 2))

    def __str__(self) -> str:
        return self.to_ascii_art('.X')

    def line_is_blank(self, y: int) -> bool:
        assert 0 <= y < self.height
        return not any(self.pixels[y])

    def column_is_blank(self, x: int) -> bool:
        assert 0 <= x < self.width
        return not any(self.pixels[y][x] for y in range(self.height))

    def trim(self) -> 'Canvas':
        top = 0
        while top < self.height and self.line_is_blank(top):
            top += 1
        bottom = self.height
        while bottom > top and self.line_is_blank(bottom - 1):
            bottom -= 1
        left = 0
        while left < self.width and self.column_is_blank(left):
            left += 1
        right = self.width
        while right > left and self.column_is_blank(right - 1):
            right -= 1
        return self.__class__(right - left, bottom - top, [
            row[left:right] for row in self.pixels[top:bottom]
        ])

    def pad(self, top: int, right: int, bottom: int, left: int) -> 'Canvas':
        assert top >= 0
        assert right >= 0
        assert bottom >= 0
        assert left >= 0
        new_width = self.width + left + right
        new_height = self.height + top + bottom
        left_pad = [0] * left
        right_pad = [0] * right
        top_pad = [[0] * new_width for _ in range(top)]
        bottom_pad = [[0] * new_width for _ in range(bottom)]
        return self.__class__(new_width, new_height, top_pad + [
            left_pad + row + right_pad for row in self.pixels
        ] + bottom_pad)

    def invert(self) -> 'Canvas':
        return self.__class__(self.width, self.height, [
            [1 - px for px in row] for row in self.pixels
        ])


class Path:

    def __init__(self, canvas: Canvas) -> None:
        # Technically the very first path drawing command must be an absolute
        # move_to, so the initial coordinates are undefined.
        self.x = 0.0
        self.y = 0.0
        self.canvas = canvas

    def move_to(self, x: float, y: float) -> None:
        self.x = x
        self.y = y

    def move_by(self, dx: float, dy: float) -> None:
        self.x += dx
        self.y += dy

    def horizontal_line_rel(self, dx: float) -> None:
        if dx > 0:
            self.canvas.horizontal_line(self.x, self.y, dx)
        elif dx < 0:
            self.canvas.horizontal_line(self.x + dx, self.y, -dx)
        self.x += dx

    def draw(self, commands: Iterable[PathCommand]) -> None:
        for cmd, args in commands:
            if cmd == 'M' and len(args) == 2:
                self.move_to(*args)
            elif cmd == 'm' and len(args) == 2:
                self.move_by(*args)
            elif cmd == 'h' and len(args) == 1:
                self.horizontal_line_rel(*args)
            else:
                raise Error(f'Did not expect drawing command {cmd}'
                            f' with {len(args)} parameters')


class QR:

    def __init__(self, size: int) -> None:
        self.size = size
        self.canvas = Canvas(size, size)

    def to_ascii_art(
        self,
        chars: str = HALF_CHARS,
        big: bool = False,
        trim: bool = False,
        pad: int = 0,
        invert: bool = False,
    ) -> str:
        canvas = self.canvas
        if trim:
            canvas = canvas.trim()
        if pad:
            canvas = canvas.pad(pad, pad, pad, pad)
        if invert:
            canvas = canvas.invert()
        if big:
            return canvas.to_ascii_art(chars[::3], 2)
        else:
            return canvas.to_unicode_blocks(chars)

    @classmethod
    def get_dim(cls, node: xml.etree.ElementTree.Element, attr: str) -> float:
        value = node.get(attr)
        if value is None:
            raise Error(f"Image {attr} is not specified")
        try:
            return float(value)
        except ValueError:
            raise Error(f"Couldn't parse {attr}: {value}")

    @classmethod
    def from_svg(cls, fileobj: FileNameOrFileObject) -> 'QR':
        try:
            tree = xml.etree.ElementTree.parse(fileobj)
        except xml.etree.ElementTree.ParseError as e:
            raise Error(f"Couldn't parse SVG: {e}")
        root = tree.getroot()
        if root.tag != f"{SVG_NS}svg":
            raise Error(f"This is not an SVG image: <{root.tag}>")
        if root.get('class') != 'pyqrcode':
            raise Error("The image was not generated by PyQRCode")
        viewbox = root.get('viewBox')
        if viewbox:
            try:
                x, y, width, height = map(float, viewbox.split())
            except ValueError:
                raise Error(f"Couldn't parse viewbox: {viewbox}")
            if (x, y) != (0, 0):
                raise Error(f"Unexpected viewbox origin: {viewbox}")
        else:
            width = cls.get_dim(root, 'width')
            height = cls.get_dim(root, 'height')
        if width != height:
            raise Error(f"Image is not square: {width} x {height}")
        path = root.find(f"{SVG_NS}path[@class='pyqrline']")
        if path is None:
            raise Error("Did not find the QR code in the image")
        # path.get('transform') should be something like "scale(8)"
        # path.get('stroke') should be '#000'
        # path.get('d') is the QR code itself, encoded as drawing commands
        transform = path.get('transform')
        if transform:
            m = TRANSFORM_SCALE_RX.match(transform)
            if not m:
                raise Error(f"Couldn't parse transform: {transform}")
            scale = float(m.group(1))
        else:
            scale = 1
        size = int(width / scale)
        qr = cls(size)
        d = path.get('d')
        if d is None:
            raise Error("SVG <path> element has no 'd' attribute")
        Path(qr.canvas).draw(PathParser.parse(d))
        return qr

    def decode(self) -> Optional[bytes]:
        if pyzbar is None:
            return None

        # Note: experiments with pyqrcode and zbarimg show that I need
        # pyqrcode.create('text').svg('file.svg', background='#fff', scale=2)
        # to have recognizable qr codes.  no background or scale=1 make zbarimg
        # fail to find any codes.
        scale = 2
        image_data = (self.canvas.to_bytes(xscale=scale, yscale=scale),
                      self.size * scale, self.size * scale)
        res = pyzbar.decode(image_data, symbols=[pyzbar.ZBarSymbol.QRCODE])
        assert 0 <= len(res) <= 1
        if not res:
            return None
        assert isinstance(res[0].data, bytes)  # for mypy
        return res[0].data


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Convert PyQRCode SVG images to ASCII art")
    parser.add_argument("--version", action="version",
                        version="%(prog)s version " + __version__)
    parser.add_argument("--black-background", action="store_false",
                        dest='invert', default=False,
                        help='terminal is white on black (default)')
    parser.add_argument("--white-background", "--invert", action="store_true",
                        dest='invert',
                        help='terminal is black on white')
    parser.add_argument("--big", action="store_true",
                        dest='big', default=False,
                        help='use full unicode blocks instead of half blocks')
    parser.add_argument("--trim", action="store_true",
                        dest='trim', default=False,
                        help='remove empty border')
    parser.add_argument("--pad", type=int, default=0,
                        help='pad with empty border')
    parser.add_argument("--decode", action="store_true",
                        default=(pyzbar is not None),
                        help=("decode the QR codes"
                              " (default if libzbar is available)"))
    parser.add_argument("--no-decode", action="store_false",
                        dest="decode",
                        help="don't decode the QR codes")
    parser.add_argument("filename", type=argparse.FileType('rb'), nargs='+',
                        help='SVG file with the QR code (use - for stdin)')
    args = parser.parse_args()

    if args.decode and pyzbar is None:
        print("libzbar is not available, --decode ignored", file=sys.stderr)

    rc = 0
    try:
        for filename in args.filename:
            with filename as fp:
                try:
                    qr = QR.from_svg(fp)
                except Error as e:
                    print(f"{filename.name}: {e}", file=sys.stderr, flush=True)
                    rc = 1
                    continue
            print(qr.to_ascii_art(invert=not args.invert, big=args.big,
                                  trim=args.trim, pad=args.pad))
            if args.decode:
                data = qr.decode()
                if data:
                    print(data.decode(errors='replace'))
            sys.stdout.flush()
    except KeyboardInterrupt:
        print("^C", file=sys.stderr)
        rc = 1
    except Error as e:  # pragma: nocover -- currently this cannot happen
        print(e, file=sys.stderr)
        rc = 1
    sys.exit(rc)


if __name__ == "__main__":
    main()
