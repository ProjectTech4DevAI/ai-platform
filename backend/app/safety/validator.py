from abc import ABC, abstractmethod

class Validator(ABC):
    def __init__(self) -> None:
        pass

    @abstractmethod
    def execute(cls, text: str):
        pass

    @abstractmethod
    def make(cls, validator_config):
        pass