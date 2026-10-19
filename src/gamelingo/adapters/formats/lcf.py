"""Pure-Python RPG Maker 2000/2003 LCF (LcfDataBase, LcfMapTree, LcfMapUnit) parser and serializer.

Supports reading, modifying, and safely writing LCF files:
- RPG_RT.ldb (Database)
- RPG_RT.lmt (Map Tree)
- Map####.lmu (Map Unit)
with encoding detection and preservation (CP932 / Shift_JIS, UTF-8, Windows-1252).
"""

from __future__ import annotations

import io
import re
from typing import Any, Dict, List, Optional, Tuple, Union


class LcfError(Exception):
    """Raised when parsing or serializing LCF binary data fails."""

    pass


def read_ber_int(stream: io.BytesIO) -> int:
    """Reads a BER variable-length quantity integer from stream."""
    val = 0
    bytes_read = 0
    while True:
        b = stream.read(1)
        if not b:
            raise LcfError("Unexpected EOF while reading BER integer")
        byte_val = b[0]
        val = (val << 7) | (byte_val & 0x7F)
        bytes_read += 1
        if bytes_read > 5:
            raise LcfError("BER integer exceeds maximum 5-byte length")
        if not (byte_val & 0x80):
            break
    return val


def write_ber_int(val: int) -> bytes:
    """Encodes an integer into a BER variable-length quantity byte sequence."""
    if val < 0:
        raise LcfError(f"BER integer cannot be negative: {val}")
    if val == 0:
        return b"\x00"
    chunks = []
    tmp = val
    while tmp > 0:
        chunks.append(tmp & 0x7F)
        tmp >>= 7
    chunks.reverse()
    out = bytearray()
    for i, c in enumerate(chunks):
        if i < len(chunks) - 1:
            out.append(c | 0x80)
        else:
            out.append(c)
    return bytes(out)


def detect_encoding(raw_bytes: bytes) -> str:
    """Detects whether raw byte content is UTF-8, CP932 (Shift_JIS), or Windows-1252."""
    if not raw_bytes:
        return "utf-8"
    try:
        decoded_utf8 = raw_bytes.decode("utf-8")
        # Check if it has Japanese characters
        if re.search(r"[\u3040-\u30ff\u4e00-\u9fff]", decoded_utf8):
            return "utf-8"
    except UnicodeDecodeError:
        pass

    try:
        decoded_cp932 = raw_bytes.decode("cp932")
        if re.search(r"[\u3040-\u30ff\u4e00-\u9fff]", decoded_cp932):
            return "cp932"
    except UnicodeDecodeError:
        pass

    try:
        raw_bytes.decode("utf-8")
        return "utf-8"
    except UnicodeDecodeError:
        return "cp932"


class LcfCommand:
    """Represents an RPG Maker 2000/2003 event command."""

    def __init__(
        self,
        code: int,
        indent: int,
        string: Union[str, bytes],
        args: Optional[List[int]] = None,
        encoding: str = "cp932",
    ):
        self.code = code
        self.indent = indent
        self._raw_string: bytes = (
            string.encode(encoding) if isinstance(string, str) else string
        )
        self.args: List[int] = args or []
        self.encoding = encoding

    @property
    def string(self) -> str:
        try:
            return self._raw_string.decode(self.encoding)
        except UnicodeDecodeError:
            try:
                return self._raw_string.decode("cp932")
            except UnicodeDecodeError:
                return self._raw_string.decode("latin-1", errors="replace")

    def set_string(self, new_text: str, encoding: Optional[str] = None) -> None:
        enc = encoding or self.encoding
        try:
            self._raw_string = new_text.encode(enc)
            self.encoding = enc
        except (UnicodeEncodeError, LookupError):
            self._raw_string = new_text.encode("utf-8")
            self.encoding = "utf-8"

    def __repr__(self) -> str:
        return f"<LcfCommand code={self.code} indent={self.indent} string={self.string!r} args={self.args}>"


class LcfStruct:
    """Represents an LCF chunk dictionary where chunk_id maps to raw bytes, sub-structs, or arrays."""

    def __init__(self):
        self.chunks: Dict[int, Any] = {}

    def get_chunk(self, chunk_id: int, default: Any = None) -> Any:
        return self.chunks.get(chunk_id, default)

    def set_chunk(self, chunk_id: int, value: Any) -> None:
        self.chunks[chunk_id] = value

    def get_string(self, chunk_id: int, encoding: str = "cp932") -> str:
        val = self.chunks.get(chunk_id)
        if val is None:
            return ""
        if isinstance(val, str):
            return val
        if isinstance(val, bytes):
            try:
                return val.decode(encoding)
            except UnicodeDecodeError:
                try:
                    return val.decode("cp932")
                except UnicodeDecodeError:
                    return val.decode("latin-1", errors="replace")
        return str(val)

    def set_string(self, chunk_id: int, text: str, encoding: str = "cp932") -> None:
        try:
            self.chunks[chunk_id] = text.encode(encoding)
        except (UnicodeEncodeError, LookupError):
            self.chunks[chunk_id] = text.encode("utf-8")


class LcfArray:
    """Represents an LCF indexed array (count + [id + struct])."""

    def __init__(self):
        self.items: Dict[int, LcfStruct] = {}

    def __getitem__(self, item_id: int) -> LcfStruct:
        return self.items[item_id]

    def __setitem__(self, item_id: int, value: LcfStruct) -> None:
        self.items[item_id] = value

    def __contains__(self, item_id: int) -> bool:
        return item_id in self.items

    def __len__(self) -> int:
        return len(self.items)


KNOWN_LCF_HEADERS = {
    b"LcfDataBase": "RPG_RT.ldb",
    b"LcfMapTree": "RPG_RT.lmt",
    b"LcfMapUnit": "Map Unit",
}


class LcfReader:
    """Reader for LCF binary data."""

    def __init__(self, stream: io.BytesIO, default_encoding: str = "cp932"):
        self.stream = stream
        self.default_encoding = default_encoding
        self.detected_encoding = default_encoding

    def read_header(self) -> str:
        # Read header: length-prefixed ASCII string
        b = self.stream.read(1)
        if not b:
            raise LcfError("Unexpected EOF while reading LCF header")
        length = b[0]
        header_bytes = self.stream.read(length)
        if header_bytes not in KNOWN_LCF_HEADERS:
            # Check if header matches without length prefix
            all_bytes = b + header_bytes
            for h in KNOWN_LCF_HEADERS:
                if h in all_bytes:
                    return h.decode("ascii")
            raise LcfError(f"Unknown LCF header: {header_bytes!r}")
        return header_bytes.decode("ascii")

    def read_struct(self) -> LcfStruct:
        st = LcfStruct()
        while True:
            pos = self.stream.tell()
            b = self.stream.read(1)
            if not b:
                break
            self.stream.seek(pos)
            chunk_id = read_ber_int(self.stream)
            if chunk_id == 0:
                # End of struct
                break
            chunk_len = read_ber_int(self.stream)
            chunk_data = self.stream.read(chunk_len)
            if len(chunk_data) != chunk_len:
                raise LcfError(
                    f"Unexpected EOF in chunk {chunk_id}: expected {chunk_len}, got {len(chunk_data)}"
                )
            st.set_chunk(chunk_id, chunk_data)
        return st

    def parse_array_of_structs(self, raw_bytes: bytes) -> LcfArray:
        stream = io.BytesIO(raw_bytes)
        count = read_ber_int(stream)
        arr = LcfArray()
        sub_reader = LcfReader(stream, self.default_encoding)
        for _ in range(count):
            item_id = read_ber_int(stream)
            item_struct = sub_reader.read_struct()
            arr[item_id] = item_struct
        return arr

    def parse_event_command_list(
        self, raw_bytes: bytes, encoding: Optional[str] = None
    ) -> List[LcfCommand]:
        enc = encoding or self.default_encoding
        stream = io.BytesIO(raw_bytes)
        commands: List[LcfCommand] = []
        while stream.tell() < len(raw_bytes):
            try:
                code = read_ber_int(stream)
                indent = read_ber_int(stream)
                str_len = read_ber_int(stream)
                str_bytes = stream.read(str_len)
                num_args = read_ber_int(stream)
                args = [read_ber_int(stream) for _ in range(num_args)]
                commands.append(
                    LcfCommand(code, indent, str_bytes, args=args, encoding=enc)
                )
            except Exception:
                break
        return commands


class LcfWriter:
    """Writer for LCF binary data."""

    def __init__(self, stream: io.BytesIO, encoding: str = "cp932"):
        self.stream = stream
        self.encoding = encoding

    def write_header(self, header: str) -> None:
        header_bytes = header.encode("ascii")
        self.stream.write(bytes([len(header_bytes)]))
        self.stream.write(header_bytes)

    def write_struct(self, st: LcfStruct) -> None:
        for chunk_id, chunk_val in sorted(st.chunks.items()):
            if chunk_id == 0:
                continue
            self.stream.write(write_ber_int(chunk_id))
            if isinstance(chunk_val, bytes):
                self.stream.write(write_ber_int(len(chunk_val)))
                self.stream.write(chunk_val)
            elif isinstance(chunk_val, LcfStruct):
                sub_buf = io.BytesIO()
                sub_writer = LcfWriter(sub_buf, self.encoding)
                sub_writer.write_struct(chunk_val)
                raw = sub_buf.getvalue()
                self.stream.write(write_ber_int(len(raw)))
                self.stream.write(raw)
            elif isinstance(chunk_val, LcfArray):
                raw = serialize_array_of_structs(chunk_val, self.encoding)
                self.stream.write(write_ber_int(len(raw)))
                self.stream.write(raw)
            elif (
                isinstance(chunk_val, list)
                and chunk_val
                and isinstance(chunk_val[0], LcfCommand)
            ):
                raw = serialize_event_command_list(chunk_val, self.encoding)
                self.stream.write(write_ber_int(len(raw)))
                self.stream.write(raw)
            else:
                # String or other
                b = str(chunk_val).encode(self.encoding)
                self.stream.write(write_ber_int(len(b)))
                self.stream.write(b)

        # End of struct
        self.stream.write(write_ber_int(0))


def serialize_array_of_structs(arr: LcfArray, encoding: str = "cp932") -> bytes:
    buf = io.BytesIO()
    buf.write(write_ber_int(len(arr)))
    writer = LcfWriter(buf, encoding)
    for item_id, item_struct in sorted(arr.items.items()):
        buf.write(write_ber_int(item_id))
        writer.write_struct(item_struct)
    return buf.getvalue()


def serialize_event_command_list(
    commands: List[LcfCommand], encoding: str = "cp932"
) -> bytes:
    buf = io.BytesIO()
    for cmd in commands:
        buf.write(write_ber_int(cmd.code))
        buf.write(write_ber_int(cmd.indent))
        raw_str = (
            cmd._raw_string
            if hasattr(cmd, "_raw_string")
            else cmd.string.encode(encoding)
        )
        buf.write(write_ber_int(len(raw_str)))
        buf.write(raw_str)
        buf.write(write_ber_int(len(cmd.args)))
        for a in cmd.args:
            buf.write(write_ber_int(a))
    return buf.getvalue()


class LcfDatabase:
    """Represents RPG_RT.ldb database."""

    def __init__(self, root_struct: LcfStruct, encoding: str = "cp932"):
        self.root = root_struct
        self.encoding = encoding
        self.reader = LcfReader(io.BytesIO(), encoding)

        # Arrays cached for easy modification
        self.actors: LcfArray = self._get_or_parse_array(11)
        self.skills: LcfArray = self._get_or_parse_array(12)
        self.items: LcfArray = self._get_or_parse_array(13)
        self.enemies: LcfArray = self._get_or_parse_array(14)
        self.states: LcfArray = self._get_or_parse_array(18)
        self.common_events: LcfArray = self._get_or_parse_array(21)
        self.terms: Optional[LcfStruct] = self._get_or_parse_struct(26)

    def _get_or_parse_array(self, chunk_id: int) -> LcfArray:
        val = self.root.get_chunk(chunk_id)
        if isinstance(val, LcfArray):
            return val
        if isinstance(val, bytes):
            arr = self.reader.parse_array_of_structs(val)
            self.root.set_chunk(chunk_id, arr)
            return arr
        arr = LcfArray()
        self.root.set_chunk(chunk_id, arr)
        return arr

    def _get_or_parse_struct(self, chunk_id: int) -> Optional[LcfStruct]:
        val = self.root.get_chunk(chunk_id)
        if isinstance(val, LcfStruct):
            return val
        if isinstance(val, bytes):
            st = LcfReader(io.BytesIO(val), self.encoding).read_struct()
            self.root.set_chunk(chunk_id, st)
            return st
        return None

    def serialize(self) -> bytes:
        buf = io.BytesIO()
        writer = LcfWriter(buf, self.encoding)
        writer.write_header("LcfDataBase")
        writer.write_struct(self.root)
        return buf.getvalue()


def load_lcf(
    data: Union[bytes, io.BytesIO], encoding: Optional[str] = None
) -> Tuple[str, LcfStruct, str]:
    """Loads an LCF file and returns (header, root_struct, detected_encoding)."""
    stream = io.BytesIO(data) if isinstance(data, bytes) else data
    raw_content = stream.getvalue() if isinstance(stream, io.BytesIO) else b""
    detected_enc = encoding or detect_encoding(raw_content)

    reader = LcfReader(stream, detected_enc)
    header = reader.read_header()
    root = reader.read_struct()
    return header, root, detected_enc


def dump_lcf(header: str, root: LcfStruct, encoding: str = "cp932") -> bytes:
    """Serializes an LcfStruct to bytes with the given LCF header."""
    buf = io.BytesIO()
    writer = LcfWriter(buf, encoding)
    writer.write_header(header)
    writer.write_struct(root)
    return buf.getvalue()


LCF_TABLE_CHUNKS = {
    "actors": 11,
    "skills": 12,
    "items": 13,
    "enemies": 14,
    "states": 18,
    "common_events": 21,
    "system": 22,
    "terms": 26,
    "events": 71,
    "maps": 1,
}

LCF_SUBFIELD_CHUNKS = {
    "name": 1,
    "title": 2,
    "description": 2,
    "game_title": 31,
    "message1": 51,
    "message2": 52,
    "message3": 53,
    "message4": 54,
}


def _tokenize_lcf_locator(locator: str) -> List[Any]:
    return [
        m.group(1) or int(m.group(2))
        for m in re.finditer(r"([a-zA-Z0-9_]+)|\[(\d+)\]", locator)
    ]


def resolve_lcf_locator(root: LcfStruct, locator: str, encoding: str = "cp932") -> str:
    """Resolves text at locator within an LcfStruct."""
    tokens = _tokenize_lcf_locator(locator)
    reader = LcfReader(io.BytesIO(), encoding)

    table_name = str(tokens[0])
    chunk_id = LCF_TABLE_CHUNKS.get(table_name, None)
    if chunk_id is None:
        raise ValueError(f"Unknown LCF table in locator: {table_name}")

    if table_name == "system":
        st_data = root.get_chunk(chunk_id)
        if isinstance(st_data, bytes):
            st_data = LcfReader(io.BytesIO(st_data), encoding).read_struct()
            root.set_chunk(chunk_id, st_data)
        field_name = str(tokens[1]) if len(tokens) > 1 else "game_title"
        sub_id = LCF_SUBFIELD_CHUNKS.get(field_name, 31)
        return st_data.get_string(sub_id, encoding=encoding)

    # Array table
    arr_data = root.get_chunk(chunk_id)
    if isinstance(arr_data, bytes):
        arr_data = reader.parse_array_of_structs(arr_data)
        root.set_chunk(chunk_id, arr_data)

    item_id = int(tokens[1])
    item_struct = arr_data.items.get(item_id)
    if item_struct is None:
        raise ValueError(f"Item {item_id} not found in LCF table {table_name}")

    if len(tokens) >= 3 and tokens[2] == "pages":
        # Map event pages: events[id].pages[page_idx].list[cmd_idx]
        pages_raw = item_struct.get_chunk(5)
        if isinstance(pages_raw, bytes):
            pages_arr = reader.parse_array_of_structs(pages_raw)
            item_struct.set_chunk(5, pages_arr)
        else:
            pages_arr = pages_raw

        page_id = int(tokens[3]) + 1  # 1-indexed in LCF
        page_struct = pages_arr.items.get(
            page_id, list(pages_arr.items.values())[int(tokens[3])]
        )
        cmds_raw = page_struct.get_chunk(52)
        if isinstance(cmds_raw, bytes):
            cmds = reader.parse_event_command_list(cmds_raw, encoding)
            page_struct.set_chunk(52, cmds)
        else:
            cmds = cmds_raw

        cmd_idx = int(tokens[5])
        return cmds[cmd_idx].string

    if len(tokens) >= 3 and tokens[2] == "list":
        # Common event commands: common_events[id].list[cmd_idx]
        cmds_raw = item_struct.get_chunk(52)
        if isinstance(cmds_raw, bytes):
            cmds = reader.parse_event_command_list(cmds_raw, encoding)
            item_struct.set_chunk(52, cmds)
        else:
            cmds = cmds_raw
        cmd_idx = int(tokens[3])
        return cmds[cmd_idx].string

    field_name = str(tokens[2])
    sub_id = LCF_SUBFIELD_CHUNKS.get(field_name, 1)
    return item_struct.get_string(sub_id, encoding=encoding)


def apply_lcf_locator(
    root: LcfStruct, locator: str, new_value: str, encoding: str = "cp932"
) -> None:
    """Applies new translated text into an LcfStruct at locator."""
    tokens = _tokenize_lcf_locator(locator)
    reader = LcfReader(io.BytesIO(), encoding)

    table_name = str(tokens[0])
    chunk_id = LCF_TABLE_CHUNKS.get(table_name, None)
    if chunk_id is None:
        raise ValueError(f"Unknown LCF table in locator: {table_name}")

    if table_name == "system":
        st_data = root.get_chunk(chunk_id)
        if isinstance(st_data, bytes):
            st_data = LcfReader(io.BytesIO(st_data), encoding).read_struct()
            root.set_chunk(chunk_id, st_data)
        field_name = str(tokens[1]) if len(tokens) > 1 else "game_title"
        sub_id = LCF_SUBFIELD_CHUNKS.get(field_name, 31)
        st_data.set_string(sub_id, new_value, encoding=encoding)
        return

    # Array table
    arr_data = root.get_chunk(chunk_id)
    if isinstance(arr_data, bytes):
        arr_data = reader.parse_array_of_structs(arr_data)
        root.set_chunk(chunk_id, arr_data)

    item_id = int(tokens[1])
    item_struct = arr_data.items.get(item_id)
    if item_struct is None:
        raise ValueError(f"Item {item_id} not found in LCF table {table_name}")

    if len(tokens) >= 3 and tokens[2] == "pages":
        pages_raw = item_struct.get_chunk(5)
        if isinstance(pages_raw, bytes):
            pages_arr = reader.parse_array_of_structs(pages_raw)
            item_struct.set_chunk(5, pages_arr)
        else:
            pages_arr = pages_raw

        page_id = int(tokens[3]) + 1
        page_struct = pages_arr.items.get(
            page_id, list(pages_arr.items.values())[int(tokens[3])]
        )
        cmds_raw = page_struct.get_chunk(52)
        if isinstance(cmds_raw, bytes):
            cmds = reader.parse_event_command_list(cmds_raw, encoding)
            page_struct.set_chunk(52, cmds)
        else:
            cmds = cmds_raw

        cmd_idx = int(tokens[5])
        cmds[cmd_idx].set_string(new_value, encoding=encoding)
        return

    if len(tokens) >= 3 and tokens[2] == "list":
        cmds_raw = item_struct.get_chunk(52)
        if isinstance(cmds_raw, bytes):
            cmds = reader.parse_event_command_list(cmds_raw, encoding)
            item_struct.set_chunk(52, cmds)
        else:
            cmds = cmds_raw
        cmd_idx = int(tokens[3])
        cmds[cmd_idx].set_string(new_value, encoding=encoding)
        return

    field_name = str(tokens[2])
    sub_id = LCF_SUBFIELD_CHUNKS.get(field_name, 1)
    item_struct.set_string(sub_id, new_value, encoding=encoding)
