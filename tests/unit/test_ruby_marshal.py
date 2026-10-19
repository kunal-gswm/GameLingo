import pytest

from gamelingo.adapters.formats.ruby_marshal import (
    RubyMarshalError,
    RubyObject,
    RubyString,
    RubySymbol,
    RubyUserClass,
    RubyUserDefined,
    RubyUserMarshal,
    dump_marshal,
    load_marshal,
)


def test_ruby_marshal_primitives():
    # nil, true, false
    assert load_marshal(dump_marshal(None)) is None
    assert load_marshal(dump_marshal(True)) is True
    assert load_marshal(dump_marshal(False)) is False

    # Fixnums
    for num in [
        0,
        1,
        42,
        122,
        123,
        255,
        256,
        1000,
        65535,
        1000000,
        -1,
        -5,
        -42,
        -123,
        -256,
        -10000,
    ]:
        dumped = dump_marshal(num)
        loaded = load_marshal(dumped)
        assert loaded == num

    # Float
    flt = 3.14159
    assert abs(load_marshal(dump_marshal(flt)) - flt) < 1e-5

    # Bignum
    bignum = 123456789012345678901234567890
    assert load_marshal(dump_marshal(bignum)) == bignum
    assert load_marshal(dump_marshal(-bignum)) == -bignum


def test_ruby_marshal_symbols():
    sym1 = RubySymbol("name")
    sym2 = RubySymbol("description")
    arr = [sym1, sym2, sym1]  # Repeated symbol should use symbol link ';'
    dumped = dump_marshal(arr)
    loaded = load_marshal(dumped)
    assert len(loaded) == 3
    assert loaded[0] == "name"
    assert loaded[1] == "description"
    assert loaded[2] == "name"
    # Ensure ';' is in dumped bytes for repeated symbol
    assert b";" in dumped


def test_ruby_marshal_japanese_strings():
    jp_texts = [
        "勇者ハロルド",  # Kanji + Katakana
        "ポーションを使いました！",  # Hiragana + Katakana + Kanji + Full-width exclamation
        "「こんにちは、世界！」",  # Full-width quotes
        "『伝説の剣』〜古代の秘宝〜",  # Double brackets and full-width tilde
        "テスト・メッセージ？",  # Middle dot and full-width question mark
    ]
    for text in jp_texts:
        rs = RubyString(text.encode("utf-8"), encoding="utf-8")
        dumped = dump_marshal(rs)
        loaded = load_marshal(dumped)
        assert isinstance(loaded, RubyString)
        assert loaded.text == text
        assert loaded == text

    # Raw python string serialized automatically
    dumped_str = dump_marshal("日本語のテキスト")
    loaded_str = load_marshal(dumped_str)
    assert loaded_str.text == "日本語のテキスト"


def test_ruby_marshal_containers():
    data = {
        "title": "RPG Adventure",
        "scores": [10, 20, 30],
        "nested": {"key": "val", "list": [True, False, None]},
    }
    dumped = dump_marshal(data)
    loaded = load_marshal(dumped)
    assert loaded["title"] == "RPG Adventure"
    assert loaded["scores"] == [10, 20, 30]
    assert loaded["nested"]["key"] == "val"
    assert loaded["nested"]["list"] == [True, False, None]


def test_ruby_marshal_ruby_objects():
    # Simulating RPG::Actor
    actor = RubyObject("RPG::Actor")
    actor.set("id", 1)
    actor.set("name", "ハロルド")
    actor.set("nickname", "勇者")
    actor.set("profile", "伝説の剣士。")

    dumped = dump_marshal(actor)
    loaded = load_marshal(dumped)
    assert isinstance(loaded, RubyObject)
    assert loaded.class_name == "RPG::Actor"
    assert loaded.get("id") == 1
    assert loaded.get("name") == "ハロルド"
    assert loaded.get("nickname") == "勇者"
    assert loaded.get("profile") == "伝説の剣士。"

    # Test modification
    loaded.set("name", "Harold")
    re_dumped = dump_marshal(loaded)
    re_loaded = load_marshal(re_dumped)
    assert re_loaded.get("name") == "Harold"


def test_ruby_marshal_user_defined_and_special_classes():
    # UserDefined ('u') like Table
    table_data = b"\x03\x00\x00\x00" + b"\x01" * 16
    ud = RubyUserDefined("Table", table_data)
    dumped = dump_marshal(ud)
    loaded = load_marshal(dumped)
    assert isinstance(loaded, RubyUserDefined)
    assert loaded.class_name == "Table"
    assert loaded.data == table_data

    # UserMarshal ('U')
    um = RubyUserMarshal("CustomClass", [1, 2, 3])
    dumped_um = dump_marshal(um)
    loaded_um = load_marshal(dumped_um)
    assert isinstance(loaded_um, RubyUserMarshal)
    assert loaded_um.class_name == "CustomClass"
    assert loaded_um.value == [1, 2, 3]

    # UserClass ('C')
    uc = RubyUserClass("SpecialArray", ["a", "b"])
    dumped_uc = dump_marshal(uc)
    loaded_uc = load_marshal(dumped_uc)
    assert isinstance(loaded_uc, RubyUserClass)
    assert loaded_uc.class_name == "SpecialArray"


def test_ruby_marshal_object_links():
    # Repeated object reference should emit '@' object link
    obj = RubyObject("Node")
    obj.set("val", 100)
    arr = [obj, obj]
    dumped = dump_marshal(arr)
    assert b"@" in dumped

    loaded = load_marshal(dumped)
    assert loaded[0] is loaded[1]
    assert loaded[0].get("val") == 100


def test_ruby_marshal_safety_and_bounds():
    # Invalid header
    with pytest.raises(RubyMarshalError, match="Invalid Ruby Marshal header"):
        load_marshal(b"\x00\x00invalid")

    # Truncated data
    with pytest.raises(RubyMarshalError, match="Unexpected end of stream"):
        load_marshal(b"\x04\x08[")

    # Excess container size rejection
    # Byte 0x5b is array, Fixnum 10000000 exceeds MAX_CONTAINER_SIZE
    fake_huge_array = b"\x04\x08[\x04\x80\x96\x98\x00"
    with pytest.raises(RubyMarshalError, match="exceeds maximum bounds"):
        load_marshal(fake_huge_array)


def test_ruby_marshal_locator_resolution_and_application():
    from gamelingo.adapters.formats.ruby_marshal import (
        apply_ruby_locator,
        resolve_ruby_locator,
    )

    # Test database array locator
    actor = RubyObject("RPG::Actor")
    actor.set("name", "勇者")
    actor.set("profile", "伝説の戦士")
    actors = [None, actor]

    assert resolve_ruby_locator(actors, "[1].name") == "勇者"
    assert resolve_ruby_locator(actors, "[1].profile") == "伝説の戦士"

    apply_ruby_locator(actors, "[1].name", "Hero")
    assert resolve_ruby_locator(actors, "[1].name") == "Hero"

    # Test event commands locator (choices & show text)
    cmd_text = RubyObject("RPG::EventCommand")
    cmd_text.set("code", 401)
    cmd_text.set("parameters", [RubyString("こんにちは！".encode("utf-8"))])

    cmd_choices = RubyObject("RPG::EventCommand")
    cmd_choices.set("code", 102)
    cmd_choices.set(
        "parameters",
        [[RubyString("はい".encode("utf-8")), RubyString("いいえ".encode("utf-8"))], 1],
    )

    event = RubyObject("RPG::Event")
    page = RubyObject("RPG::Event::Page")
    page.set("list", [cmd_text, cmd_choices])
    event.set("pages", [page])
    event_map = {1: event}
    map_data = RubyObject("RPG::Map")
    map_data.set("events", event_map)

    assert (
        resolve_ruby_locator(map_data, "events[1].pages[0].list[0]") == "こんにちは！"
    )
    assert (
        resolve_ruby_locator(map_data, "events[1].pages[0].list[1].choices[0]")
        == "はい"
    )
    assert (
        resolve_ruby_locator(map_data, "events[1].pages[0].list[1].choices[1]")
        == "いいえ"
    )

    apply_ruby_locator(map_data, "events[1].pages[0].list[0]", "Hello!")
    apply_ruby_locator(map_data, "events[1].pages[0].list[1].choices[0]", "Yes")
    apply_ruby_locator(map_data, "events[1].pages[0].list[1].choices[1]", "No")

    assert resolve_ruby_locator(map_data, "events[1].pages[0].list[0]") == "Hello!"
    assert (
        resolve_ruby_locator(map_data, "events[1].pages[0].list[1].choices[0]") == "Yes"
    )
    assert (
        resolve_ruby_locator(map_data, "events[1].pages[0].list[1].choices[1]") == "No"
    )
