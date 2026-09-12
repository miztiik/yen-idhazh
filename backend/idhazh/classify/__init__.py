"""What an article is about, read out of the article rather than declared for it.

A feed declares a vertical and a kind, and every item it carries inherits both
whatever the item says. The model that already reads the whole article for the
summary can answer those questions from the text instead, and this package is
where it asks.

`calls.py` holds the two calls that read one article. Later work adds one module
a label; nothing is stubbed ahead of the code that fills it (`CLAUDE.md` section
10). There is no package-level re-export, because every caller in this
repository imports the submodule it means and a second name for one thing is a
second place to keep correct.
"""
