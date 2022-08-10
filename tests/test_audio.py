import numpy as np
import pytest

from vocoder.audio_utils import record_duration


@pytest.mark.asyncio
async def test_record_duration():
    audio_ = await record_duration(0.05)
    assert audio_.shape[0] == 1
    assert audio_.shape[1] > 1
    assert audio_.dtype == np.float64
