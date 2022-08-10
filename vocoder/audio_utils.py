import asyncio as aio

import numpy as np
import torch

from vocoder.audio_to_ctc import format_vad_to_model, get_audio_stream
from vocoder.utils import queue_to_list


async def record_duration(seconds: float = 60):
    "Set model_format to false if you want to run vad on audio"
    stream, audio_queue = get_audio_stream()
    stream.start()
    try:
        await aio.sleep(seconds)
    except:
        pass
    stream.stop()
    stream.close()
    audio_ = np.concatenate(queue_to_list(audio_queue))
    return format_vad_to_model(audio_)


async def record_duration_raw(seconds: float = 60):
    "Set model_format to false if you want to run vad on audio"
    stream, audio_queue = get_audio_stream()
    stream.start()
    try:
        await aio.sleep(seconds)
    except:
        pass
    stream.stop()
    stream.close()
    return queue_to_list(audio_queue)


def format_audio_for_vad(audio: torch.Tensor):
    if not isinstance(audio, np.ndarray):
        audio = audio.numpy()
    audio_ = (audio.flatten() * 32768).astype(np.int16)
    (L,) = audio_.shape
    q, r = divmod(L, 480)
    segments = list[np.ndarray]()
    for i in range(q):
        segments.append(audio_[480 * i : 480 * i + 480][:, None])
    segments.append(
        np.concatenate([audio_[q * 480 :], np.zeros(480 - r, np.int16)])[:, None]
    )
    return segments
