from abc import ABC, abstractmethod, abstractclassmethod


class CreatorBase(ABC):
    """Marker interface for pydantic models to be created from kwargs.
    Its main use is for better typing in EventManager.
    """
    @abstractclassmethod
    def create(cls, **kwargs):
        ...
