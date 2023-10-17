from abc import ABC, abstractmethod, abstractclassmethod


class CreatorBase(ABC):
    """Marker interface for pydantic models to be created from kwargs by calling a supported function.
    Its main use is for better typing in EventManager.
    """
    @abstractclassmethod
    def create(cls, function_name:str, **kwargs) -> 'CreatorBase':
        ...

    @abstractclassmethod
    def default_fn_name(cls) -> str:
        ...
