"""
How "For you" weighs a story (src/services/news_map/for_you.py;
docs/decisions/news-map.md, "For you").

Reasoned, not fitted: there is no labelled set of what a reader wanted
to fit them against. Each part is in [0, 1]; the weights sum to 1 (a
test), so a score is in [0, 1] and the parts shown beside a story add up
to it. A reader's "not interested" scales one part down for them alone
(NOT_INTERESTED_STEP, never below NOT_INTERESTED_FLOOR), and the weights
are renormalised so they still sum to 1.
"""

FOR_YOU_WEIGHTS: dict[str, float] = {
    # A followed topic: the story's confidence in it; a followed group: half.
    "topic": 0.35,
    # A followed name: 2 / (stories naming it), as /graph/related counts a
    # shared entity, summed and capped at 1.
    "entity": 0.25,
    # Nearness in meaning to the stories the reader saved.
    "nearness": 0.20,
    # Halving every FRESHNESS_HALF_LIFE_DAYS.
    "freshness": 0.20,
}

# A topic confidence this high counts in full; the classifier's run from
# ~0.35 to ~0.6 on the stories read so far (news-map.md, N1).
TOPIC_FULL_CONFIDENCE = 0.5

# How much a followed group counts against a followed topic.
GROUP_SHARE = 0.5

# bge-m3 cosine from which nearness starts counting (two random claims
# average 0.34, measured 29 Oct) and at which it is full.
NEARNESS_FROM = 0.35
NEARNESS_FULL = 0.80

FRESHNESS_HALF_LIFE_DAYS = 3.0

# In the first DIVERSITY_WINDOW stories, at most this many from one topic:
# more for a topic the reader follows ("mostly what you follow"), few for
# any other ("but not only").
DIVERSITY_WINDOW = 10
MAX_FROM_A_FOLLOWED_TOPIC = 7
MAX_FROM_ANOTHER_TOPIC = 3

# Two stories from one outlet within this many seconds: only the better.
SAME_OUTLET_SECONDS = 3600

NOT_INTERESTED_STEP = 0.8
NOT_INTERESTED_FLOOR = 0.25
