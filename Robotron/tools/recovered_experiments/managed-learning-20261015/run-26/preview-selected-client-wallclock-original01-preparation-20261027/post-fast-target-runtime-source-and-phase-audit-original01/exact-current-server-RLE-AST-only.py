def exact_current_RLE_decode(pixels, expected_px):
    out = bytearray(expected_px)
    oi = si = 0
    plen = len(pixels)
    ok = True
    while si < plen and oi < expected_px:
        ctrl = pixels[si]
        si += 1
        words = (ctrl & 127) + 1
        if ctrl & 128 != 0:
            if si + 1 >= plen:
                ok = False
                break
            b0, b1 = (pixels[si], pixels[si + 1])
            si += 2
            need = words * 2
            if oi + need > expected_px:
                ok = False
                break
            for _ in range(words):
                out[oi] = b0
                out[oi + 1] = b1
                oi += 2
        else:
            need = words * 2
            if si + need > plen or oi + need > expected_px:
                ok = False
                break
            out[oi:oi + need] = pixels[si:si + need]
            oi += need
            si += need
    if not ok or oi != expected_px or si != plen:
        return None
    preview_pixels = bytes(out)
    preview_format = 1
    return preview_pixels
