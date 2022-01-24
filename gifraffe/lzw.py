BYTE = 8
MAX_BITLEN = 12
MAX_TABLE_SIZE = 0xFFF
SUB_BLOCK_SIZE = 0xFF


def encoder(index_stream, color_table=()):
    """Yield encoded GIF-style LZW bytes from incoming indices."""
    return _block_encoder(index_stream, (len(color_table[:-1]) // 3).bit_length())


def _block_encoder(index_stream, lzw_min):
    """Yield sub-blocked bytes from incoming bytes."""
    lzw_min = lzw_min or max(index_stream := [*index_stream]).bit_length()
    index_iter = iter(index_stream)
    unblocked = _byte_encoder(index_iter, lzw_min)
    yield lzw_min
    byte_buffer = []
    for byte in unblocked:
        byte_buffer += [byte]
        if len(byte_buffer) == SUB_BLOCK_SIZE:
            yield SUB_BLOCK_SIZE
            for _ in range(SUB_BLOCK_SIZE):
                yield byte_buffer.pop(0)
    if byte_buffer:
        yield len(byte_buffer)
        for byte in byte_buffer:
            yield byte
    yield 0x00


def _byte_encoder(index_iter, lzw_min):
    """Yield bit-packed bytes from incoming LZW-encoded bytes."""
    bitlength = lzw_min + 1
    code_table = *_, (clear,), _ = {(i,): i for i in range(2 ** lzw_min + 2)}
    coded = _code_encoder(index_iter, code_table)
    bit_buffer = []
    for code in coded:
        bit_buffer += [code & 1 << b and 1 for b in range(bitlength)]
        while len(bit_buffer) > BYTE:
            yield sum(bit_buffer.pop(0) << b for b in range(BYTE))
        bitlength += bitlength < MAX_BITLEN and len(code_table) > 1 << bitlength
        if code == clear:
            bitlength = lzw_min + 1
    bit_buffer += [0] * (BYTE - len(bit_buffer) % BYTE)
    while bit_buffer:
        yield sum(bit_buffer.pop(0) << b for b in range(BYTE))


def _code_encoder(index_iter, code_table):
    """Yield GIF-style LZW-encoded bytes from incoming indices."""
    *_, (clear,), (eoi,) = code_table
    index_buffer = (next(index_iter),)
    yield clear
    for k in index_iter:
        if index_buffer + (k,) in code_table:
            index_buffer += (k,)
        else:
            code_table |= {index_buffer + (k,): len(code_table)}
            yield code_table[index_buffer]
            index_buffer = (k,)
            if len(code_table) == MAX_TABLE_SIZE:
                yield clear
                code_table.clear()
                code_table |= {(i,): i for i in range(eoi + 1)}
    yield code_table[index_buffer]
    yield eoi


def decoder(code_bytes):
    """Yield decoded indices from incoming GIF-style LZW-encoded bytes."""
    bytes_iter = iter(code_bytes)
    lzw_min = next(bytes_iter)
    get_code = _get_code_getter(bytes_iter)
    code = clear = get_code(lzw_min + 1)
    eoi = clear + 1
    while code != eoi:
        if code == clear:
            bitlength = lzw_min + 1
            code_table = [[i] for i in range(eoi + 1)]
            last, code = get_code(bitlength), get_code(bitlength)
            yield last
        if code < len(code_table):
            output = code_table[code]
            to_add = code_table[last] + [code_table[code][0]]
        else:
            to_add = output = code_table[last] + [code_table[last][0]]
        for i in output:
            yield i
        code_table += [to_add]
        bitlength += bitlength < MAX_BITLEN and len(code_table) == 1 << bitlength
        last, code = code, get_code(bitlength)


def _get_code_getter(code_iter):
    def bit_stream():
        """Yield least significant bit remaining in current byte."""
        length = next(code_iter)
        for read, byte in enumerate(code_iter):
            if read == length:
                length += byte + 1
            else:
                for bit in (1 << b & byte and 1 for b in range(BYTE)):
                    yield bit

    def code_getter(bitlength):
        """Retrieve/structure bits, least significant first."""
        return sum(next(code_stream) << z for z in range(bitlength))

    code_stream = bit_stream()
    return code_getter
