"""
Which outlet a domain belongs to, for counting independent sources.

The verifier takes the side more outlets take, the scorer counts independent
domains, and the funnel keeps one page per domain, so "how many outlets" is
a figure verdicts rest on. It used to be the host: `en.wikipedia.org` and
`es.wikipedia.org` were two sources, `bbc.com` and `bbc.co.uk` two, and an
article from `edition.cnn.com` could be backed by `cnn.com` as if by someone
else (trends/angles.py, audit 2026-10-28 N7).

Not used for the reliability ratings, which are held per host. And the host
stays what is displayed: this only decides what counts as the same voice.

A short list rather than the public-suffix list: only the suffixes this
project's sources and their neighbours use, and a domain it does not know
keeps its last two labels. `abc.es` and `abc.net.au` stay two outlets, as
they should, because the whole registrable domain is compared.
"""

from urllib.parse import urlsplit

_TWO_LEVEL_SUFFIXES = frozenset({
    "co.uk", "org.uk", "ac.uk", "gov.uk", "me.uk",
    "com.au", "net.au", "org.au", "gov.au",
    "co.za", "org.za", "gov.za",
    "co.nz", "org.nz", "govt.nz",
    "com.es", "org.es", "gob.es", "edu.es",
    "com.mx", "org.mx", "gob.mx",
    "com.ar", "org.ar", "gob.ar",
    "com.br", "org.br", "gov.br",
    "com.co", "gov.co", "com.pe", "gob.pe", "com.ve", "gob.ve", "cl.cl",
    "co.in", "gov.in", "co.jp", "or.jp", "co.kr", "com.cn", "com.tr",
    "com.sg", "com.hk", "gov.jm", "com.jm",
})

# One newsroom, two registrable domains.
_ALIASES = {
    "bbc.co.uk": "bbc.com",
    "the-independent.com": "independent.co.uk",
    "reuters.co.uk": "reuters.com",
    "theguardian.co.uk": "theguardian.com",
    "guardian.co.uk": "theguardian.com",
    "nytimes.org": "nytimes.com",
    "elpais.es": "elpais.com",
}


def outlet_of(domain_or_url: str | None) -> str:
    """The registrable domain behind a host or URL, aliases resolved; "" for nothing."""

    value = (domain_or_url or "").strip().lower()

    if "//" in value:
        value = urlsplit(value).netloc

    value = value.split(":")[0].rstrip(".")

    labels = [label for label in value.split(".") if label]

    if len(labels) <= 2:
        registrable = ".".join(labels)
    elif ".".join(labels[-2:]) in _TWO_LEVEL_SUFFIXES:
        registrable = ".".join(labels[-3:])
    else:
        registrable = ".".join(labels[-2:])

    return _ALIASES.get(registrable, registrable)


def same_outlet(left: str | None, right: str | None) -> bool:

    return bool(left) and bool(right) and outlet_of(left) == outlet_of(right)
