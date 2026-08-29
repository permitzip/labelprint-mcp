from labelprint.render import render_label


def _ink_x_runs(img) -> list[tuple[int, int]]:
    pix = img.load()
    assert pix is not None
    width, height = img.size
    xs = [x for x in range(width) if any(pix[x, y] < 128 for y in range(height))]
    assert xs
    runs: list[tuple[int, int]] = []
    start = prev = xs[0]
    for x in xs[1:]:
        if x != prev + 1:
            runs.append((start, prev))
            start = x
        prev = x
    runs.append((start, prev))
    return runs


def _ink_bbox_in(img, x0: int, x1: int) -> tuple[int, int, int, int]:
    pix = img.load()
    assert pix is not None
    width, height = img.size
    xs: list[int] = []
    ys: list[int] = []
    for y in range(height):
        for x in range(x0, min(x1, width)):
            if pix[x, y] < 128:
                xs.append(x)
                ys.append(y)
    assert xs
    return min(xs), min(ys), max(xs), max(ys)


def test_title_body_label_size() -> None:
    img = render_label(width_px=384, height_px=240, title="BOARDS", body="Is this a controller?")
    assert img.size == (384, 240)
    assert img.mode == "L"
    # Must have ink.
    assert img.getextrema()[0] < 128


def test_qr_layout_keeps_canvas(tmp_path) -> None:
    try:
        img = render_label(width_px=384, height_px=240, title="ITEM", qr="https://example.com/i/1")
    except Exception as exc:  # optional extra
        if "labelprint[qr]" in str(exc):
            return
        raise
    assert img.size == (384, 240)


def test_qr_plus_text_is_ink_centered() -> None:
    try:
        img = render_label(
            width_px=384,
            height_px=240,
            title=(
                "0.96 Inch OLED I2C IIC Display Module 12864 "
                "128x64 Pixel SSD1306 Mini Self-Luminous OLED Screen Board"
            ),
            body="MODULES / SENSORS / DISPLAYS",
            qr="http://localhost:3003/lab/i/fb2cfd55-b575-4b18-92e7-1daae4af5dd2",
        )
    except Exception as exc:
        if "labelprint[qr]" in str(exc):
            return
        raise
    runs = _ink_x_runs(img)
    assert len(runs) >= 2, runs
    qr_l, qr_r = runs[0]
    text = _ink_bbox_in(img, runs[1][0], img.size[0])
    qr_to_text = text[0] - qr_r
    text_to_right = img.size[0] - 1 - text[2]
    top_gap = text[1]
    bottom_gap = img.size[1] - 1 - text[3]
    group_left = qr_l
    group_right = text_to_right
    # Text sits next to the QR; leftover air belongs on the right, not a flush right edge.
    assert qr_to_text >= 6, (qr_to_text, runs, text)
    assert text_to_right >= qr_to_text, (qr_to_text, text_to_right, text)
    assert abs(top_gap - bottom_gap) <= 8, (top_gap, bottom_gap)
    # Whole QR+text group is left-biased so a right-sitting 384-dot head
    # looks centered on 50 mm tape.
    assert group_right - group_left >= 16, (group_left, group_right, text)
    # Short last line must not sit on the right (old per-line centering looked right-justified).
    pix = img.load()
    assert pix is not None
    last_xs = [
        x
        for y in range(text[3] - 14, text[3] + 1)
        for x in range(text[0], img.size[0])
        if pix[x, y] < 128
    ]
    assert last_xs
    last_left = min(last_xs)
    last_right = max(last_xs)
    assert last_left - text[0] <= 8, (last_left, text[0])
    assert (img.size[0] - 1 - last_right) > (last_left - qr_r), (last_left, last_right, qr_r)
