config = {
    "json_example": {},  # To generate json schema
    "model_location_package": "main.model",  # Change this to some where pydantic/dataclass model will be generated in.
    # Function returns object of desired type and a string representing the function call itself for replay, like:
    # "called_fn(arg1, arg2,.... kwarg1="...", kwarg2="...")"
    # One return type will be the model generated above. Once the type is generated, along
    # side will need to be
    #
    # TODO: Support user generated types with a plugin model.
    "function_for_ai_response": lambda message_node: None,  # passed through to aidriver.
    # If the events flag is set then the function is attached to the user message to AI
    # I can probably have a library wrapper to do this.
    # If the interrogation flag is attached.
    "apply_function_call_to": ["event", "interrogation"],
    # explicit auto or none.
    "function_call_mode": {"event": "explicit", "interrogation": "auto"},
    # The interrogation class is set up with this flag and the function.
    "interrogation_class": "InterrogationClass reference",
}

# 1: Use a json example/schema to generate a pydantic model of type T using https://github.com/koxudaxi/datamodel-code-generator/
# 1.2: How to put the generated model in a module?
# When using as a script(python -m drop.generate) I can consume a project location or dir.
# 1.3. Code gen: Use model_create call that will create an instance of EventNode with the type T. This new type will be in a module, along with a factory thing to
#       create the EventNode object from the type T.
#       This will be used by AIDriver to generate the EventNode object subtype.
#
# 1.4: Support for passing fn call signature to OpenAI:
#   A function that will use the JSONSchema to return Tuple[OpenAIFunctionCallSpec,  Union[UserExplicitFunctionCall, UserFunctionCallMode]
#   Test: OpenAIFunctionCallParameters will need to have one of the fields 'items' or 'properties' set, but not both.
# when OpenAIFunctionCallParameters does not support the outer type to be array.
# 1.5: Code gen a function like call_ai_generated_function_for_event that creates an abstract "call" function that accepts ai_message: MessageNode
#       and calls a function that can accept AIFunctionCall type containing what the AI sent back.

#   Interesting ideas: Once I have the pydantic model I could event use it customize the model:
#       - Have validation on specific fields: https://docs.pydantic.dev/latest/concepts/json_schema/#schema-customization
#       - What if user's API returns arbitrary json/xml objects? Assuming they can't be stored for whatever reason, could we still generate model, function on the fly?

PRIME_EVENT_EXAMPLE = """{
"name": "The Laugh Tour Comedy Club at Dorrian’s Red Hand",
"description": "The Laugh Tour Comedy Club located inside Dorrian’s Red Hand has four shows this weekend. All shows are hosted by comedian Rich Kiamco and will feature comedians from Nickelodeon, Colbert, Gas Digital, MTV, Showtime, America’s Got Talent, iTunes, Tru TV, and Boston Comedy Festival. Show tickets $25 for all shows plus a 2 item minimum per person (food or drink with 20% gratuity automatically added).",
"categories": ["Comedy club"], 
"addresses": ["555 Washington Boulevard, Jersey City"], 
"is_ongoing": false, 
"start_date": ["2023-09-01", "2023-09-02"],
"end_date": ["2023-09-01", "2023-09-02"], 
"start_time": ["19:30", "21:45", "18:30", "21:00"], 
"end_time": ["19:30", "21:45", "18:30", "21:00"], 
"is_paid": true,
"has_promotion": true, 
"promotion_details": "You can receive 15% off your ticket by using the code HOBOKENGIRL when u go to the counter.", 
"payment_mode": "ticket", 
"payment_details": "https://bit.ly/HOB-GIRL-LAUGHTOUR", 
"links": ["https://bit.ly/HOB-GIRL-LAUGHTOUR", "https://dorrians-jc.com/",
"https://www.instagram.com/thelaughtour_/"]
}
"""
# Couple of interesting things happened
# 1. I changed Event to BaseModel type and assignment of values from AI response was erronous.
# This means I either want to relax the validation or iterate on fixing the definition. Another option is
# log and deal with it later.
import functools

# from ..model.types import Event
# print(json.dumps(Event.model_json_schema(), indent=2))
import importlib

# A thought: A json can map to map to one or more valid schemas.
# But is it better to start instead with a dataclass and generate a jsonschema?
# I think so, because the dataclass will be more expressive and I can use that to generate the jsonschema.
#
import json
import re
from pathlib import Path
from types import ModuleType

# 1 lets use JSONSchema to generate the scheam from above

# define the name description, categories, is_ongoing(boolean), is_paid(boolean), has_promotion(boolean) as required.
# everything else can be the type or null.
# Enum types: payment_mode,
# There is also validation one can do for the python type using, for example, pydantic. Why not use that?


############################################################################################


def generate_function_call_param_function(
    type_name: str,
    schema_module_prefix: str,
):
    # Convert type name to module name
    # Convert type name to module name
    module_name = camel_to_snake(type_name)

    # Dynamically import the schema function
    schema_module = importlib.import_module(
        f"{schema_module_prefix}.{module_name}_schema"
    )
    schema_function_name = f"{module_name}_json_schema"

    # Define the function body for the function call param function
    func_code = f"""
# Generated code. Don't change this file unless you know what you are doing.
import json
from typing import Tuple

from drop_backend.model.ai_conv_types import (
    OpenAIFunctionCallSpec, UserExplicitFunctionCall
)

def {module_name}_function_call_param() -> Tuple[OpenAIFunctionCallSpec, UserExplicitFunctionCall]:
    json_schema_{module_name} = {schema_function_name}()
    print('.')
    params = {{"parameters": json.loads(json_schema_{module_name})}}
    return (
        [
            OpenAIFunctionCallSpec(
                name= "create_{module_name}",
                description = "Parse the data into a {type_name} object",
                **params,
            )
        ],
        UserExplicitFunctionCall(name="create_{module_name}"),
    )
"""

    # Compile the function code

    schema_file_path = Path(schema_module.__file__)
    with schema_file_path.open("a") as f:
        f.write(func_code)

    # Reload the schema module to include the new function
    return importlib.reload(schema_module)


def gen_schema(
    type_name: str,
    schema_directory_prefix: str,
    type_module_prefix: str,
) -> ModuleType:
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
    schema_module = importlib.import_module(path_to_module(schema_file_path))
    schema_module_prefix = schema_module.__name__[
        : schema_module.__name__.rfind(".")
    ]
    return schema_module, schema_module_prefix


import os


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
    json_schema_str = json.dumps(type_class.model_json_schema(), indent=2)

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
            current_schema = type_class.model_json_schema()

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
