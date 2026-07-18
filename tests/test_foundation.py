def test_imports():
    import fastapi
    import google.genai
    import pydantic

    assert fastapi is not None
    assert google.genai is not None
    assert pydantic is not None
