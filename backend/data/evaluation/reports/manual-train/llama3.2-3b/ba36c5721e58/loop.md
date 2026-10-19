# The tuning loop: manual-train

Run `ba36c5721e58`, model `llama3.2:3b`. 69 of 69 claims scored. Bootstrap: 10000 resamples, seed 2026.

First pass: accuracy 44.9% [33.3%, 56.5%], 38 claims disagree with gold.

## What the loop made of each claim

| Outcome | Claims | Meaning | Ids |
|---|---|---|---|
| agreed | 31 | the first verdict is the gold label |  |
| fixed | 9 | the second look reached the gold label | fact008, fact085, fact106, fact125, fact127, fact132, fact133, fact138, fact163 |
| retrieval | 8 | the annotator's pages give the gold label: the search never found them | fact015, fact064, fact090, fact107, fact114, fact124, fact176, fact178 |
| adjudicate | 15 | the annotator's pages give the pipeline's verdict: a person decides, model or label | fact009, fact010, fact011, fact038, fact066, fact081, fact088, fact100, fact123, fact126, fact129, fact151, fact153, fact154, fact169 |
| reasoning | 2 | the annotator's pages give a third verdict | fact016, fact143 |
| unreadable | 2 | no annotator page could be read | fact037, fact101 |
| no_reference | 2 | the row has no annotator links (an UNVERIFIED gold label needs none) | fact049, fact099 |

Disagreements by origin: mutated {'adjudicate': 4, 'fixed': 1, 'retrieval': 2}; natural {'fixed': 8, 'adjudicate': 11, 'retrieval': 6, 'reasoning': 2, 'unreadable': 2, 'no_reference': 2}

With the gold label choosing which claims get a second look (an upper bound, not a score): accuracy 58.0%.

## The trigger, without gold

The second verdict in place of the first wherever the rule fires, paired over the same claims.

| Rule | Fired | Accuracy before | after | Difference [95% CI] | Wrong to right | Right to wrong |
|---|---|---|---|---|---|---|
| unverifiedOrUnsure | 15 | 44.9% | 47.8% | +2.9 [-2.9, +8.7] | 3 | 1 |
| unverifiedOnly | 2 | 44.9% | 44.9% | +0.0 [+0.0, +0.0] | 0 | 0 |

## For a person to decide: model or label

Gold label -> the model's verdict on the annotator's pages: TRUE -> FALSE (5); FALSE -> TRUE (4); UNVERIFIED -> FALSE (3); PARTIALLY_TRUE -> FALSE (2); PARTIALLY_TRUE -> TRUE (1)

| Id | Claim | Gold | First | Second look | On the annotator's pages | Why |
|---|---|---|---|---|---|---|
| fact009 | La nave despegó hacia las 14:49 (hora española) en su decimocuarta prueba desde el complejo de SpaceX en el extremo sur  | PARTIALLY_TRUE | FALSE | FALSE | FALSE | La nave no reingresó en la órbita terrestre, sino que se situó en la órbita terrestre y realizó una maniobra orbital, pero no reingresó |
| fact010 | Cuando sea ejecutada esta infraestructura, la función de ronda metropolitana pasará a esa 'nueva' SE-20 y desaparecerá p | UNVERIFIED | FALSE | FALSE | FALSE | La Ronda Urbana Norte no será un gran bulevar verde, sino que se convertirá en la SE-20 y desaparecerá de la Ronda Urbana Norte. |
| fact011 | El proyecto original de ronda intermedia que tumbó Europa hace diez años se transformará en una vía urbana que conectará | UNVERIFIED | FALSE | FALSE | FALSE | El proyecto original de ronda intermedia que tumbó Europa hace diez años se transformará en una vía urbana que conectará la Supernorte con la SE-40 y la SE-30 a la altura del Calonge para desatascar l |
| fact038 | Meanwhile, the Arctic recorded its minimum summer sea ice extent on 12 September. | TRUE | FALSE | FALSE | FALSE | The claim states the Arctic recorded its minimum summer sea ice extent on September 12, but the evidence actually states that the minimum likely reached on September 12, and the 2026 minimum shares th |
| fact066 | Bodegas Benjamin de Rothschild & Vega Sicilia (Macán) es el proyecto conjunto, con sede en Samaniego (La Rioja), de esta | PARTIALLY_TRUE | TRUE | TRUE | TRUE | The claim states that Bodegas Benjamin de Rothschild & Vega Sicilia is a joint project between the Rothschild and Vega Sicilia families, with its headquarters in Samaniego, La Rioja. The evidence conf |
| fact081 | In 2012, an 11-set Venn diagram that met those criteria was discovered, and another with 13 sets was found in 2014. | TRUE | FALSE | FALSE | FALSE | The claim states that an 11-set Venn diagram was discovered in 2012, but the evidence shows that a simple symmetric 11-Venn diagram was found in 2012, not an 11-set Venn diagram. |
| fact088 | Blau and her colleague, Nidhi Bhutani, an associate professor of orthopedic surgery, discovered that in older mice, bloc | TRUE | FALSE | FALSE | FALSE | The claim states that blocking 15-PGDH reversed cartilage loss in older mice, but the evidence shows that blocking 15-PGDH prevented the development of arthritis after knee injuries, not reversed exis |
| fact100 | In total, wind and solar have generated a record 41% share of the UK’s electricity needs in 2026 to date, compared with  | UNVERIFIED | FALSE | FALSE | FALSE | The claim states that wind and solar have generated a record 41% share of the UK's electricity needs, but the evidence only reports the share of electricity generation by Major Power Producers, which  |
| fact123 | As Juice flew just 8640 km above the Indian Ocean, it snapped a series of images with its onboard monitoring cameras. | TRUE | FALSE | FALSE | FALSE | The claim states Juice flew 8640 km above the Indian Ocean, but the evidence states it passed at an altitude of 8,640 km above the Indian Ocean, which is not the same location. |
| fact126 | A 2026 Pew report found that 10% of Americans are using chatbots for emotional support or companionship. | TRUE | FALSE | FALSE | FALSE | The claim states that 10% of Americans use chatbots for emotional support or companionship, but the evidence only mentions that 'about half of U.S. adults now report using AI chatbots', without provid |
| fact129 | Cases of ARFID are also on the rise, increasing by 305 percent from 2018 to 2022, according to a 2023 FAIR Health white  | PARTIALLY_TRUE | TRUE | FALSE | FALSE | The claim states that ARFID increased by 305 percent, but the evidence shows that ARFID increased by 305 percent from 2018 to 2022, while the overall increase in eating disorder claim lines was 65 per |
| fact151 | La vicepresidenta segunda del Gobierno, Yolanda Díaz, ha presentado hoy en Barcelona un ejercicio de prospectiva social, | FALSE | TRUE | TRUE | TRUE | La vicepresidenta segunda del Gobierno, Yolanda Díaz, ha presentado un ejercicio de prospectiva social que analiza cómo podrían evolucionar las trayectorias vitales de la población española en los pró |
| fact153 | Much attention is now directed toward this, including an MIT report on AI and education published this spring. | FALSE | TRUE | TRUE | TRUE | The MIT report outlines recommendations for responsible AI use in education, including creating an 'AI-aware' curriculum, centering decisions on people and community, and building ongoing infrastructu |
| fact154 | Two days later, last Friday, a county emergency official arrived at Kirk’s debris-laden front lawn in Wyandotte County,  | FALSE | TRUE | TRUE | TRUE | The claim states that a county emergency official arrived at Kirk's debris-laden front lawn with a tarp, lumber, and a crew to cover up the maple-shaped gash in Kirk's house, and this is supported by  |
| fact169 | “It’s like in the Great Stink,” she adds, referring to the hot, dry summer of 1958, when the Thames – and all the raw se | FALSE | TRUE | TRUE | TRUE | The claim refers to the hot, dry summer of 1858 when the Thames became a foul-smelling health hazard due to raw sewage and rubbish dumped into it, which is accurately described in the provided evidenc |

## The search missed what the annotator found

| Id | Claim | Gold | First | Second look | On the annotator's pages | Why |
|---|---|---|---|---|---|---|
| fact015 | Founded in 2017 by writer Wanjiru Koinange and publisher Angela Wachuka, the nonprofit has restored the Eastlands and Ka | TRUE | FALSE | FALSE | TRUE | The claim states that the nonprofit was founded in 2017 by writer Wanjiru Koinange and publisher Angela Wachuka, which is supported by evidence [0] and [1]. However, the exact date of the founding is  |
| fact064 | In eight of 11 industrial sectors — including textiles, food, pharmaceuticals, and machinery — fossil fuel use has alrea | TRUE | FALSE | FALSE | TRUE | The evidence confirms that China's industrial sectors are shifting away from fossil fuels and towards clean electricity, with wind, solar, and batteries displacing coal, oil, and gas. |
| fact090 | “It’s like in the Great Stink,” she adds, referring to the hot, dry summer of 1858, when the Thames – and all the raw se | TRUE | UNVERIFIED | FALSE | TRUE | The claim accurately references the Great Stink of 1858, a significant event in London's history where the Thames River became a public health menace due to severe pollution. |
| fact107 | “Oh, it’s unbelievable, the way the community has come together,” Kirk said. | TRUE | FALSE | FALSE | TRUE | The claim is supported by the quote from Kirk, where he expresses gratitude and amazement at the community's response to his situation. |
| fact114 | El Presidente del Gobierno, Pedro Sánchez, ha presentado hoy en Barcelona un ejercicio de prospectiva social, impulsado  | TRUE | PARTIALLY_TRUE | PARTIALLY_TRUE | TRUE | El Presidente del Gobierno, Pedro Sánchez, ha presentado un ejercicio de prospectiva social que analiza cómo podrían evolucionar las trayectorias vitales de la población española en los próximos 24 añ |
| fact124 | Esto también conlleva un estado de ánimo más bajo que afecta al bienestar emocional de las mujeres, según un estudio pub | TRUE | FALSE | FALSE | TRUE | The study found a link between higher progesterone levels and less distinct brain patterns involved in emotion control, which could explain differences in mood among women. |
| fact176 | Blau and her colleague, Nidhi Bhutani, an associate professor of orthopedic surgery, discovered that in older mice, bloc | FALSE | TRUE | TRUE | FALSE | The claim states that blocking 15-PGDH accelerated cartilage loss in older mice, but the evidence shows that blocking 15-PGDH actually reversed cartilage loss and prevented arthritis. |
| fact178 | En el estudio participaron 316 mujeres con ciclos menstruales naturales (que no utilizaban anticonceptivos hormonales). | FALSE | TRUE | TRUE | FALSE | The study focuses on the effect of endogenous progesterone on frontostriatal representations of emotion control, but does not mention menstrual cycles or hormone use in women. |

## Cost

40 second looks and 27 checks against the annotator's pages: 108 LLM calls, 9884.7 s in all.
