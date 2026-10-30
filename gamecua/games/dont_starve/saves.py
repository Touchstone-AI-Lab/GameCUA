"""Data-only decoding of native KLEI saves; Lua is never executed."""

import base64
import re
import zlib

TOKEN = re.compile(
    r'\s*(?:(?P<string>"(?:[^"\\]|\\.)*"|\'(?:[^\'\\]|\\.)*\')'
    r"|(?P<number>[+-]?(?:\d+\.?\d*|\.\d+)(?:[eE][+-]?\d+)?)"
    r"|(?P<name>[A-Za-z_][A-Za-z_0-9]*)|(?P<punct>[{}\[\]=,;]))",
    re.DOTALL,
)
ESCAPES = {"a": "\a", "b": "\b", "f": "\f", "n": "\n", "r": "\r", "t": "\t", "v": "\v"}
ESCAPE = re.compile(r"\\([0-9]{1,3}|.)", re.DOTALL)
LITERALS = {"true": True, "false": False, "nil": None}


def string(token):
    return ESCAPE.sub(
        lambda match: chr(int(match[1])) if match[1].isdigit() else ESCAPES.get(match[1], match[1]),
        token[1:-1],
    )


class LuaData:
    def __init__(self, text):
        self.tokens = [(match.lastgroup, match[match.lastgroup]) for match in TOKEN.finditer(text)]
        self.index = 0

    def take(self):
        self.index += 1
        return self.tokens[self.index - 1]

    def peek(self):
        return self.tokens[self.index]

    def value(self):
        kind, token = self.take()
        if kind == "string":
            return string(token)
        if kind == "number":
            return float(token) if any(c in token for c in ".eE") else int(token)
        if token != "{":
            return LITERALS[token]
        result, implicit = {}, 1
        while self.peek()[1] != "}":
            if self.peek()[1] == "[":
                self.take()
                key = self.value()
                self.index += 2
            elif self.peek()[0] == "name" and self.peek()[1] not in LITERALS:
                key = self.take()[1]
                self.index += 1
            else:
                key, implicit = implicit, implicit + 1
            result[key] = self.value()
            if self.peek()[1] in (",", ";"):
                self.take()
        self.take()
        return result


def decode(raw):
    parser = LuaData(zlib.decompress(base64.b64decode(raw[11:])[16:]).decode())
    parser.take()
    return parser.value()
