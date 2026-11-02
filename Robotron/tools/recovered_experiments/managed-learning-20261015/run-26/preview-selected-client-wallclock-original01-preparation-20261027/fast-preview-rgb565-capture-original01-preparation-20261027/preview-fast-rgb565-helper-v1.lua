-- Preview bytes only: group native snapshot pixels to avoid per-pixel Lua/C
-- string allocations. RGB565 layout and the resize fallback remain exact.
local PREVIEW_NATIVE_UNPACK16 = "=" .. string.rep("I4", 16)
local PREVIEW_RGB565_PACK16 = ">" .. string.rep("I2", 16)
local function preview_pack_native16(p1, p2, p3, p4, p5, p6, p7, p8, p9, p10, p11, p12, p13, p14, p15, p16)
    return string.pack(PREVIEW_RGB565_PACK16,
        (((p1 >> 19) & 0x1F) << 11) | (((p1 >> 10) & 0x3F) << 5) | ((p1 >> 3) & 0x1F),
        (((p2 >> 19) & 0x1F) << 11) | (((p2 >> 10) & 0x3F) << 5) | ((p2 >> 3) & 0x1F),
        (((p3 >> 19) & 0x1F) << 11) | (((p3 >> 10) & 0x3F) << 5) | ((p3 >> 3) & 0x1F),
        (((p4 >> 19) & 0x1F) << 11) | (((p4 >> 10) & 0x3F) << 5) | ((p4 >> 3) & 0x1F),
        (((p5 >> 19) & 0x1F) << 11) | (((p5 >> 10) & 0x3F) << 5) | ((p5 >> 3) & 0x1F),
        (((p6 >> 19) & 0x1F) << 11) | (((p6 >> 10) & 0x3F) << 5) | ((p6 >> 3) & 0x1F),
        (((p7 >> 19) & 0x1F) << 11) | (((p7 >> 10) & 0x3F) << 5) | ((p7 >> 3) & 0x1F),
        (((p8 >> 19) & 0x1F) << 11) | (((p8 >> 10) & 0x3F) << 5) | ((p8 >> 3) & 0x1F),
        (((p9 >> 19) & 0x1F) << 11) | (((p9 >> 10) & 0x3F) << 5) | ((p9 >> 3) & 0x1F),
        (((p10 >> 19) & 0x1F) << 11) | (((p10 >> 10) & 0x3F) << 5) | ((p10 >> 3) & 0x1F),
        (((p11 >> 19) & 0x1F) << 11) | (((p11 >> 10) & 0x3F) << 5) | ((p11 >> 3) & 0x1F),
        (((p12 >> 19) & 0x1F) << 11) | (((p12 >> 10) & 0x3F) << 5) | ((p12 >> 3) & 0x1F),
        (((p13 >> 19) & 0x1F) << 11) | (((p13 >> 10) & 0x3F) << 5) | ((p13 >> 3) & 0x1F),
        (((p14 >> 19) & 0x1F) << 11) | (((p14 >> 10) & 0x3F) << 5) | ((p14 >> 3) & 0x1F),
        (((p15 >> 19) & 0x1F) << 11) | (((p15 >> 10) & 0x3F) << 5) | ((p15 >> 3) & 0x1F),
        (((p16 >> 19) & 0x1F) << 11) | (((p16 >> 10) & 0x3F) << 5) | ((p16 >> 3) & 0x1F))
end

local function preview_rgb565_bytes(src, vw, vh, tw, th)
    if tw == vw and th == vh then
        local out = {}
        local n = tw * th
        local grouped = n - (n % 16)
        local oi = 1
        for pixel = 0, grouped - 1, 16 do
            out[oi] = preview_pack_native16(string.unpack(PREVIEW_NATIVE_UNPACK16, src, pixel * 4 + 1))
            oi = oi + 1
        end
        for pixel = grouped, n - 1 do
            local px = string.unpack("=I4", src, pixel * 4 + 1)
            local rgb565 = (((px >> 19) & 0x1F) << 11) | (((px >> 10) & 0x3F) << 5) | ((px >> 3) & 0x1F)
            out[oi] = string.pack(">I2", rgb565)
            oi = oi + 1
        end
        return table.concat(out)
    end
        local out = {}
        local oi = 1
        for ty = 0, th - 1 do
            local sy = math.floor(((ty + 0.5) * vh) / th)
            if sy >= vh then sy = vh - 1 end
            local row_base = sy * vw
            for tx = 0, tw - 1 do
                local sx = math.floor(((tx + 0.5) * vw) / tw)
                if sx >= vw then sx = vw - 1 end
                local px_off = ((row_base + sx) * 4) + 1
                local px = string.unpack("=I4", src, px_off)
                local r = (px >> 16) & 0xFF
                local g = (px >> 8) & 0xFF
                local b = px & 0xFF
                local rgb565 = ((r >> 3) << 11) | ((g >> 2) << 5) | (b >> 3)
                out[oi] = string.pack(">I2", rgb565)
                oi = oi + 1
            end
        end

        return table.concat(out)
end

