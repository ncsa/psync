import pytest
import pstestdir

@pytest.fixture
def testdir():
    pstestdir.reset()
    return pstestdir
