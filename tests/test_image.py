from PIL import Image

from labelprint.imageutil import encode_rows, mm_to_px, pack_row, prepare_bitmap, split_ink_counts


def test_mm_to_px_50x30_at_203() -> None:
    assert mm_to_px(50, 203) == 400
    assert mm_to_px(30, 203) == 240


def test_pack_row_msb_is_left() -> None:
    img = Image.new("L", (8, 1), 255)
    img.putpixel((0, 0), 0)
    assert pack_row(img, 0) == b"\x80"


def test_pack_row_all_ink() -> None:
    img = Image.new("L", (8, 1), 0)
    assert pack_row(img, 0) == b"\xff"


def test_prepare_fits_inside_max_width() -> None:
    src = Image.new("L", (800, 100), 0)
    out = prepare_bitmap(src, max_width_px=384, width_px=384, height_px=240)
    assert out.size == (384, 240)


def test_encode_rows_collapses_blanks() -> None:
    img = Image.new("L", (8, 5), 255)
    runs = encode_rows(img)
    assert runs == [(0, 5, b"\x00")]


def test_split_ink_counts_three_buckets() -> None:
    line = bytes([0xFF] * 48)
    c0, c1, c2 = split_ink_counts(line, 384)
    assert c0 + c1 + c2 == 48 * 8
