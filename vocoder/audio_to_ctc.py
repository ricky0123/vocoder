import asyncio as aio
import typing as t
from collections import deque
from contextlib import asynccontextmanager

import numpy as np
import sounddevice as sd
import torch
import torch.nn as nn
import webrtcvad

from vocoder.utils import panic


@asynccontextmanager
async def ctc_serve(model: nn.Module, stop: aio.Event):

    stream, audio_queue = get_audio_stream()
    voice_active_queue = aio.Queue[np.ndarray]()
    ctc_queue = aio.Queue[np.ndarray]()
    vad_task = aio.create_task(
        produce_vad(audio_queue, voice_active_queue, stop), name="vad"
    )
    model_task = aio.create_task(
        produce_ctc(voice_active_queue, stop, ctc_queue, model), name="model"
    )

    stream.start()
    try:
        yield ctc_queue
    finally:
        stream.stop()
        stream.close()
        try:
            await aio.wait_for(vad_task, 0.1)
            await aio.wait_for(model_task, 0.1)
        except aio.TimeoutError:
            panic("audio tasks did not end in time")


def get_audio_stream():
    audio_queue = aio.Queue[np.ndarray]()

    block_duration = 30  # milliseconds
    sample_rate = 16000
    blocksize = int(sample_rate / 1000 * block_duration)

    loop = aio.get_event_loop()

    def callback(indata, frame_count, time_info, status):
        loop.call_soon_threadsafe(audio_queue.put_nowait, indata.copy())

    stream = sd.InputStream(
        samplerate=sample_rate,
        blocksize=blocksize,  # This is supposed to be 30 milliseconds?
        channels=1,
        dtype=np.int16,
        callback=callback,
    )
    return stream, audio_queue


async def produce_vad(
    audio_queue: aio.Queue[np.ndarray],
    vad_queue: aio.Queue[np.ndarray],
    exit_event: aio.Event,
):
    front_padding = 5
    n_vad_decisions = 15
    on_threshold_fraction = 0.7
    off_threshold_fraction = 0.1

    vad = webrtcvad.Vad(3)

    decisions = deque[int](  # last n decisions returned by webrtcvad
        [0] * n_vad_decisions, maxlen=n_vad_decisions
    )
    current_vote = 0  # moving sum of vad decisions == sum(decisions)

    on_threshold = round(on_threshold_fraction * n_vad_decisions)
    off_threshold = round(off_threshold_fraction * n_vad_decisions)

    tentative_buffer = deque[np.ndarray](maxlen=front_padding + n_vad_decisions)
    indata_buffer = deque[np.ndarray]()

    is_active = False

    while not exit_event.is_set():
        try:
            audio = await aio.wait_for(audio_queue.get(), 0.001)
        except aio.TimeoutError:
            continue

        current_vote, is_active = run_frame(
            audio,
            vad_queue,
            vad,
            decisions,
            current_vote,
            tentative_buffer,
            is_active,
            indata_buffer,
            off_threshold,
            on_threshold,
        )


def run_frame(
    indata: np.ndarray,
    voice_active_queue: aio.Queue[np.ndarray],
    vad: webrtcvad.Vad,
    decisions: deque[int],
    current_vote: int,
    tentative_buffer: deque[np.ndarray],
    is_active: bool,
    indata_buffer: deque[np.ndarray],
    off_threshold: float,
    on_threshold: float,
):
    is_speech = int(vad.is_speech(indata.tobytes(), 16000))
    current_vote = -decisions.popleft() + current_vote + is_speech
    decisions.append(is_speech)
    tentative_buffer.append(indata)

    if is_active:
        indata_buffer.append(indata)

        if current_vote <= off_threshold:
            is_active = False
            queue_item = np.concatenate(indata_buffer)
            voice_active_queue.put_nowait(queue_item)
            indata_buffer.clear()

    elif not is_active and current_vote >= on_threshold:
        is_active = True
        indata_buffer.extend(tentative_buffer)

    return current_vote, is_active


async def produce_ctc(
    vad_queue: aio.Queue[np.ndarray],
    exit_event: aio.Event,
    ctc_queue: aio.Queue[np.ndarray],
    model: t.Callable,
):
    while not exit_event.is_set():
        try:
            audio_ = await aio.wait_for(vad_queue.get(), 0.001)
        except aio.TimeoutError:
            continue

        audio = audio_ndarray_to_tensor(format_vad_to_model(audio_))
        ctc = model(audio)
        ctc_queue.put_nowait(ctc)


def audio_ndarray_to_tensor(x: np.ndarray, cuda: bool = False) -> torch.Tensor:
    return torch.tensor(  # pylint: disable=not-t.callable
        x,
        dtype=torch.float32,
        requires_grad=False,
        device="cuda" if cuda else None,
    )


def format_vad_to_model(x: np.ndarray) -> np.ndarray:
    return x.transpose() / 32768
