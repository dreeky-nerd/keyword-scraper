def test_package_importable():
    import trendfinder

    assert trendfinder.__version__ == "0.1.0"
