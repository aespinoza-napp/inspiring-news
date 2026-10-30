# Trend signals

One YAML per signal, loaded by `src/repositories/trend_signal_repository.py`
into `src/models/core/trend_signal.py`'s `TrendSignal`. A signal is a public
feed that says what is spreading right now - not a news source: it is never
evidence and is not rated. Why, and what each one gave on 2026-10-26:
`docs/decisions/trends.md`.

```yaml
id: google_trends_es          # unique
name: Google Trends · Spain
kind: google_trends           # google_trends | ranked_feed
url: https://trends.google.com/trending/rss?geo=ES
language: es                  # one with a lexicon: en or es
country: ES                   # optional, Google's geo
positive: false               # its items are chosen for being good news (never read by the Devastating edition)
devastating: false            # its items lean to bad news: read only by the Devastating edition
enabled: true
```

**Free by rule.** A signal is a public feed read with no key and no login.
A route that needs a card, a subscription or an application is not added
(docs/goals.md, "Trends"). TikTok is not a signal: its listing needs a
signed session and its terms forbid scraping. It reaches the system as a
hashtag or link a person types on /discover.
