from fastcrud import FastCRUD
from .token_blacklist import (
    TokenBlacklist,
    TokenBlacklistCreate,
    TokenBlacklistUpdate,
    TokenBlacklistRead
)

CRUDTokenBlacklist = FastCRUD[
    TokenBlacklist,           # Model
    TokenBlacklistCreate,     # Create schema
    TokenBlacklistUpdate,     # Update schema
    TokenBlacklistUpdate,     # UpdateInternal schema
    TokenBlacklistUpdate,     # Delete schema
    TokenBlacklistRead,       # Read schema
]

crud_token_blacklist = CRUDTokenBlacklist(TokenBlacklist)