""""""

import struct
from functools import wraps

from lzw import encoder, decoder


def extension(mth):
    @wraps(mth)
    def wrapped_ext(*args, **kwargs):
        try:
            return mth(*args, **kwargs)
        except KeyError:
            return {}

    return wrapped_ext


class Gif:
    """Broken down representation of an 89a gif, iterating generates frames.

    Same data structure returned by getters may be used to set the same values.
    Getters and setters are specific to the current frame when appropriate.
    """
    # Global getters/setters
    HEAD = 'Header Block'
    LSD = 'Logical Screen Descriptor'
    GCT = 'Global Color Table'
    TRAIL = 'Trailer'
    # Frame specific getters/setters
    GCE = 'Graphics Control Extension'
    ID = 'Image Descriptor'
    IMG = 'Image Data Block'
    LCT = 'Local Color Table'
    PTE = 'Plain Text Extension'
    AE = 'Application Extension'
    CE = 'Comment Extension'

    block_properties = {}
    for name in {**locals()}:
        if name.isupper():
            block_properties |= {locals()[name]: name.lower()}
        block_properties |= {HEAD: 'header', TRAIL: 'trailer'}

    def __init__(self, gif_data):
        if isinstance(gif_data, bytes):
            raw = gif_data
        else:
            raw = b''.join([*gif_data])
        self.data = self.deconstructor(raw)

        self.__frames = 0
        self._frame = 0

    def __getitem__(self, key):
        """Accessing data from sub-levels is possible with subscription"""
        return self._search(key)[1]

    def __setitem__(self, key, value):
        """Setting data from sub-levels is possible with subscription"""
        loc, _ = self._search(key)
        if loc in (self, self.data, self.data[self.frame]):
            if key in self.block_properties:
                setattr(self, self.block_properties[key], 0)
            else:
                raise AttributeError('Attribute found but cannot be changed via subscription')
        else:
            data = loc
            data[key] = value

    def _search(self, key):
        """Search for desired item"""
        for loc in (
                self.data, self.data[self.frame], self.header, self.lsd,
                self.gce, self.id, self.ae, self.ce,
        ):
            if (value := loc.get(key, None)) is not None:
                return loc, value
            if (value := loc.get(key.title(), None)) is not None:
                return loc, value
        return self, getattr(self, key, None)

    @property
    def header(self):
        """No setter"""
        data = asc(self.data[self.HEAD])
        return {'Signature': data[:3], 'Version': data[-3:]}

    @property
    def lsd(self):
        raw = self.data[self.LSD]
        data, packed = hexd(raw, packed=4)
        return {
            'Canvas Width': H< raw[:2],
            'Canvas Height': H< raw[2:4],
            'Packed Field': {
                'Global Color Flag': packed[0],
                'Color Resolution': packed[1:4],
                'Sort Flag': packed[4],
                'Size of Global Color Table': packed[5:]
            },
            'Background Color Index': data[5],
            'Pixel Aspect Ratio': data[6]
        }

    @lsd.setter
    def lsd(self, unpacked):
        self.data[self.LSD] = pack(unpacked)

    @property
    def gct(self):
        return unpack_table(self.data[self.GCT])

    @gct.setter
    def gct(self, unpacked):
        self.data[self.GCT] = pack_table(unpacked)

    @property
    def trailer(self):
        return hex(self.data[self.TRAIL][0])

    # --- For dealing with frames rather than base attributes

    def __iter__(self):
        return self

    def __next__(self):
        try:
            self.frame = self._frame + 1
        except IndexError:
            raise StopIteration
        return self.data[self._frame]

    @property
    def frames(self):
        return len([value for key, value in self.data.items() if isinstance(key, int)])

    @property
    def frame(self):
        return self._frame

    @frame.setter
    def frame(self, n):
        if n >= self.frames:
            raise IndexError("Frame index out of range.")
        else:
            self._frame = n

    @property
    def gce(self):
        raw = self.data[self.frame][self.GCE]
        data, pack = hexd(raw, packed=3)
        return {
            'Extension Introducer': data[0],
            'Graphic Control Label': data[1],
            'Byte Size': data[2],
            'Packed Field': {
                'Reserved for Future Use': pack[:3],
                'Disposal Method': pack[3:6],
                'User Input Flag': pack[6],
                'Transparent Color Flag': pack[7]
            },
            'Delay Time': H< raw[4:6],
            'Transparent Color Index': data[6],
            'Block Terminator': data[7]
        }

    @gce.setter
    def gce(self, unpacked):
        self.data[self.frame][self.GCE] = pack(unpacked)

    @property
    def id(self):
        raw = self.data[self.frame][self.ID]
        data, pack = hexd(raw, packed=9)
        return {
            'Image Seperator': data[0],
            'Image Left': H< raw[1:3],
            'Image Top': H< raw[3:5],
            'Image Width': H< raw[5:7],
            'Image Height': H< raw[7:9],
            'Packed Field': {
                'Local Color Table': pack[0],
                'Interlace Flag': pack[1],
                'Sort Flag': pack[2],
                'Reserved For Future Use': pack[3:5],
                'Size of Local Color Table': pack[5:]
            }

        }

    @id.setter
    def id(self, unpacked):
        self.data[self.frame][self.ID] = pack(unpacked)

    @property
    def lct(self):
        return unpack_table(self.data[self.frame][self.LCT])

    @lct.setter
    def lct(self, unpacked):
        self.data[self.frame][self.LCT] = pack_table(unpacked)

    @property
    def img(self):
        """Decompresses frame's img data"""
        return decoder(self.data[self.frame][self.IMG])

    @img.setter
    def img(self, img_data):
        """Compresses new img data"""
        self.data[self.frame][self.IMG] = bytes(encoder(img_data, self.data[self.frame][self.LCT] or self.data[self.GCT]))

    @property
    @extension
    def pte(self):
        """Pending decompressor for text, add to _search when added"""
        intro, label, length, *rest = self.data[self.frame][self.PTE]
        block, *text = rest[length:], rest[:length]
        return self.data[self.frame][self.PTE]

    @pte.setter
    def pte(self, text):
        self.data[self.frame][self.PTE] = text

    @property
    @extension
    def ae(self):
        raw = self.data[self.frame][self.AE]
        data = hexd(raw)
        return {
            'Extension Introducer': data[0],
            'Application Extension Label': data[1],
            'Application Block Length': data[2],
            'Application Identifier': asc(raw[3:11]),
            'Application Auth Code': asc(raw[11:14]),
            'Length of Sub Block': data[14],
            'Random one': data[15],
            'Loop': H< raw[16:18],
            'Sub Block Terminator': data[18]
        }

    @ae.setter
    def ae(self, unpacked):
        packed = pack(unpacked)
        self.data[self.frame][self.AE] = packed

    @property
    @extension
    def ce(self):
        raw = self.data[self.frame][self.CE]
        data = hexd(raw)
        return {
            'Extension Introducer': data[0],
            'Comment Label': data[1],
            'Comment Size': data[2],
            'Comment': asc(raw[3:-1]),
            'Sub Block Terminator': data[-1]
        }

    @ce.setter
    def ce(self, unpacked):
        self.data[self.frame][self.CE] = pack(unpacked)

    # --- For converting gif data into and out of pure bytes

    @staticmethod
    def deconstructor(data: bytes):
        """Break a gif's bytes down into a dict with int-keyed frame dicts"""
        data, header = data[6:], data[:6]
        lsd, data = data[:7], data[7:]
        gct_size = 3 * 2 ** (1 + (lsd[-3] & 0b00000111))
        gct, data = data[:gct_size], data[gct_size:]
        deconstructed = {
            Gif.HEAD: header,
            Gif.LSD: lsd,
            Gif.GCT: gct
        }

        def get_ext():
            nonlocal data
            extensions = {}
            ei, el, *_ = data
            # extensions = {ext: b'' for ext in {Gif.GCE, Gif.AE, Gif.PTE, Gif.CE}}
            while ei == 0x21:
                if el == 0xF9:
                    extensions[Gif.GCE], data = data[:8], data[8:]
                if el == 0xFF:
                    extensions[Gif.AE], data = data[:19], data[19:]
                if el == 0x01:
                    size = len(data[data[2] + 3:].split(b'\x00')[0]) + data[2] + 4
                    extensions[Gif.PTE], data = data[:size], data[size:]
                if el == 0xFE:
                    size = len(data.split(b'\x00')[0]) + 1
                    extensions[Gif.CE], data = data[:size], data[size:]
                ei, el, *_ = data
            return extensions

        for n in range(0xfffffff):
            try:
                extensions = get_ext()
                id, data = data[:10], data[10:]
                if id[-1] & 0b10000000:
                    size = 3 * 2 ** ((id[-1] & 0b00000111) + 1)
                    lct, data = data[:size], data[size:]
                else:
                    lct = b''
                size = data[1]
                total = 1  # skipping LZW
                while size != 0:
                    total += size + 1
                    size = data[total]
                total += 1  # for final null
                block, data = data[:total], data[total:]
                deconstructed |= {n: {**extensions, Gif.ID: id, Gif.LCT: lct, Gif.IMG: block}}
            except (ValueError, IndexError):
                break
        assert len(data) == 1, 'Trailer should always just be 3B'
        deconstructed |= {Gif.TRAIL: data}
        return deconstructed

    @staticmethod
    def reconstruct(deconstructed):
        frames = [frame for key, frame in deconstructed.items() if isinstance(key, int)]
        other = [frame for key, frame in deconstructed.items() if isinstance(key, str)]
        deconstructed_frames = [b''.join(value for key, value in x.items()) for x in frames]
        return b''.join([*other[:-1], *deconstructed_frames, other[-1]])

    @property
    def raw(self):
        return self.reconstruct(self.data)

    @raw.setter
    def raw(self, new_raw):
        self.__init__(new_raw)


def asc(byte):
    return str(byte)[2:-1]


def pad_hex(to_pad):
    return to_pad[:2] + (to_pad[2:].zfill(2))


def hexd(byte, packed=None):
    hexxed = [*map(hex, byte)]
    padded = [*map(pad_hex, hexxed)]
    if packed is not None:
        return padded, bin(eval(hexxed[packed]))[2:].zfill(8)
    return padded


def unpack_table(table):
    """Unpacks a color table"""
    hexxed = [x[2:] for x in hexd(table)]
    return [f'{"".join(x.zfill(2) for x in hexxed[i:i + 3])}' for i in range(0, len(hexxed), 3)]


def pack_table(unpacked):
    """Repacks a table"""
    return b''.fromhex(''.join(unpacked))


class _H:
    """Translate bytes from unsigned little endian short to int with <"""

    def __lt__(self, other):
        return struct.unpack('<H', other)[0]


H = _H()


def pack_short(short):
    packed = [pad_hex(hex(x)) for x in struct.pack('<H', short)]
    if len(packed) == 1:
        print('this happened')
        packed = ['0x00', *packed]
    return packed


def pack(unpacked):
    """Repacks an unpacked dict of values"""
    initial_convert = [
        pad_hex(hex(int(''.join(value.values()), 2))) if key == 'Packed Field'
        else pack_short(value) if isinstance(value, int)
        else [pad_hex(hex(ord(x))) for x in value] if (isinstance(value, str) and value[:2] != '0x')
        else value
        for key, value in unpacked.items()
    ]
    return b''.fromhex(
        ''.join(
            x.zfill(2) for x in ''.join(
                ''.join([*x]) for x in initial_convert
            )[2:].split('0x')
        )
    )


def test():
    """Test all getters and setters"""
    from copy import deepcopy
    with open('testy.gif', 'rb') as tester:
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
                    # assert str(e) == "'Plain Text Extension'"
                if x not in {'pte', 'header', 'trailer'}:
                    setattr(f, x, cur)
            if broken := [old[0] for old, new in zip(old_data.items(), f.data.items()) if old != new]:
                print(f'broken in frame {i}:', broken)
    with open('testing.gif', 'rb') as tester:
        tester = b''.join([*tester])
    f = Gif(tester)
    assert f.raw == tester
    with open('test.gif', 'rb') as tester:
        tester = b''.join([*tester])
    f.raw = tester
    assert f.raw == tester


if __name__ == '__main__':
    ...
