# A topic classifier trained on MN-DS, in English and Spanish: the rule

Written on 2026-11-17, before any result, at the author's request: the topics should come
from a classifier trained on a published dataset the literature accepts, in both of the app's
languages.

## The data

**MN-DS** (Petukhova & Fachada, "MN-DS: A Multilabeled News Dataset for News Articles
Hierarchical Classification", *Data* 8(5), 74, 2023; CC BY 4.0): 10,917 English news articles
of 2019 from 215 outlets (NELA-GT-2019), each labelled by hand, by one coder, with one IPTC
Media Topic: 17 first-level, 109 second-level categories, about 100 articles per second-level
one. Read from the Hugging Face mirror `textminr/mn-ds` (Zenodo refused this machine); it
matches the paper's Table 1 exactly (every first-level count, 109 second-level, 215 sources).

No human-labelled news-topic set in English and Spanish covers the app's five groups
(searched 17 Nov: MLDoc, XGLUE NC, MIND, SIB-200, X-Topic, Babel Briefings; Environment is
missing from every bilingual one). So the Spanish half is **MN-DS machine-translated**
(Helsinki-NLP OPUS-MT en-es), "translate-train", the usual way to train for a language with no
labelled data of its own. Its labels are the English article's.

## The classifier

Each article as its title and first 80 words, in each language; bge-m3 (the model the app
already holds) embeds it; multinomial logistic regression over the 17 first-level
categories, its C chosen by 5-fold cross-validation on the training part only. Split 80/20 by
article id (stratified by category, seed 0), so an article and its translation are on the same
side. Fixed before the results:

| IPTC first level | The app's group |
|---|---|
| environment; weather | environment |
| science and technology | science |
| health | health |
| arts, culture, entertainment and media; human interest | culture |
| education; society; labour | society |
| politics; crime, law and justice; conflict, war and peace; disaster, accident and emergency incident; economy, business and finance; sport; religion and belief; lifestyle and leisure | none (off the mission or no group) |

## What decides

On the app's own 56 labelled articles (38 English, 20 Spanish less the two that would not
extract; the gold topics of `experiments/topics/20261020T093630Z`, many from the AI pass and
none reviewed), the group the classifier's top category maps to, against today's embedding
classifier's top-1 group (0.82 [0.71, 0.91]), claim by claim.

**Adopted as the group classifier** if both hold:

1. its group accuracy on all 56 is at least the embedding classifier's (point estimate), and
2. in neither language does it get more than 2 articles fewer right than the embedding
   classifier.

Otherwise it is kept as an option and the embedding classifier stays. Either way the 23 topics
stay: the IPTC categories name what an article is about at a coarser level, and the app's
topics are what its rounds and admission are built on.

Reported beside it, not deciding: accuracy and macro-F1 over the 17 categories on MN-DS's
held-out fifth, in English and in its Spanish translation, against the paper's own level-1
F1 (TF-IDF + logistic regression 0.774, DistilBERT 0.844, on its own split), and the seconds
an article takes.

## What it cannot say

56 articles give intervals of about ±10 points. MN-DS is US news from 2019, much of it hard
news; the app reads constructive news from 2026 in two languages. The Spanish training half is
translated, not written in Spanish. The gold groups are partly an AI's.
