#!/usr/bin/env python
# Copyright (c) Microsoft Corporation.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import inspect
import re
from types import FunctionType
from typing import Any, Optional, get_type_hints

from playwright._impl._helper import to_snake_case
from scripts.documentation_provider import DocumentationProvider
from scripts.generate_api import (
    Overload,
    all_types,
    api_globals,
    arguments,
    header,
    is_overload,
    process_type,
    return_type,
    return_value,
    short_name,
    signature,
)

documentation_provider = DocumentationProvider(True)


def generate(t: Any) -> None:
    print("")
    class_name = short_name(t)
    base_class = t.__bases__[0].__name__
    if class_name in ["Page", "BrowserContext", "Browser"]:
        base_sync_class = "AsyncContextManager"
    elif base_class in ["ChannelOwner", "object"]:
        base_sync_class = "AsyncBase"
    else:
        base_sync_class = base_class
    print(f"class {class_name}({base_sync_class}):")
    print("")
    print(f"    def __init__(self, obj: {class_name}Impl):")
    print("        super().__init__(obj)")
    for [name, type] in get_type_hints(t, api_globals).items():
        print("")
        print("    @property")
        print(f"    def {name}(self) -> {process_type(type)}:")
        documentation_provider.print_entry(class_name, name, {"return": type}, True)
        [prefix, suffix] = return_value(type)
        prefix = "        return " + prefix + f"self._impl_obj.{name}"
        print(f"{prefix}{suffix}")
    for [name, value] in t.__dict__.items():
        if name.startswith("_"):
            continue
        if str(value).startswith("<property"):
            value = value.fget
            print("")
            print("    @property")
            print(
                f"    def {name}({signature(value, len(name) + 9)}) -> {return_type(value)}:"
            )
            documentation_provider.print_entry(
                class_name, name, get_type_hints(value, api_globals), True
            )
            [prefix, suffix] = return_value(
                get_type_hints(value, api_globals)["return"]
            )
            prefix = "        return " + prefix + f"self._impl_obj.{name}"
            print(f"{prefix}{arguments(value, len(prefix))}{suffix}")
    for [name, value] in t.__dict__.items():
        overload: Optional[Overload] = None
        if is_overload(name):
            overload = Overload(t, name)
            overload.assert_has_implementation()
            name = overload.name
        if (
            not name.startswith("_")
            and isinstance(value, FunctionType)
            and "remove_listener" != name
        ):
            is_async = inspect.iscoroutinefunction(value)
            return_type_value = return_type(value)
            return_type_value = re.sub(r"\"([^\"]+)Impl\"", r"\1", return_type_value)
            return_type_value = return_type_value.replace(
                "EventContextManager", "AsyncEventContextManager"
            )
            print("")
            async_prefix = "async " if is_async else ""
            if overload is not None:
                print("    @typing.overload")
            print(
                f"    {async_prefix}def {name}({signature(value, len(name) + 9, overload is not None)}) -> {return_type_value}:"
            )
            if overload is None:
                documentation_provider.print_entry(
                    class_name, name, get_type_hints(value, api_globals)
                )
                if "expect_" in name:
                    print("")
                    print(
                        f"        return AsyncEventContextManager(self._impl_obj.{name}({arguments(value, 12)}).future)"
                    )
                else:
                    [prefix, suffix] = return_value(
                        get_type_hints(value, api_globals)["return"]
                    )
                    if is_async:
                        prefix += (
                            f'await self._async("{to_snake_case(class_name)}.{name}", '
                        )
                        suffix += ")"
                    prefix = prefix + f"self._impl_obj.{name}("
                    suffix = ")" + suffix
                    print(
                        f"""
        return {prefix}{arguments(value, len(prefix))}{suffix}"""
                    )
            else:
                print("        pass")
    if class_name == "Playwright":
        print(
            """
    def __getitem__(self, value: str) -> "BrowserType":
        if value == "chromium":
            return self.chromium
        elif value == "firefox":
            return self.firefox
        elif value == "webkit":
            return self.webkit
        raise ValueError("Invalid browser "+value)
            """
        )
    print("")
    print(f"mapping.register({class_name}Impl, {class_name})")


def main() -> None:
    print(header)
    print(
        "from playwright._impl._async_base import AsyncEventContextManager, AsyncBase, AsyncContextManager, mapping"
    )
    print("NoneType = type(None)")

    for t in all_types:
        generate(t)
    documentation_provider.print_remainder()


if __name__ == "__main__":  # pragma: no cover
    main()
