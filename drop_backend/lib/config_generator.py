# 1: Use a json example/schema to generate a pydantic model of type T using
#    https://github.com/koxudaxi/datamodel-code-generator/
# 1.2: How to put the generated model in a module?
# When using as a script(python -m drop.generate) I can consume a project location or dir.
# 1.3. Code gen: Use model_create call that will create an instance of EventNode
#       with the type T. This new type will be in a module, along with a factory thing to:
#       create the EventNode object from the type T.
#       This will be used by AIDriver to generate the EventNode object subtype.
#
# 1.4: Support for passing fn call signature to OpenAI:
#   A function that will use the JSONSchema to return
#   Tuple[OpenAIFunctionCallSpec,  Union[UserExplicitFunctionCall,
#   UserFunctionCallMode] Test: OpenAIFunctionCallParameters will need to have
#   one of the fields 'items' or 'properties' set, but not both.
# when OpenAIFunctionCallParameters does not support the outer type to be array.
# 1.5: Code gen a function like call_ai_generated_function_for_event that
#      creates an abstract "call" function that accepts ai_message: MessageNode and
#      calls a function that can accept AIFunctionCall type containing what the AI
#      sent back.

#   Interesting ideas: Once I have the pydantic model I could event use it customize the model:
#       - Have validation on specific fields:
#       https://docs.pydantic.dev/latest/concepts/json_schema/#schema-customization
#       - What if user's API returns arbitrary json/xml objects? Assuming they
#       can't be stored for whatever reason, could we still generate model,
#       function on the fly?


# Couple of interesting things happened
# 1. I changed Event to BaseModel type and assignment of values from AI response was erronous.
# This means I either want to relax the validation or iterate on fixing the
# definition. Another option is log and deal with it later.
# A thought: A json can map to map to one or more valid schemas.
# But is it better to start instead with a dataclass and generate a jsonschema?
# I think so, because the dataclass will be more expressive and I can use that
# to generate the jsonschema.
import functools
import importlib
import json
import os
import re
from pathlib import Path
from types import ModuleType
from typing import Tuple

from ..types.base import CreatorBase

from ..types.base import CreatorBase

# 1 lets use JSONSchema to generate the scheam from above

# define the name description, categories, is_ongoing(boolean), is_paid(boolean), has_promotion(boolean) as required.
# everything else can be the type or null.
# Enum types: payment_mode,
# There is also validation one can do for the python type using, for example, pydantic. Why not use that?


############################################################################################


def generate_function_call_param_function(
    type_name: str,
    schema_module_prefix: str,
    type_module_prefix: str,
):
    # Convert type name to module name
    # Convert type name to module name
    type_module_name = camel_to_snake(type_name)
    type_module_instance = importlib.import_module(
        f"{type_module_prefix}.{type_module_name}"
    )
    type_class = getattr(type_module_instance, type_name)
    assert (
        CreatorBase in type_class.__mro__
    ), f"Type {type_name} must inherit from CreatorBase"
    # Dynamically import the schema function
    schema_module = importlib.import_module(
        f"{schema_module_prefix}.{type_module_name}_schema"
    )
    schema_function_name = f"{type_module_name}_json_schema"
    default_fn_name = type_class.default_fn_name()
    assert default_fn_name is not None
    # Define the function body for the function call param function
    func_code = f"""
# Generated code. Don't change this file unless you know what you are doing.
import json
from typing import Tuple, List


from drop_backend.model.ai_conv_types import (
    OpenAIFunctionCallSpec, UserExplicitFunctionCall
)

def {type_module_name}_function_call_param() -> Tuple[List[OpenAIFunctionCallSpec], UserExplicitFunctionCall]:
    json_schema_{type_module_name} = {schema_function_name}()
    params = {{"parameters": json.loads(json_schema_{type_module_name})}}
    return (
        [
            OpenAIFunctionCallSpec(
                name= "{default_fn_name}",
                description = "Parse the data into a {type_name} object",
                **params,
            )
        ],
        # TODO: Also support "auto" and "none"
        UserExplicitFunctionCall(name="{default_fn_name}"),
    )
"""

    # Compile the function code
    assert schema_module.__file__ is not None
    schema_file_path = Path(schema_module.__file__)
    with schema_file_path.open("a", encoding="utf-8") as f:
        f.write(func_code)

    # Reload the schema module to include the new function
    return importlib.reload(schema_module)


def gen_schema(
    type_name: str,
    schema_directory_prefix: str,
    type_module_prefix: str,
) -> Tuple[ModuleType, str]:
    """
    type_name: The name of the pydantic type to generate the schema for.
    schema_directory_prefix: The directory where the schema will be written.
    type_module_prefix: The module prefix where the python module that returns the schema is returned as a json string.
    """
    json_schema = generate_json_schema(
        type_module_prefix,
        type_name,
    )

    # Write the function to a new file
    # TODO: for external project we need to change main.lib.config_generator to
    # this project's dirs.
    schema_code = f"""
# Generated code. Don't change this file unless you know what you are doing.
from drop_backend.lib.config_generator import validate_schema

@validate_schema("{type_name}", "{type_module_prefix}")
def {camel_to_snake(type_name)}_json_schema():
    return \"\"\"{json_schema}\"\"\"
    """

    schema_directory = Path(schema_directory_prefix)
    schema_file_path = (
        schema_directory / f"{camel_to_snake(type_name)}_schema.py"
    )
    with schema_file_path.open("w") as f:
        f.write(schema_code)
    schema_module = importlib.import_module(
        path_to_module(str(schema_file_path))
    )
    schema_module_prefix = schema_module.__name__[
        : schema_module.__name__.rfind(".")
    ]
    return schema_module, schema_module_prefix


def path_to_module(path: str) -> str:
    # Remove file extension if present
    base, _ = os.path.splitext(path)
    # Convert path separators to dots
    return base.replace(os.sep, ".")


def camel_to_snake(name: str) -> str:
    """Convert CamelCase to snake_case."""
    s1 = re.sub("(.)([A-Z][a-z]+)", r"\1_\2", name)
    return re.sub("([a-z0-9])([A-Z])", r"\1_\2", s1).lower()


def generate_json_schema(module_prefix: str, type_name: str):
    # Dynamically import the module
    module_name = camel_to_snake(type_name)
    type_module = importlib.import_module(f"{module_prefix}.{module_name}")
    type_class = getattr(type_module, type_name)
    json_schema_str = json.dumps(
        # Use alias only in validation of incoming data: https://docs.pydantic.dev/latest/concepts/fields/#field-aliases
        type_class.model_json_schema(by_alias=False),
        indent=2,
    )

    return json_schema_str


class SchemaHasChanged(ValueError):
    pass


#############Validation functions #############
def validate_schema(type_name: str, type_module_prefix: str):
    """Decorator to validate the JSON schema against the model's schema."""

    def _deco(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # Call the original function to get the stored schema
            stored_schema = json.loads(func(*args, **kwargs))

            # Dynamically get the type's module and class.
            # FIXME: this is brittle to change in naming convention.
            module_name = camel_to_snake(type_name)
            type_module = importlib.import_module(
                f"{type_module_prefix}.{module_name}"
            )
            type_class = getattr(type_module, type_name)

            # Generate the current schema from the model
            current_schema = type_class.model_json_schema(by_alias=False)

            # Compare the stored schema with the current schema
            if stored_schema != current_schema:
                raise SchemaHasChanged(
                    f"The schema for {type_name} has changed!"
                )

            return json.dumps(stored_schema)

        return wrapper

    return _deco


def check_should_update_schema(
    type_name: str,
    schema_directory_prefix: str,
    type_module_prefix: str,
) -> bool:
    module_name = camel_to_snake(type_name)
    schema_file_path = (
        Path(schema_directory_prefix) / f"{module_name}_schema.py"
    )

    # Check if the schema file already exists
    if schema_file_path.exists():
        # Dynamically import the existing schema function
        schema_module = importlib.import_module(
            f"{type_module_prefix}.schema.{module_name}_schema"
        )
        existing_schema_function = getattr(
            schema_module, f"{module_name}_json_schema"
        )
        try:
            json.loads(existing_schema_function())
        except SchemaHasChanged:
            # Ask the user if they want to regenerate the schema
            choice = input(
                f"The schema for {type_name} has changed. Do you want to regenerate it? (yes/no): "
            )
            if choice.lower() == "yes":
                return True
            else:
                return False
    return True
