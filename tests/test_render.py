from labelprint.render import render_label


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
