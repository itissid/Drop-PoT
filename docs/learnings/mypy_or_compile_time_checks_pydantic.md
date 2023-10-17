1. Pydantic needs a plugin for MyPy validation. There are some flags that can
control validation of initializaton of Pydantic models from, say, dictionaries.
These flags are set in the `mypy.ini` file:
```
init_forbid_extra = True
init_typed = True
```
2. One thing that is a bit odd is that mypy won't check your function code 
unless you annotate the function with return types: 
https://mypy.readthedocs.io/en/stable/common_issues.html#no-errors-reported-for-obviously-wrong-code

3. For types that are optional I have to set their values in the Model declaration explicitly to `None`:
```
class MyModel(BaseModel):
    my_optional: Optional[str] = None
```

4. Pydantic does not validate assignment to types you do after the object is
constructed, for example, say using dot attribute assignment. It works off of
Annotations and static metadata at creation time. The philosophy is that the
data is validated while loading, serializing, and deserializing but once the
data is in a pydantic object your code knows what to do with it. This is also a 
tradeoff
```
# ---------------- Example 1 -----------------------------------
class User(BaseModel):
    id: int
    name: str = 'John Doe'
    signup_ts: Optional[datetime] = None

m = User.model_validate({'id': 123, 'name': 'James'})
print(m)
#> id=123 name='James' signup_ts=None

try:
    User.model_validate(['not', 'a', 'dict'])
except ValidationError as e:
    print(e)
    """
    1 validation error for User
      Input should be a valid dictionary or instance of User [type=model_type, input_value=['not', 'a', 'dict'], input_type=list]
    """

# But this does not complain:
m.id = '123' # No checking done by pydantic and that ok, it is in line with its objectives and philosophy.
# ----------------- Example 2 -----------------------------
from annotated_types import Gt
from typing_extensions import Annotated

from pydantic import TypeAdapter, ValidationError

PositiveInt = Annotated[int, Gt(0)]

ta = TypeAdapter(PositiveInt)

print(ta.validate_python(1))

# --------------------------------------------------------

```