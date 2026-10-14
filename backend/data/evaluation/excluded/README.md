# Facts left out of the custom set: off-mission articles

The custom set is meant to hold the claims this pipeline would check: the
claims of constructive news on our topics. Before the mission screen
(Oct 6, widened Oct 9) and the topic check on the labelling batch (Oct 14),
the daily batch also drew party politics, war, crime, sport, a product
review, a puzzle and a roundup. Their facts were labelled correctly but
are outside the set's domain, so they are kept here rather than deleted.
The harness, the labeller and the graph sync read `manual/` only.

**Rule, applied on 2026-10-14, one decision per article, from its headline:**
an article is left out when its subject is one of the mission screen's
off-mission kinds (`OFF_MISSION` in
`backend/src/services/selection/mission_screen.py`: politics, labour
disputes and protests, crime, accidents and disasters, war and conflict,
celebrity, sport, markets, service pages) or its page is one of the
screen's non-article formats (`FORMATS`: podcast, roundup, quiz, gallery,
advisory, promotion, shopping). The same criteria the pipeline uses to
keep a story out, so the set and the system agree on what is in scope.

**Kept, deliberately:** epidemics (the Ebola and dengue articles) are
`public_health`, one of our topics, not a disaster story; music
interviews (Judeline, Paco Pastor) are culture, not celebrity gossip; the
Bird Photographer of the Year page had article text, so it is not a
gallery-only page; the winery director interview fits no off-mission kind.

39 facts (6 human, 33 AI) from 17 articles; 148 → 109 in `manual/`.
To bring one back: `git mv excluded/factNNN.json manual/`. The labeller
numbers new facts past these as well, so no number is reused.

| Fact | Kind | Label | Labelled by | Article |
|---|---|---|---|---|
| fact022 | politics | TRUE | human | BBC paying to air shows like Suits and Schitt's Creek is illogical, MPs say |
| fact023 | politics | TRUE | human | BBC paying to air shows like Suits and Schitt's Creek is illogical, MPs say |
| fact136 | politics | TRUE | AI | BBC paying to air shows like Suits and Schitt's Creek is illogical, MPs say |
| fact026 | crime | TRUE | human | At Least 124 Environmental Defenders Killed Worldwide Last Year |
| fact027 | crime | TRUE | human | At Least 124 Environmental Defenders Killed Worldwide Last Year |
| fact032 | politics | TRUE | human | DPR Korea tells UN its nuclear status is 'irreversible', rejects outside pressure |
| fact033 | politics | TRUE | human | DPR Korea tells UN its nuclear status is 'irreversible', rejects outside pressure |
| fact137 | politics | UNVERIFIED | AI | DPR Korea tells UN its nuclear status is 'irreversible', rejects outside pressure |
| fact039 | politics | TRUE | AI | Brasil en cifras: ¿qué economía recibe el próximo presidente? |
| fact040 | politics | TRUE | AI | Brasil en cifras: ¿qué economía recibe el próximo presidente? |
| fact041 | politics | TRUE | AI | Brasil en cifras: ¿qué economía recibe el próximo presidente? |
| fact042 | shopping | TRUE | AI | Del IPS al OLED con el monitor Samsung Odyssey OLED G8 de 32 pulgadas |
| fact043 | shopping | UNVERIFIED | AI | Del IPS al OLED con el monitor Samsung Odyssey OLED G8 de 32 pulgadas |
| fact044 | shopping | TRUE | AI | Del IPS al OLED con el monitor Samsung Odyssey OLED G8 de 32 pulgadas |
| fact051 | crime | TRUE | AI | 'Potential crime' probe into death of Scots wingsuit flyer dropped |
| fact059 | politics | TRUE | AI | Artist 'taking legal advice' over Tories' use of Andy Burnham portrait |
| fact060 | politics | TRUE | AI | Artist 'taking legal advice' over Tories' use of Andy Burnham portrait |
| fact061 | politics | PARTIALLY_TRUE | AI | Artist 'taking legal advice' over Tories' use of Andy Burnham portrait |
| fact067 | conflict | TRUE | AI | Sudan: Driver killed in aerial attack on aid trucks in South Kordofan |
| fact068 | conflict | TRUE | AI | Sudan: Driver killed in aerial attack on aid trucks in South Kordofan |
| fact069 | crime | TRUE | AI | An Arson Investigation Is Underway After a Suspected 'Senseless Act of Vandalism'... |
| fact070 | crime | TRUE | AI | An Arson Investigation Is Underway After a Suspected 'Senseless Act of Vandalism'... |
| fact071 | crime | TRUE | AI | An Arson Investigation Is Underway After a Suspected 'Senseless Act of Vandalism'... |
| fact072 | sport | TRUE | AI | Claudia Pina, la nueva estrella del Camp Nou |
| fact073 | sport | TRUE | AI | Claudia Pina, la nueva estrella del Camp Nou |
| fact077 | quiz | TRUE | AI | Can you solve it? Isaac Newton's tower drop puzzle |
| fact087 | conflict | TRUE | AI | Yemen: Children brave snipers and mortars to go to school near front line |
| fact091 | politics | PARTIALLY_TRUE | AI | ¿Por qué Cataluña volverá a decidir las elecciones en España? |
| fact092 | politics | TRUE | AI | ¿Por qué Cataluña volverá a decidir las elecciones en España? |
| fact093 | celebrity | TRUE | AI | Quiénes son los nominados al Martín Fierro de Radio 2026 |
| fact097 | conflict | UNVERIFIED | AI | Israeli demolition in East Jerusalem displaces 69 Palestinians |
| fact098 | conflict | TRUE | AI | Israeli demolition in East Jerusalem displaces 69 Palestinians |
| fact102 | labour | TRUE | AI | Madrid despide a Maricarmen con una marcha multitudinaria |
| fact103 | labour | TRUE | AI | Madrid despide a Maricarmen con una marcha multitudinaria |
| fact104 | labour | TRUE | AI | Madrid despide a Maricarmen con una marcha multitudinaria |
| fact105 | labour | TRUE | AI | Madrid despide a Maricarmen con una marcha multitudinaria |
| fact108 | roundup | TRUE | AI | What We're Reading: Rat Rangers to the Rescue |
| fact109 | roundup | TRUE | AI | What We're Reading: Rat Rangers to the Rescue |
| fact110 | roundup | TRUE | AI | What We're Reading: Rat Rangers to the Rescue |
