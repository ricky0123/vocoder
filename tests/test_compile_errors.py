import pytest

from tests.fixtures.compile_error_programs import CompileErrorProgram


@pytest.mark.timeout(0.1)
def test_compile_errors(compile_error_program: CompileErrorProgram):
    p = compile_error_program
    with p.context():
        p.build()
