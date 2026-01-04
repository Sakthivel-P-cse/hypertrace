from examples.patch_validator import PatchValidator, ValidationResult


def test_imports_added_and_pass():
    original = 'def foo():\n    return 1\n'
    patched = 'import json\n\ndef foo():\n    return 1\n'
    validator = PatchValidator({'validation_level': 'normal'})
    is_valid, issues = validator.validate_patch(original, patched, 'example.py', 'python')
    assert is_valid
    assert any(i.check == 'imports_added' for i in issues)


def test_dangerous_pattern_strict_fails():
    dangerous = "import os\n\ndef run(cmd):\n    os.system(cmd)\n    eval(cmd)\n"
    validator = PatchValidator({'validation_level': 'strict'})
    is_valid, issues = validator.validate_patch('', dangerous, 'danger.py', 'python')
    assert not is_valid
    assert any(i.check == 'dangerous_pattern' and i.level == ValidationResult.FAIL for i in issues)
