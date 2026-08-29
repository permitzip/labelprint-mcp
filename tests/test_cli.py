from labelprint.cli import main


def test_print_refuses_without_yes() -> None:
    assert main(["print", "--image", "missing.png"]) == 2


def test_render_requires_content() -> None:
    assert main(["render"]) == 2


def test_help() -> None:
    try:
        main(["--help"])
    except SystemExit as exc:
        assert exc.code == 0
        return
    raise AssertionError("expected SystemExit")
