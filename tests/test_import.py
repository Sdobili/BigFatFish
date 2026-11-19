"""Package import smoke test for the repository skeleton."""


def test_import_bigfatfish_and_version() -> None:
    import bigfatfish

    assert bigfatfish.__version__ == "0.0.1"
