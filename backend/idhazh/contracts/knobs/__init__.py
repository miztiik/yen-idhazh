"""One module a block of `config/idhazh.json`, so a change to one loads one file.

`idhazh.contracts.app_config` holds the aggregate that names these and the
validators that read two blocks at once. Nothing here imports it, so a block can
be read without loading every other block's prose.
"""
