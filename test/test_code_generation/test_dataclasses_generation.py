from typing import Dict, List

import pytest

from json_to_models.dynamic_typing import (DDict, DList, DOptional, DUnion, FloatString, IntString, ModelMeta,
                                           compile_imports)
from json_to_models.models import sort_fields
from json_to_models.models.base import METADATA_FIELD_NAME, generate_code
from json_to_models.models.dataclasses import (DataclassModelCodeGenerator, convert_strings,
                                               dataclass_post_init_converters)
from test.test_code_generation.test_models_code_generator import model_factory, trim


def field_meta(original_name):
    return f"metadata={{'{METADATA_FIELD_NAME}': '{original_name}'}}"


# Data structure:
# pytest.param id -> {
#   "model" -> (model_name, model_metadata),
#   test_name -> expected, ...
# }
test_data = {
    "base": {
        "model": ("Test", {
            "foo": int,
            "Bar": int,
            "baz": float
        }),
        "fields_data": {
            "foo": {
                "name": "foo",
                "type": "int"
            },
            "Bar": {
                "name": "bar",
                "type": "int",
                "body": f"field({field_meta('Bar')})"
            },
            "baz": {
                "name": "baz",
                "type": "float"
            }
        },
        "fields": {
            "imports": "",
            "fields": [
                f"foo: int",
                f"bar: int = field({field_meta('Bar')})",
                f"baz: float",
            ]
        },
        "generated": trim(f"""
        from dataclasses import dataclass, field


        @dataclass
        class Test:
            foo: int
            bar: int = field({field_meta('Bar')})
            baz: float
        """)
    },
    "complex": {
        "model": ("Test", {
            "foo": int,
            "baz": DOptional(DList(DList(str))),
            "bar": DOptional(IntString),
            "qwerty": FloatString,
            "asdfg": DOptional(int),
            "dict": DDict(int)
        }),
        "fields_data": {
            "foo": {
                "name": "foo",
                "type": "int"
            },
            "baz": {
                "name": "baz",
                "type": "Optional[List[List[str]]]",
                "body": f"field(default_factory=list)"
            },
            "bar": {
                "name": "bar",
                "type": "Optional[IntString]",
                "body": "None"
            },
            "qwerty": {
                "name": "qwerty",
                "type": "FloatString"
            },
            "asdfg": {
                "name": "asdfg",
                "type": "Optional[int]",
                "body": "None"
            },
            "dict": {
                "name": "dict",
                "type": "Dict[str, int]"
            }
        },
        "generated": trim("""
        from dataclasses import dataclass, field
        from json_to_models.dynamic_typing import FloatString, IntString
        from json_to_models.models.dataclasses import convert_strings
        from typing import Dict, List, Optional


        @dataclass
        @convert_strings(['bar#U.S', 'qwerty'])
        class Test:
            foo: int
            qwerty: FloatString
            dict: Dict[str, int]
            baz: Optional[List[List[str]]] = field(default_factory=list)
            bar: Optional[IntString] = None
            asdfg: Optional[int] = None
        """)
    },
    "converters": {
        "model": ("Test", {
            "a": int,
            "b": IntString,
            "c": DOptional(FloatString),
            "d": DList(DList(DList(IntString))),
            "e": DDict(IntString),
            "u": DUnion(DDict(IntString), DList(DList(IntString))),
        }),
        "generated": trim("""
        from dataclasses import dataclass, field
        from json_to_models.dynamic_typing import FloatString, IntString
        from json_to_models.models.dataclasses import convert_strings
        from typing import Dict, List, Optional, Union


        @dataclass
        @convert_strings(['b', 'c#U.S', 'd#L.L.L.S', 'e#D.S'])
        class Test:
            a: int
            b: IntString
            d: List[List[List[IntString]]]
            e: Dict[str, IntString]
            u: Union[Dict[str, IntString], List[List[IntString]]]
            c: Optional[FloatString] = None
        """)
    }
}

test_data_unzip = {
    test: [
        pytest.param(
            model_factory(*data["model"]),
            data[test],
            id=id
        )
        for id, data in test_data.items()
        if test in data
    ]
    for test in ("fields_data", "fields", "generated")
}


@pytest.mark.parametrize("value,expected", test_data_unzip["fields_data"])
def test_fields_data_dc(value: ModelMeta, expected: Dict[str, dict]):
    gen = DataclassModelCodeGenerator(value, meta=True)
    required, optional = sort_fields(value)
    for is_optional, fields in enumerate((required, optional)):
        for field in fields:
            field_imports, data = gen.field_data(field, value.type[field], bool(is_optional))
            assert data == expected[field]


@pytest.mark.parametrize("value,expected", test_data_unzip["fields"])
def test_fields_dc(value: ModelMeta, expected: dict):
    expected_imports: str = expected["imports"]
    expected_fields: List[str] = expected["fields"]
    gen = DataclassModelCodeGenerator(value, meta=True)
    imports, fields = gen.fields
    imports = compile_imports(imports)
    assert imports == expected_imports
    assert fields == expected_fields


@pytest.mark.parametrize("value,expected", test_data_unzip["generated"])
def test_generated_dc(value: ModelMeta, expected: str):
    generated = generate_code(
        ([{"model": value, "nested": []}], {}),
        DataclassModelCodeGenerator,
        class_generator_kwargs={'meta': True, 'post_init_converters': True}
    )
    assert generated.rstrip() == expected, generated


def test_dataclass_post_init_converters():
    from dataclasses import dataclass

    @dataclass
    class A:
        x: IntString
        y: FloatString

        __post_init__ = dataclass_post_init_converters(['x', 'y'])

    a = A('1', '1.1')
    assert type(a.x) is IntString
    assert type(a.y) is FloatString


def test_convert_strings_decorator():
    from dataclasses import dataclass

    @dataclass
    @convert_strings(['x', 'y'])
    class A:
        x: IntString
        y: FloatString

    @dataclass
    @convert_strings(['x', 'y'])
    class B:
        x: IntString
        y: FloatString

        def __post_init__(self):
            self.x *= 2

    a = A('1', '1.1')
    b = B('1', '1.1')
    assert type(a.x) is IntString
    assert type(a.y) is FloatString
    assert b.x == 2
