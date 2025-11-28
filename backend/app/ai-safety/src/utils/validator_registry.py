from ..validators.piiremover import PIIRemover
from ..validators.lexicalslur import LexicalSlur

VALIDATOR_REGISTRY = {
    "pii_remover": PIIRemover,
    "lexical_slur": LexicalSlur,
}