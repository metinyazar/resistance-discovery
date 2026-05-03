from src.llm import strip_code_fences


def test_strip_code_fences_handles_json_block():
    text = """```json
{"gene_symbol":"EGFR"}
```"""
    assert strip_code_fences(text) == '{"gene_symbol":"EGFR"}'
