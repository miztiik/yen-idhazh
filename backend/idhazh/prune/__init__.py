"""Which module answers which prune question?

`one_at_a_time` is the core: how to delete the members of a collection one at a
time, safely, resumably, and under a ceiling. It knows nothing about what a
collection is made of.

`github_collections` is one driver for it: the workflow artifacts and workflow
runs GitHub holds on our behalf.

A second driver lives in `idhazh.telemetry.prune`, because that one's question
is an operator's ("which store, and which days?") rather than a transport's, and
it belongs beside the command an operator types.
"""
