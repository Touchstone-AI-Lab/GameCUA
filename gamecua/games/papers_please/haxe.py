"""Data-only reader for native Haxe serialized save objects."""

import re
from urllib.parse import unquote


class Reader:
    """Cursor over one Haxe serialization string with its string and object caches."""

    def __init__(self, text):
        self.text = text
        self.index = 0
        self.strings = []
        self.objects = []

    def token(self, pattern):
        """Consume and return the text matching pattern at the cursor."""
        match = re.match(pattern, self.text[self.index :])
        self.index += len(match[0])
        return match[0]

    def entries(self, result, end):
        """Read key and value pairs into result up to the end marker."""
        self.objects.append(result)
        while self.text[self.index] != end:
            key = self.read()
            result[key] = self.read()
        self.index += 1
        return result

    def read(self):
        """Read the next serialized value."""
        token = self.text[self.index]
        self.index += 1
        if token in "ntfz":
            return {"n": None, "t": True, "f": False, "z": 0}[token]
        if token == "i":
            return int(self.token(r"-?\d+"))
        if token == "d":
            return float(self.token(r"[-+0-9.eE]+"))
        if token == "y":
            size = int(self.token(r"\d+"))
            self.index += size + 1
            value = unquote(self.text[self.index - size : self.index])
            self.strings.append(value)
            return value
        if token in "Rr":
            return (self.strings if token == "R" else self.objects)[int(self.token(r"\d+"))]
        if token in "co":
            return self.entries({"__class__": self.read()} if token == "c" else {}, "g")
        if token == "b":
            return self.entries({}, "h")
        if token in "al":
            result = []
            self.objects.append(result)
            while self.text[self.index] != "h":
                if token == "a" and self.text[self.index] == "u":
                    self.index += 1
                    result.extend([None] * int(self.token(r"\d+")))
                else:
                    result.append(self.read())
            self.index += 1
            return result
        if token == "w":
            name, constructor = self.read(), self.read()
            self.index += 1
            count = int(self.token(r"\d+"))
            result = {
                "__enum__": name,
                "constructor": constructor,
                "arguments": [self.read() for _ in range(count)],
            }
            self.objects.append(result)
            return result
        raise ValueError("Unsupported native serialization token")


def read(text):
    """Decode one Haxe serialized value."""
    return Reader(text).read()
