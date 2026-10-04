"""How does a ledger's CSV move onto the ledger door without losing a filled cell?

Each module answers one step of the move. This package, its command
`backend/utilities/migrate_to_parquet.py` and its tests are deleted when no
ledger a program writes is left on CSV.
"""
