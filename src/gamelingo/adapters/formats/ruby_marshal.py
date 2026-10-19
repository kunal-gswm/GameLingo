"""Pure-Python Ruby Marshal 4.8 parser and serializer.

Supports reading, modifying, and writing Ruby Marshal objects (version 4.8)
commonly found in RPG Maker XP (.rxdata), RPG Maker VX (.rvdata), and
RPG Maker VX Ace (.rvdata2) game data files.
"""

from __future__ import annotations

import io
import struct
from typing import Any, Dict, List, Optional, Union


class RubyMarshalError(Exception):
    """Raised when parsing or serializing Ruby Marshal data fails."""

    pass


class RubySymbol(str):
    """Represents a Ruby Symbol."""

    pass


class RubyString:
    """Represents a Ruby String, preserving raw bytes, encoding, and instance variables."""

    def __init__(
        self,
        raw_bytes: Union[bytes, str],
        encoding: str = "utf-8",
        ivars: Optional[Dict[str, Any]] = None,
    ):
        if isinstance(raw_bytes, str):
            self.raw_bytes = raw_bytes.encode(encoding)
        else:
            self.raw_bytes = raw_bytes
        self.encoding = encoding
        self.ivars: Dict[str, Any] = ivars or {}

    @property
    def text(self) -> str:
        """Decodes raw bytes to string, trying specified encoding, then utf-8, then cp932."""
        try:
            return self.raw_bytes.decode(self.encoding)
        except (UnicodeDecodeError, LookupError):
            try:
                return self.raw_bytes.decode("utf-8")
            except UnicodeDecodeError:
                try:
                    return self.raw_bytes.decode("cp932")
                except UnicodeDecodeError:
                    return self.raw_bytes.decode("latin-1", errors="replace")

    def set_text(self, new_text: str, encoding: Optional[str] = None) -> None:
        """Encodes new string into raw bytes using specified or current encoding."""
        enc = encoding or self.encoding
        try:
            self.raw_bytes = new_text.encode(enc)
            self.encoding = enc
        except (UnicodeEncodeError, LookupError):
            self.raw_bytes = new_text.encode("utf-8")
            self.encoding = "utf-8"

    def __str__(self) -> str:
        return self.text

    def __repr__(self) -> str:
        return f"RubyString({self.text!r}, encoding={self.encoding!r})"

    def __eq__(self, other: Any) -> bool:
        if isinstance(other, RubyString):
            return self.raw_bytes == other.raw_bytes
        if isinstance(other, str):
            return self.text == other
        if isinstance(other, bytes):
            return self.raw_bytes == other
        return False

    def __hash__(self) -> int:
        return hash(self.raw_bytes)


class RubyObject:
    """Represents a Ruby Object ('o') with class name and instance variables."""

    def __init__(self, class_name: str, ivars: Optional[Dict[str, Any]] = None):
        self.class_name = class_name
        self.ivars: Dict[str, Any] = ivars or {}

    def get(self, key: str, default: Any = None) -> Any:
        # Check direct key (e.g. '@name') or with '@' prefix
        if key in self.ivars:
            return self.ivars[key]
        at_key = f"@{key}" if not key.startswith("@") else key[1:]
        return self.ivars.get(at_key, default)

    def set(self, key: str, value: Any) -> None:
        # Set matching existing key, or default to '@' prefix
        if key in self.ivars:
            self.ivars[key] = value
        elif f"@{key}" in self.ivars:
            self.ivars[f"@{key}"] = value
        else:
            actual_key = key if key.startswith("@") else f"@{key}"
            self.ivars[actual_key] = value

    def __getitem__(self, key: str) -> Any:
        val = self.get(key)
        if val is None and key not in self.ivars and f"@{key}" not in self.ivars:
            raise KeyError(key)
        return val

    def __setitem__(self, key: str, value: Any) -> None:
        self.set(key, value)

    def __repr__(self) -> str:
        return f"<RubyObject {self.class_name} ivars={list(self.ivars.keys())}>"


class RubyUserDefined:
    """Represents a Ruby object dumped via `_dump` ('u') such as RPG::Table, Color, Tone."""

    def __init__(self, class_name: str, data: bytes):
        self.class_name = class_name
        self.data = data

    def __repr__(self) -> str:
        return f"<RubyUserDefined {self.class_name} len={len(self.data)}>"


class RubyUserMarshal:
    """Represents a Ruby object dumped via `marshal_dump` ('U')."""

    def __init__(self, class_name: str, value: Any):
        self.class_name = class_name
        self.value = value

    def __repr__(self) -> str:
        return f"<RubyUserMarshal {self.class_name} value={self.value!r}>"


class RubyUserClass:
    """Represents a Ruby UserClass ('C') wrapping an object."""

    def __init__(self, class_name: str, wrapped: Any):
        self.class_name = class_name
        self.wrapped = wrapped

    def __repr__(self) -> str:
        return f"<RubyUserClass {self.class_name} wrapped={self.wrapped!r}>"


MAX_RECURSION_DEPTH = 100
MAX_STRING_BYTES = 50 * 1024 * 1024  # 50MB
MAX_CONTAINER_SIZE = 1_000_000


class RubyMarshalReader:
    """Deserializer for Ruby Marshal 4.8 format."""

    def __init__(self, stream: io.BytesIO):
        self.stream = stream
        self.symbols: List[RubySymbol] = []
        self.objects: List[Any] = []
        self.depth = 0

    def read_byte(self) -> int:
        b = self.stream.read(1)
        if not b:
            raise RubyMarshalError("Unexpected end of stream while reading byte")
        return b[0]

    def read_bytes(self, n: int) -> bytes:
        if n < 0 or n > MAX_STRING_BYTES:
            raise RubyMarshalError(f"Requested byte length {n} exceeds bounds")
        data = self.stream.read(n)
        if len(data) != n:
            raise RubyMarshalError(
                f"Unexpected end of stream: expected {n} bytes, got {len(data)}"
            )
        return data

    def read_fixnum(self) -> int:
        b = self.read_byte()
        if b == 0:
            return 0
        if 4 < b < 128:
            return b - 5
        if 1 <= b <= 4:
            raw = self.read_bytes(b)
            # Little endian unsigned
            val = 0
            for i, byte_val in enumerate(raw):
                val |= byte_val << (8 * i)
            return val
        if b >= 252:  # -4 <= signed <= -1
            signed_len = 256 - b
            raw = self.read_bytes(signed_len)
            val = 0
            for i, byte_val in enumerate(raw):
                val |= byte_val << (8 * i)
            # Sign extend
            val -= 1 << (8 * signed_len)
            return val
        if 128 <= b <= 251:  # -128 <= signed < -4
            signed_val = b - 256
            return signed_val + 5
        return b

    def read_symbol(self) -> RubySymbol:
        marker = self.read_byte()
        if marker == 0x3A:  # ':' New symbol
            length = self.read_fixnum()
            name_bytes = self.read_bytes(length)
            sym = RubySymbol(name_bytes.decode("utf-8", errors="replace"))
            self.symbols.append(sym)
            return sym
        elif marker == 0x3B:  # ';' Symbol link
            index = self.read_fixnum()
            if index < 0 or index >= len(self.symbols):
                raise RubyMarshalError(
                    f"Symbol link index {index} out of bounds ({len(self.symbols)})"
                )
            return self.symbols[index]
        else:
            raise RubyMarshalError(
                f"Expected Symbol marker (':' or ';'), got {chr(marker)!r} (0x{marker:02x})"
            )

    def read_object(self) -> Any:
        if self.depth > MAX_RECURSION_DEPTH:
            raise RubyMarshalError("Maximum recursion depth exceeded in Ruby Marshal")
        self.depth += 1
        try:
            return self._read_object_internal()
        finally:
            self.depth -= 1

    def _read_object_internal(self) -> Any:
        marker = self.read_byte()

        # Immediate values (not stored in objects table)
        if marker == 0x30:  # '0' nil
            return None
        if marker == 0x54:  # 'T' true
            return True
        if marker == 0x46:  # 'F' false
            return False
        if marker == 0x69:  # 'i' Fixnum
            return self.read_fixnum()
        if marker == 0x3A:  # ':' Symbol
            length = self.read_fixnum()
            name_bytes = self.read_bytes(length)
            sym = RubySymbol(name_bytes.decode("utf-8", errors="replace"))
            self.symbols.append(sym)
            return sym
        if marker == 0x3B:  # ';' Symbol link
            index = self.read_fixnum()
            if index < 0 or index >= len(self.symbols):
                raise RubyMarshalError(f"Symbol link {index} out of range")
            return self.symbols[index]
        if marker == 0x40:  # '@' Object link
            index = self.read_fixnum()
            if index < 0 or index >= len(self.objects):
                raise RubyMarshalError(
                    f"Object link {index} out of range ({len(self.objects)})"
                )
            return self.objects[index]

        # Non-immediate values (stored in objects table)
        if marker == 0x22:  # '"' String
            length = self.read_fixnum()
            raw_bytes = self.read_bytes(length)
            rs = RubyString(raw_bytes)
            self.objects.append(rs)
            return rs

        if marker == 0x49:  # 'I' IVAR (object with instance variables / encoding)
            # The wrapped object is read, added to objects table, then IVARs are read
            obj = self.read_object()
            num_ivars = self.read_fixnum()
            ivars: Dict[str, Any] = {}
            for _ in range(num_ivars):
                sym = self.read_symbol()
                val = self.read_object()
                ivars[str(sym)] = val

            # Check for encoding attribute in IVAR
            # Ruby 1.9+ encoding: ':E' -> True is UTF-8, False is US-ASCII; ':encoding' -> str
            encoding = "utf-8"
            if ":E" in ivars:
                encoding = "utf-8" if ivars[":E"] is True else "us-ascii"
            elif ":encoding" in ivars:
                enc_val = ivars[":encoding"]
                if isinstance(enc_val, (RubyString, str)):
                    encoding = str(enc_val)

            if isinstance(obj, RubyString):
                obj.encoding = encoding
                obj.ivars.update(ivars)
            elif isinstance(obj, RubyObject):
                obj.ivars.update(ivars)
            return obj

        if marker == 0x5B:  # '[' Array
            length = self.read_fixnum()
            if length > MAX_CONTAINER_SIZE:
                raise RubyMarshalError(f"Array size {length} exceeds maximum bounds")
            arr: List[Any] = []
            self.objects.append(arr)
            for _ in range(length):
                arr.append(self.read_object())
            return arr

        if marker == 0x7B:  # '{' Hash
            num_pairs = self.read_fixnum()
            if num_pairs > MAX_CONTAINER_SIZE:
                raise RubyMarshalError(f"Hash size {num_pairs} exceeds maximum bounds")
            h: Dict[Any, Any] = {}
            self.objects.append(h)
            for _ in range(num_pairs):
                k = self.read_object()
                v = self.read_object()
                h[k] = v
            return h

        if marker == 0x7D:  # '}' Hash with default
            num_pairs = self.read_fixnum()
            h = {}
            self.objects.append(h)
            for _ in range(num_pairs):
                k = self.read_object()
                v = self.read_object()
                h[k] = v
            default_val = self.read_object()
            h["__default__"] = default_val
            return h

        if marker == 0x6F:  # 'o' Object
            class_sym = self.read_symbol()
            obj = RubyObject(str(class_sym))
            self.objects.append(obj)
            num_ivars = self.read_fixnum()
            for _ in range(num_ivars):
                ivar_name = self.read_symbol()
                ivar_val = self.read_object()
                obj.ivars[str(ivar_name)] = ivar_val
            return obj

        if marker == 0x75:  # 'u' UserDefined (_dump)
            class_sym = self.read_symbol()
            length = self.read_fixnum()
            data = self.read_bytes(length)
            ud = RubyUserDefined(str(class_sym), data)
            self.objects.append(ud)
            return ud

        if marker == 0x55:  # 'U' UserMarshal (marshal_dump)
            class_sym = self.read_symbol()
            val = self.read_object()
            um = RubyUserMarshal(str(class_sym), val)
            self.objects.append(um)
            return um

        if marker == 0x43:  # 'C' UserClass
            class_sym = self.read_symbol()
            wrapped = self.read_object()
            uc = RubyUserClass(str(class_sym), wrapped)
            self.objects.append(uc)
            return uc

        if marker == 0x66:  # 'f' Float
            length = self.read_fixnum()
            f_str = self.read_bytes(length).decode("ascii", errors="replace")
            try:
                flt = float(f_str)
            except ValueError:
                flt = 0.0
            self.objects.append(flt)
            return flt

        if marker == 0x6C:  # 'l' Bignum
            sign = chr(self.read_byte())
            num_shortwords = self.read_fixnum()
            raw = self.read_bytes(num_shortwords * 2)
            val = 0
            for i in range(num_shortwords):
                sw = struct.unpack_from("<H", raw, i * 2)[0]
                val |= sw << (16 * i)
            if sign == "-":
                val = -val
            self.objects.append(val)
            return val

        raise RubyMarshalError(
            f"Unsupported Ruby Marshal marker: 0x{marker:02x} ({chr(marker) if 32 <= marker <= 126 else '?'})"
        )


class RubyMarshalWriter:
    """Serializer for Ruby Marshal 4.8 format."""

    def __init__(self, stream: io.BytesIO):
        self.stream = stream
        self.symbols: Dict[str, int] = {}
        self.objects: Dict[int, int] = {}

    def write_byte(self, b: int) -> None:
        self.stream.write(bytes([b & 0xFF]))

    def write_bytes(self, data: bytes) -> None:
        self.stream.write(data)

    def write_fixnum(self, val: int) -> None:
        if val == 0:
            self.write_byte(0)
        elif 0 < val < 123:
            self.write_byte(val + 5)
        elif -124 < val < 0:
            self.write_byte((val - 5) & 0xFF)
        elif val >= 123:
            packed = []
            tmp = val
            while tmp > 0:
                packed.append(tmp & 0xFF)
                tmp >>= 8
            self.write_byte(len(packed))
            self.write_bytes(bytes(packed))
        else:  # val <= -124
            # Two's complement packing
            packed = []
            tmp = val
            # Need minimum bytes to represent signed
            min_bytes = (tmp.bit_length() + 8) // 8
            for i in range(min_bytes):
                packed.append((tmp >> (8 * i)) & 0xFF)
            self.write_byte((-len(packed)) & 0xFF)
            self.write_bytes(bytes(packed))

    def write_symbol(self, sym_str: str) -> None:
        if sym_str in self.symbols:
            self.write_byte(0x3B)  # ';'
            self.write_fixnum(self.symbols[sym_str])
        else:
            idx = len(self.symbols)
            self.symbols[sym_str] = idx
            self.write_byte(0x3A)  # ':'
            b = sym_str.encode("utf-8")
            self.write_fixnum(len(b))
            self.write_bytes(b)

    def write_object(self, obj: Any) -> None:
        # Check immediates
        if obj is None:
            self.write_byte(0x30)  # '0'
            return
        if obj is True:
            self.write_byte(0x54)  # 'T'
            return
        if obj is False:
            self.write_byte(0x46)  # 'F'
            return
        if isinstance(obj, int) and -1073741824 <= obj <= 1073741823:
            self.write_byte(0x69)  # 'i'
            self.write_fixnum(obj)
            return
        if isinstance(obj, RubySymbol):
            self.write_symbol(str(obj))
            return

        # Non-immediate objects (check object table by id)
        obj_id = id(obj)
        if obj_id in self.objects:
            self.write_byte(0x40)  # '@'
            self.write_fixnum(self.objects[obj_id])
            return

        # Register in object table
        idx = len(self.objects)
        self.objects[obj_id] = idx

        if isinstance(obj, RubyString):
            # IVAR String if encoding or ivars present
            has_ivars = bool(obj.ivars)
            enc_utf8 = obj.encoding.lower() in ("utf-8", "utf8")
            if has_ivars or enc_utf8:
                self.write_byte(0x49)  # 'I'
                # Inner string
                self.write_byte(0x22)  # '"'
                self.write_fixnum(len(obj.raw_bytes))
                self.write_bytes(obj.raw_bytes)

                # Collect IVARs
                ivars_to_write = dict(obj.ivars)
                if enc_utf8 and ":E" not in ivars_to_write:
                    ivars_to_write[":E"] = True

                self.write_fixnum(len(ivars_to_write))
                for k, v in ivars_to_write.items():
                    self.write_symbol(k)
                    self.write_object(v)
            else:
                self.write_byte(0x22)  # '"'
                self.write_fixnum(len(obj.raw_bytes))
                self.write_bytes(obj.raw_bytes)
            return

        if isinstance(obj, str):
            # Convert raw str to UTF-8 RubyString
            b = obj.encode("utf-8")
            self.write_byte(0x49)  # 'I'
            self.write_byte(0x22)  # '"'
            self.write_fixnum(len(b))
            self.write_bytes(b)
            self.write_fixnum(1)
            self.write_symbol(":E")
            self.write_object(True)
            return

        if isinstance(obj, bytes):
            self.write_byte(0x22)  # '"'
            self.write_fixnum(len(obj))
            self.write_bytes(obj)
            return

        if isinstance(obj, list):
            self.write_byte(0x5B)  # '['
            self.write_fixnum(len(obj))
            for item in obj:
                self.write_object(item)
            return

        if isinstance(obj, dict):
            self.write_byte(0x7B)  # '{'
            items = [(k, v) for k, v in obj.items() if k != "__default__"]
            self.write_fixnum(len(items))
            for k, v in items:
                self.write_object(k)
                self.write_object(v)
            return

        if isinstance(obj, RubyObject):
            self.write_byte(0x6F)  # 'o'
            self.write_symbol(obj.class_name)
            self.write_fixnum(len(obj.ivars))
            for k, v in obj.ivars.items():
                self.write_symbol(k)
                self.write_object(v)
            return

        if isinstance(obj, RubyUserDefined):
            self.write_byte(0x75)  # 'u'
            self.write_symbol(obj.class_name)
            self.write_fixnum(len(obj.data))
            self.write_bytes(obj.data)
            return

        if isinstance(obj, RubyUserMarshal):
            self.write_byte(0x55)  # 'U'
            self.write_symbol(obj.class_name)
            self.write_object(obj.value)
            return

        if isinstance(obj, RubyUserClass):
            self.write_byte(0x43)  # 'C'
            self.write_symbol(obj.class_name)
            self.write_object(obj.wrapped)
            return

        if isinstance(obj, float):
            self.write_byte(0x66)  # 'f'
            f_str = f"{obj:.16g}".encode("ascii")
            self.write_fixnum(len(f_str))
            self.write_bytes(f_str)
            return

        if isinstance(obj, int):
            # Bignum
            self.write_byte(0x6C)  # 'l'
            sign = b"+" if obj >= 0 else b"-"
            self.write_bytes(sign)
            abs_val = abs(obj)
            shortwords = []
            while abs_val > 0:
                shortwords.append(abs_val & 0xFFFF)
                abs_val >>= 16
            self.write_fixnum(len(shortwords))
            for sw in shortwords:
                self.write_bytes(struct.pack("<H", sw))
            return

        raise RubyMarshalError(f"Cannot serialize object of type {type(obj)}")


def load_marshal(data: Union[bytes, io.BytesIO]) -> Any:
    """Loads a Ruby Marshal 4.8 dump from bytes or a stream."""
    stream = io.BytesIO(data) if isinstance(data, bytes) else data
    header = stream.read(2)
    if header != b"\x04\x08":
        raise RubyMarshalError(
            f"Invalid Ruby Marshal header: {header!r} (expected b'\\x04\\x08')"
        )
    reader = RubyMarshalReader(stream)
    return reader.read_object()


def dump_marshal(obj: Any) -> bytes:
    """Serializes a Python/Ruby structure into Ruby Marshal 4.8 bytes."""
    stream = io.BytesIO()
    stream.write(b"\x04\x08")
    writer = RubyMarshalWriter(stream)
    writer.write_object(obj)
    return stream.getvalue()


def _tokenize_locator(locator: str) -> List[Any]:
    import re

    return [
        m.group(1) or int(m.group(2))
        for m in re.finditer(r"([a-zA-Z0-9_]+)|\[(\d+)\]", locator)
    ]


def _get_field(curr: Any, key: Any) -> Any:
    if isinstance(curr, list):
        idx = int(key)
        if 0 <= idx < len(curr):
            return curr[idx]
        raise IndexError(f"List index {idx} out of range")
    if isinstance(curr, dict):
        if key in curr:
            return curr[key]
        if isinstance(key, str) and key.isdigit() and int(key) in curr:
            return curr[int(key)]
        raise KeyError(f"Key {key!r} not found in dict")
    if isinstance(curr, RubyObject):
        val = curr.get(str(key))
        if val is not None:
            return val
        raise KeyError(f"Field {key!r} not found in {curr.class_name}")
    raise TypeError(f"Cannot get field {key!r} from {type(curr)}")


def resolve_ruby_locator(data: Any, locator: str) -> str:
    """Resolves a hierarchical locator within a Ruby Marshal object tree and returns its text."""
    tokens = _tokenize_locator(locator)
    curr = data
    i = 0
    try:
        while i < len(tokens):
            t = tokens[i]
            # Check if curr is an EventCommand-like object
            cmd_code = None
            params = None
            if isinstance(curr, RubyObject):
                cmd_code = curr.get("code")
                params = curr.get("parameters")
            elif isinstance(curr, dict) and "code" in curr:
                cmd_code = curr.get("code")
                params = curr.get("parameters")

            if cmd_code is not None and params is not None:
                if i == len(tokens) - 1:
                    if t == "when" and cmd_code == 402:
                        val = params[1] if len(params) > 1 else ""
                        return str(val.text if isinstance(val, RubyString) else val)
                    if t == "speaker" and cmd_code == 101:
                        val = params[4] if len(params) > 4 else ""
                        return str(val.text if isinstance(val, RubyString) else val)
                    if t == "name" and cmd_code == 320:
                        val = params[1] if len(params) > 1 else ""
                        return str(val.text if isinstance(val, RubyString) else val)
                    if t == "nickname" and cmd_code == 324:
                        val = params[1] if len(params) > 1 else ""
                        return str(val.text if isinstance(val, RubyString) else val)
                    if t == "profile" and cmd_code == 325:
                        val = params[1] if len(params) > 1 else ""
                        return str(val.text if isinstance(val, RubyString) else val)
                if i == len(tokens) - 2 and t == "choices" and cmd_code == 102:
                    choice_idx = int(tokens[i + 1])
                    val = params[0][choice_idx]
                    return str(val.text if isinstance(val, RubyString) else val)

            curr = _get_field(curr, t)

            # Check if newly resolved curr is an EventCommand
            if i == len(tokens) - 1:
                if isinstance(curr, RubyObject):
                    c_code = curr.get("code")
                    c_params = curr.get("parameters")
                    if c_code in (401, 405) or (
                        c_code == 101
                        and c_params
                        and isinstance(c_params[0], (RubyString, str))
                    ):
                        val = c_params[0]
                        return str(val.text if isinstance(val, RubyString) else val)
                elif isinstance(curr, dict) and "code" in curr:
                    c_code = curr.get("code")
                    c_params = curr.get("parameters")
                    if c_code in (401, 405) or (
                        c_code == 101
                        and c_params
                        and isinstance(c_params[0], (RubyString, str))
                    ):
                        val = c_params[0]
                        return str(val.text if isinstance(val, RubyString) else val)

            i += 1

        if isinstance(curr, RubyString):
            return curr.text
        return str(curr) if curr is not None else ""
    except Exception as e:
        raise ValueError(f"Could not resolve Ruby locator {locator!r}: {e}")


def apply_ruby_locator(
    data: Any, locator: str, new_value: str, encoding: Optional[str] = None
) -> None:
    """Applies a translated text value into a Ruby Marshal object tree at locator."""
    tokens = _tokenize_locator(locator)
    curr = data
    i = 0
    try:
        while i < len(tokens):
            t = tokens[i]
            cmd_code = None
            params = None
            if isinstance(curr, RubyObject):
                cmd_code = curr.get("code")
                params = curr.get("parameters")
            elif isinstance(curr, dict) and "code" in curr:
                cmd_code = curr.get("code")
                params = curr.get("parameters")

            if cmd_code is not None and params is not None:
                if i == len(tokens) - 1:

                    def _assign_param(p_idx: int):
                        while len(params) <= p_idx:
                            params.append(RubyString(b"", encoding=encoding or "utf-8"))
                        if isinstance(params[p_idx], RubyString):
                            params[p_idx].set_text(new_value, encoding=encoding)
                        else:
                            params[p_idx] = RubyString(
                                new_value.encode(encoding or "utf-8"),
                                encoding=encoding or "utf-8",
                            )

                    if t == "when" and cmd_code == 402:
                        _assign_param(1)
                        return
                    if t == "speaker" and cmd_code == 101:
                        _assign_param(4)
                        return
                    if t == "name" and cmd_code == 320:
                        _assign_param(1)
                        return
                    if t == "nickname" and cmd_code == 324:
                        _assign_param(1)
                        return
                    if t == "profile" and cmd_code == 325:
                        _assign_param(1)
                        return
                if i == len(tokens) - 2 and t == "choices" and cmd_code == 102:
                    choice_idx = int(tokens[i + 1])
                    choices_arr = params[0]
                    if isinstance(choices_arr[choice_idx], RubyString):
                        choices_arr[choice_idx].set_text(new_value, encoding=encoding)
                    else:
                        choices_arr[choice_idx] = RubyString(
                            new_value.encode(encoding or "utf-8"),
                            encoding=encoding or "utf-8",
                        )
                    return

            if i == len(tokens) - 1:
                # Setting final field on curr
                if isinstance(curr, list):
                    idx = int(t)
                    if isinstance(curr[idx], RubyString):
                        curr[idx].set_text(new_value, encoding=encoding)
                    else:
                        curr[idx] = RubyString(
                            new_value.encode(encoding or "utf-8"),
                            encoding=encoding or "utf-8",
                        )
                    return
                elif isinstance(curr, dict):
                    key = (
                        int(t)
                        if (isinstance(t, str) and t.isdigit() and int(t) in curr)
                        else t
                    )
                    if isinstance(curr.get(key), RubyString):
                        curr[key].set_text(new_value, encoding=encoding)
                    else:
                        curr[key] = RubyString(
                            new_value.encode(encoding or "utf-8"),
                            encoding=encoding or "utf-8",
                        )
                    return
                elif isinstance(curr, RubyObject):
                    # Check if curr[t] is an EventCommand (401 / 405 / 101)
                    target = curr.get(str(t))
                    if isinstance(target, RubyObject):
                        c_code = target.get("code")
                        c_params = target.get("parameters")
                        if c_code in (401, 405) or (
                            c_code == 101
                            and c_params
                            and isinstance(c_params[0], (RubyString, str))
                        ):
                            if isinstance(c_params[0], RubyString):
                                c_params[0].set_text(new_value, encoding=encoding)
                            else:
                                c_params[0] = RubyString(
                                    new_value.encode(encoding or "utf-8"),
                                    encoding=encoding or "utf-8",
                                )
                            return
                    if isinstance(target, RubyString):
                        target.set_text(new_value, encoding=encoding)
                    else:
                        curr.set(
                            str(t),
                            RubyString(
                                new_value.encode(encoding or "utf-8"),
                                encoding=encoding or "utf-8",
                            ),
                        )
                    return

            curr = _get_field(curr, t)
            i += 1

        raise ValueError(f"Could not apply Ruby locator {locator!r}")
    except Exception as e:
        raise ValueError(f"Failed to apply Ruby locator {locator!r}: {e}")
