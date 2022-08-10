import asyncio as aio
import signal
from dataclasses import dataclass, field

from aioconsole import ainput
from loguru import logger

from vocoder import exceptions
from vocoder.acoustic_models.wav2vec2 import load_model, token_encoding
from vocoder.audio_to_ctc import ctc_serve
from vocoder.compile_grammar import compile_grammar
from vocoder.grammar import Grammar
from vocoder.namespace import Namespace
from vocoder.soft_beam_search import beam_search
from vocoder.soft_simulate import Executor, initial_path_leaves, simplify, text_simulate
from vocoder.utils import panic, vocoder_listening_message, vocoder_welcome_message


@dataclass
class App:
    grammar: Grammar
    quiet: bool = False

    exit_event: aio.Event = field(default_factory=aio.Event, init=False)

    def __post_init__(self):
        if self.quiet:
            logger.disable("vocoder")

        vocoder_welcome_message()

    def exit(self):
        logger.info("Exiting...")
        self.exit_event.set()

    def run(self, text=False):
        return aio.run(self.run_async(text))

    async def run_async(self, text: bool = False):
        try:
            self.lexicons = self.grammar.lexicon_registry
            self.automaton = compile_grammar(
                self.grammar.config,
                self.grammar.lexicon_registry,
                self.grammar.attribute_registry,
            )

            env = Namespace(app=self)
            self.executor = Executor(self.lexicons, env)

            if not text:
                self.model = load_model()
            self.token_encoding = token_encoding

            self.automaton_state = initial_path_leaves(self.automaton)
            self.automaton_state, output = simplify(self.automaton_state)
            self.executor.eat([], output)

        except KeyboardInterrupt:
            return

        def sigint_handler(signal, frame):
            self.exit()

        signal.signal(signal.SIGINT, sigint_handler)

        _main_loop = self.main_loop_asr if not text else self.main_loop_repl
        main_loop_task = aio.create_task(_main_loop())
        await self.exit_event.wait()

        try:
            await aio.wait_for(main_loop_task, 3)
        except aio.TimeoutError:
            panic("main loop did not end on time")

    async def main_loop_asr(self):

        async with ctc_serve(self.model, self.exit_event) as ctc_queue:

            vocoder_listening_message()

            while not self.exit_event.is_set():

                try:
                    ctc = await aio.wait_for(ctc_queue.get(), 0.001)
                except aio.TimeoutError:
                    continue

                logger.info("Detected voice activity.")
                new_words, prob, leaves = beam_search(
                    self.automaton,
                    self.lexicons,
                    self.automaton_state,
                    ctc,
                    self.token_encoding,
                    8,
                    8,
                )

                if not new_words:
                    logger.info("Did not detect speech.")
                    continue

                logger.info("Detected speech: " + " ".join(new_words) + ".")

                self.automaton_state, output = simplify(leaves)
                self.executor.eat(new_words, output)

    async def main_loop_repl(self):

        async for utterance in _text_prompt(self.exit_event):
            if self.exit_event.is_set():
                break

            try:
                words, path_leaves = text_simulate(
                    self.automaton,
                    self.automaton_state,
                    self.lexicons,
                    utterance,
                )
            except exceptions.InvalidWordTransition:
                logger.error("invalid word transition")
                continue

            self.automaton_state, output = simplify(path_leaves)
            self.executor.eat(words, output)


async def _text_prompt(exit_event: aio.Event):
    while True:
        input_task = aio.create_task(ainput(">>> "))
        while not input_task.done() and not exit_event.is_set():
            await aio.sleep(0.005)
        if exit_event.is_set():
            return
        yield input_task.result()
