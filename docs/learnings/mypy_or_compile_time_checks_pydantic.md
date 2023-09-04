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
