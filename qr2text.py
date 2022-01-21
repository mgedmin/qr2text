#!/usr/bin/env python3
"""
Convert SVG images containing QR codes generated by PyQRCode to ASCII art,
for displaying in a terminal.
"""

import argparse
import re
import sys
import xml.etree.ElementTree


__version__ = '0.2'


class Error(Exception):
    pass


FULL_CHARS = ' \u2588'
HALF_CHARS = ' \u2580\u2584\u2588'  # blank, upper, lower, full block


SVG_NS = '{http://www.w3.org/2000/svg}'

TRANSFORM_SCALE_RX = re.compile(r'^scale[(](\d+)[)]$')


class PathParser:

    # https://svgwg.org/svg2-draft/paths.html#PathDataBNF

    TOKEN_RX = re.compile(
        '|'.join([
            r'(?P<wsp>\s+)',
            r'(?P<comma>,)',
            r'(?P<number>[-+]?(?:\d*\.\d+|\d+)(?:[eE][-+]?\d+)?)',
            r'(?P<command>[MmZzLlHhVvCcSsQqTtAa])',
            r'(?P<error>.)',  # must be last
        ])
    )

    @classmethod
    def tokenize(cls, path):
        for m in cls.TOKEN_RX.finditer(path):
            kind = m.lastgroup
            value = m.group()
            if kind == 'wsp':
                continue
            if kind == 'error':
                pos = m.start()
                raise Error(f'Bad SVG path at position {pos}: {value}')
            yield (kind, value)

    @classmethod
    def parse(cls, path):
        command = []
        for kind, value in cls.tokenize(path):
            if kind == 'command':
                if command:
                    yield tuple(command)
                command = [value]
            elif kind == 'number':
                command.append(float(value))
            elif kind == 'comma':
                # let's just skip these
                continue
            else:  # pragma: nocover
                assert False, f'did not expect {kind}'
        if command:
            yield tuple(command)


class Canvas:

    def __init__(self, width, height, pixels=None):
        assert width > 0
        assert height > 0
        self.width = width
        self.height = height
        if pixels is None:
            self.pixels = [[0] * width for _ in range(height)]
        else:
            assert len(pixels) == height
            assert len(pixels[0]) == width
            self.pixels = pixels

    def horizontal_line(self, x, y, width):
        assert width > 0
        # PyQRCode draws 1-pixel thick horizontal lines, which means the
        # x coordinates are whole numbers, and the y coordinate is shifted by
        # 0.5 to point to the middle of the pixel
        y = int(y - 0.5)
        if 0 <= y < self.height:
            for x in range(int(x), int(x + width)):
                if 0 <= x < self.width:
                    self.pixels[y][x] = 1

    def to_bytes(self, values=(b'\xFF', b'\0'), xscale=1, yscale=1):
        return b''.join(
            b''.join(values[px] * xscale for px in row) * yscale
            for row in self.pixels
        )

    def to_ascii_art(self, chars=FULL_CHARS, xscale=1):
        return '\n'.join(
            ''.join(chars[px] * xscale for px in row) for row in self.pixels)

    def to_unicode_blocks(self, chars=HALF_CHARS):
        pixels = self.pixels
        if self.height % 2 == 1:
            pixels = pixels + [[0] * self.width]
        return '\n'.join(
            ''.join(chars[pixels[y+1][x] * 2 + pixels[y][x]]
                    for x in range(self.width))
            for y in range(0, self.height + 1, 2))

    def __str__(self):
        return self.to_ascii_art('.X')

    def line_is_blank(self, y):
        assert 0 <= y < self.height
        return not any(self.pixels[y])

    def column_is_blank(self, x):
        assert 0 <= x < self.width
        return not any(self.pixels[y][x] for y in range(self.height))

    def trim(self):
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

    def pad(self, top, right, bottom, left):
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

    def invert(self):
        return self.__class__(self.width, self.height, [
            [1 - px for px in row] for row in self.pixels
        ])


class Path:

    def __init__(self, canvas):
        # Technically the very first path drawing command must be an absolute
        # move_to, so the initial coordinates are undefined.
        self.x = 0
        self.y = 0
        self.canvas = canvas

    def move_to(self, x, y):
        self.x = x
        self.y = y

    def move_by(self, dx, dy):
        self.x += dx
        self.y += dy

    def horizontal_line_rel(self, dx):
        if dx > 0:
            self.canvas.horizontal_line(self.x, self.y, dx)
        elif dx < 0:
            self.canvas.horizontal_line(self.x + dx, self.y, -dx)
        self.x += dx

    def draw(self, commands):
        for cmd in commands:
            if cmd[0] == 'M' and len(cmd) == 3:
                self.move_to(cmd[1], cmd[2])
            elif cmd[0] == 'm' and len(cmd) == 3:
                self.move_by(cmd[1], cmd[2])
            elif cmd[0] == 'h' and len(cmd) == 2:
                self.horizontal_line_rel(cmd[1])
            else:
                raise Error(f'Did not expect drawing command {cmd[0]}'
                            f' with {len(cmd)-2} parameters')


class QR:

    def __init__(self, size):
        self.size = size
        self.canvas = Canvas(size, size)

    def to_ascii_art(self, chars=HALF_CHARS, big=False, trim=False, pad=0,
                     invert=False):
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
    def from_svg(cls, fileobj):
        tree = xml.etree.ElementTree.parse(fileobj)
        root = tree.getroot()
        if root.tag != f"{SVG_NS}svg":
            raise Error(f"This is not an SVG image ({root.tag})")
        if root.get('class') != 'pyqrcode':
            raise Error("The image was not generated by PyQRCode")
        width = int(root.get('width'))
        height = int(root.get('height'))
        if width != height:
            raise Error(f"The image is not square ({width}x{height})")
        path = root.find(f"{SVG_NS}path[@class='pyqrline']")
        if path is None:
            raise Error("Did not find the QR code in the image")
        # path.get('transform') should be something like "scale(8)"
        # path.get('stroke') should be '#000'
        # path.get('d') is the QR code itself, encoded as drawing commands
        transform = path.get('transform')
        if transform:
            m = TRANSFORM_SCALE_RX.match(transform)
            scale = int(m.group(1))
        else:
            scale = 1
        size = width // scale
        qr = cls(size)
        d = path.get('d')
        Path(qr.canvas).draw(PathParser.parse(d))
        return qr

    def decode(self):
        from pyzbar.pyzbar import ZBarSymbol, decode

        # Note: experiments with pyqrcode and zbarimg show that I need
        # pyqrcode.create('text').svg('file.svg', background='#fff', scale=2)
        # to have recognizable qr codes.  no background or scale=1 make zbarimg
        # fail to find any codes.
        scale = 2
        return decode((self.canvas.to_bytes(xscale=scale, yscale=scale),
                       self.size * scale, self.size * scale),
                      symbols=[ZBarSymbol.QRCODE])


def main():
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
    parser.add_argument("--no-decode", action="store_false",
                        dest="decode", default=True,
                        help="don't decode the QR codes")
    parser.add_argument("filename", type=argparse.FileType('r'), nargs='+',
                        help='SVG file with the QR code (use - for stdin)')
    args = parser.parse_args()

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
                for symbol in qr.decode():
                    print(symbol.data.decode(errors='replace'))
            sys.stdout.flush()
    except (Error, KeyboardInterrupt) as e:
        sys.exit(e)
    else:
        sys.exit(rc)


if __name__ == "__main__":
    main()
