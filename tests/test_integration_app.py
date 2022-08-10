import asyncio as aio

import numpy as np
import pytest
from pytest_mock import MockerFixture

from tests.fixtures.programs import Program
from vocoder.acoustic_models.wav2vec2 import token_encoding
from vocoder.app import App
from vocoder.simulate_ctc import simulate_ctc


@pytest.fixture
def no_model(mocker: MockerFixture):
    mocker.patch(
        "vocoder.app.load_model",
        return_value=None,
    )


@pytest.mark.timeout(0.2)
@pytest.mark.asyncio
async def test_run_audio(program: Program, mocker: MockerFixture, no_model):

    ctc_queue = aio.Queue[np.ndarray]()

    mocker.patch(
        "vocoder.app.ctc_serve"
    ).return_value.__aenter__.return_value = ctc_queue

    app = App(program.grammar)
    app_task = aio.create_task(app.run_async())

    for line in program.input:
        ctc_ = simulate_ctc(line, token_encoding)
        ctc_queue.put_nowait(ctc_)

    while not ctc_queue.empty():
        await aio.sleep(0.001)

    app.exit()
    await app_task
    program.test()


@pytest.mark.timeout(0.2)
@pytest.mark.asyncio
async def test_run_app_text(program: Program, mocker: MockerFixture, no_model):

    utterance_queue = aio.Queue[str]()
    for line in program.input:
        utterance_queue.put_nowait(line)

    async def _text_prompt(exit_event: aio.Event):
        while not utterance_queue.empty():
            yield utterance_queue.get_nowait()

    mocker.patch("vocoder.app._text_prompt", _text_prompt)

    app = App(program.grammar)
    app_task = aio.create_task(app.run_async(text=True))

    while not utterance_queue.empty():
        await aio.sleep(0.001)

    app.exit()
    await app_task
    program.test()
