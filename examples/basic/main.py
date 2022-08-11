from vocoder.app import App
from vocoder.grammar import Grammar
from vocoder.lexicons import en_frequent, python_keywords
from pynput.keyboard import Controller, Key

keyboard = Controller()

def execute_chord(mods, term):
    with keyboard.pressed(*mods):
        keyboard.press(term)
        keyboard.release(term)

g = Grammar()

g(f"""
!start = < !sleep | !command | !exit >
!sleep = ~(vocoder sleep) <* :en > ~(vocoder wake)
!exit = ~(vocoder exit) => %{g(lambda env: env.app.exit())}

!command = !chord | !phrase [rest]

!phrase ~= phrase < :python+:en-:python_homophones > -> %type

!chord ~= <*:modifier> @mods :terminal @term => %{g(execute_chord)}

%type = %{g(lambda words: keyboard.type(" ".join(words)))}

:reserved = vocoder+rest
:en = :{g(en_frequent(30_000))}-:reserved
:python = :{g(python_keywords)}
:python_homophones = deaf+death

:modifier = :{g({
    "soup": Key.cmd,
    "troll": Key.ctrl,
    "shift": Key.shift,
    "alt": Key.alt,
})}
:terminal = :{g({
    "tick": "`",
    "tilde": "~",
    "bang": "!",
    "lat": "@",
    "hash": "#",
    "doll": "$",
    "mod": "%",
    "try": "^",
    "amp": "&",
    "star": "*",
    "lep": "(",
    "rep": ")",
    "mine": "-",
    "score": "_",
    "lane": "=",
    "plus": "+",
    "lace": "[",
    "race": "]",
    "lack": "{",
    "rack": "}",
    "pipe": "|",
    "wink": ";",
    "coal": ":",
    "chick": "'",
    "dub": '"',
    "lang": "<",
    "rang": ">",
    "com": ",",
    "pier": ".",
    "slash": "/",
    "quest": "?",
    "ack": "a",
    "bat": "b",
    "cap": "c",
    "drum": "d",
    "each": "e",
    "fine": "f",
    "gust": "g",
    "harp": "h",
    "sit": "i",
    "jury": "j",
    "crunch": "k",
    "look": "l",
    "made": "m",
    "near": "n",
    "odd": "o",
    "pit": "p",
    "quench": "q",
    "red": "r",
    "sun": "s",
    "trap": "t",
    "urge": "u",
    "vest": "v",
    "whale": "w",
    "plex": "x",
    "yank": "y",
    "zip": "z",
    "zero": "0",
    "one": "1",
    "two": "2",
    "three": "3",
    "four": "4",
    "five": "5",
    "six": "6",
    "seven": "7",
    "eight": "8",
    "nine": "9",
    "left": Key.left,
    "right": Key.right,
    "up": Key.up,
    "down": Key.down,
    "tab": Key.tab,
    "eggs": Key.esc,
    "slap": Key.enter,
    "spooce": Key.space,
    "home": Key.home,
    "pageup": Key.page_up,
    "pagedown": Key.page_down,
    "end": Key.end,
    "junk": Key.backspace,
    "del": Key.delete,
})}
""")


App(g).run()
