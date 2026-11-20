"""Which service does this run send an article to for its names and places?

One address, one language and one deadline. `CLAUDE.md` Guardrail #11 says
article text goes only where the operator of the run sends it, and that the
destination is a committed config value rather than an environment one - an
environment value is the one kind of setting that moves with nobody reading a
diff.

The service is a sidecar the digest job starts on its own runner, so the address
is refused unless it names this machine. That is stricter than the model
server's address, which may name another box the operator controls: nothing
listens for this service anywhere else, and a value that moved article text off
the runner would otherwise be a diff a reader could miss rather than a schema
that refuses it.
"""

from __future__ import annotations

from typing import Annotated, Final, Self

from pydantic import Field, StringConstraints, model_validator

from idhazh.contracts.base import Model
from idhazh.contracts.knobs.model_server import is_loopback, resolve_base_url

#: The address the service's own committed listener binds
#: (`config/text-analysis/settings.json`, `listener`). A test holds the two together.
DEFAULT_BASE_URL: Final = "http://127.0.0.1:3020"

#: The knob's name as an operator reads it in a refusal.
BASE_URL_KNOB: Final = "text_analysis.base_url"

#: A bare lowercase language code, the key the service files its languages under.
#: The sidecar step reads it as a key, so it is a code that needs no quoting.
LanguageCode = Annotated[str, StringConstraints(pattern=r"^[a-z]{2,3}$")]


class TextAnalysisConfig(Model):
    """Where the text-analysis service listens, its language, and how long a call may take."""

    base_url: str = Field(
        default=DEFAULT_BASE_URL,
        description=(
            "Scheme, host and port of the text-analysis service, and nothing else; a "
            "trailing slash is dropped. The host must be this machine's loopback or "
            "`localhost`, because the digest job starts the service on the runner that "
            "calls it. The port is the one in `config/text-analysis/settings.json`. "
            "Committed rather than set from the environment, so moving where article "
            "text goes is a diff a person reads (CLAUDE.md Guardrail #11)."
        ),
    )
    language: LanguageCode = Field(
        default="en",
        description=(
            "The language every request asks the service to read, and the one the digest "
            "job installs a model for, so one value decides both. A bare lowercase code "
            "the service lists under `languages` in `config/text-analysis/settings.json`."
        ),
    )
    request_timeout_seconds: float = Field(
        default=15.0,
        gt=0.0,
        description=(
            "Seconds one analysis request may wait on the service before the item goes "
            "on without its names, and it bounds each wait of the exchange: connecting, "
            "sending, and the start of the reply. A service that holds a request open "
            "therefore costs one item about this much, so the busiest shard's 80 items "
            "cost at most 20 minutes rather than 80. The default is an estimate: about "
            "five times the 2.7 s a cold first request took on a hosted runner, which is "
            "the model loading; a warm request took about 16 ms. Raise it only after a "
            "run shows a healthy service answering later than this."
        ),
    )

    @model_validator(mode="after")
    def _the_address_is_this_machine(self) -> Self:
        self.base_url = resolve_base_url(self.base_url, BASE_URL_KNOB)
        if not is_loopback(self.base_url):
            raise ValueError(
                f"{BASE_URL_KNOB} must name this machine, a loopback address or localhost, "
                f"not {self.base_url!r}"
            )
        return self
