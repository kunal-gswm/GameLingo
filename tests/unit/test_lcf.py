import io

import pytest

from gamelingo.adapters.formats.lcf import (
    LcfArray,
    LcfCommand,
    LcfDatabase,
    LcfError,
    LcfStruct,
    detect_encoding,
    dump_lcf,
    load_lcf,
    read_ber_int,
    write_ber_int,
)


def test_lcf_ber_integers():
    test_cases = [0, 1, 42, 127, 128, 255, 256, 16383, 16384, 2097151, 2097152]
    for val in test_cases:
        encoded = write_ber_int(val)
        decoded = read_ber_int(io.BytesIO(encoded))
        assert decoded == val

    # Negative BER integer should raise error
    with pytest.raises(LcfError):
        write_ber_int(-1)


def test_lcf_encoding_detection():
    jp_text = "勇者アレックス"
    cp932_bytes = jp_text.encode("cp932")
    utf8_bytes = jp_text.encode("utf-8")

    assert detect_encoding(cp932_bytes) == "cp932"
    assert detect_encoding(utf8_bytes) == "utf-8"


def test_lcf_command_japanese_text():
    cmd = LcfCommand(
        code=10110,
        indent=0,
        string="こんにちは、勇者様！",
        args=[0],
        encoding="cp932",
    )
    assert cmd.string == "こんにちは、勇者様！"
    cmd.set_string("Hello, Hero!", encoding="cp932")
    assert cmd.string == "Hello, Hero!"


def test_lcf_database_round_trip():
    # Build synthetic LcfDatabase
    root = LcfStruct()

    # Actors array in chunk 11
    actors = LcfArray()
    actor1 = LcfStruct()
    actor1.set_string(1, "アレックス", encoding="cp932")  # Name
    actor1.set_string(2, "見習い剣士", encoding="cp932")  # Title
    actors[1] = actor1
    root.set_chunk(11, actors)

    # System chunk in chunk 22
    system = LcfStruct()
    system.set_string(31, "ドラゴンクエスト風RPG", encoding="cp932")
    root.set_chunk(22, system)

    # Serialize
    dumped = dump_lcf("LcfDataBase", root, encoding="cp932")
    assert len(dumped) > 0

    # Load back
    header, loaded_root, enc = load_lcf(dumped, encoding="cp932")
    assert header == "LcfDataBase"
    db = LcfDatabase(loaded_root, encoding="cp932")

    loaded_actor = db.actors[1]
    assert loaded_actor.get_string(1, encoding="cp932") == "アレックス"
    assert loaded_actor.get_string(2, encoding="cp932") == "見習い剣士"

    # Modify and serialize again
    loaded_actor.set_string(1, "Alex", encoding="cp932")
    re_dumped = db.serialize()
    _, re_loaded_root, _ = load_lcf(re_dumped, encoding="cp932")
    re_db = LcfDatabase(re_loaded_root, encoding="cp932")
    assert re_db.actors[1].get_string(1, encoding="cp932") == "Alex"
    assert re_db.actors[1].get_string(2, encoding="cp932") == "見習い剣士"


def test_lcf_error_handling():
    with pytest.raises(LcfError, match="Unknown LCF header"):
        load_lcf(b"\x06RandomGarbage")

    with pytest.raises(LcfError, match="Unexpected EOF"):
        load_lcf(b"\x0bLcfDataBase\x01\x10")  # Chunk claims length 16, but truncated
