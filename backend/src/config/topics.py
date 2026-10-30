from src.models.nlp.topics import Topic

TOPICS = {

    # ==========================
    # Society
    # ==========================

    "education": Topic(
        name="Education",
        description="Education systems, schools, universities, lifelong learning, educational innovation and public education policies.",
        keywords=[
            "education", "school", "university", "student",
            "teacher", "learning", "curriculum"
        ],
    ),

    "community": Topic(
        name="Community & Social Impact",
        description="Community initiatives, volunteering, NGOs, social innovation, inclusion, solidarity, disaster relief and civic engagement.",
        keywords=[
            "community", "volunteer", "charity",
            "social impact", "nonprofit", "activism",
            # Added after classifying real articles (e.g. Colombia earthquake
            # relief) that were miscategorized on-site as "medio ambiente"
            # but are actually humanitarian/community stories, not climate.
            "humanitarian aid", "disaster relief", "earthquake",
            "solidarity", "fundraising"
        ],
    ),

    "employment": Topic(
        name="Employment",
        description="Jobs, careers, labour market, workplace innovation, entrepreneurship and professional development.",
        keywords=[
            "employment", "career", "jobs",
            "workforce", "entrepreneurship", "skills"
        ],
    ),

    "cities": Topic(
        name="Cities & Society",
        description="Urban development, smart cities, mobility, housing, homelessness, quality of life and public services.",
        keywords=[
            "city", "urban", "housing",
            "mobility", "community", "transport",
            # Added after "Housing First Finlandia" article
            "homelessness", "housing first", "affordable housing"
        ],
    ),

    # ==========================
    # Science
    # ==========================

    "space": Topic(
        name="Space",
        description="Astronomy, astrophysics, satellites, planetary science and space exploration.",
        keywords=[
            "space", "NASA", "ESA",
            "SpaceX", "Mars", "Moon"
        ],
    ),

    "technology": Topic(
        name="Technology",
        description="Computing, cybersecurity, software engineering, robotics, artificial intelligence and emerging technologies.",
        keywords=[
            "technology", "software",
            "robotics", "cybersecurity",
            "cloud", "automation",
            # Major gap found: AI is one of the site's most recurring topics
            # ("La IA ya ganó un Nobel...", "5 usos positivos de la IA...")
            # yet had zero AI-related keywords before this.
            "artificial intelligence", "AI", "machine learning",
            "algorithm", "neural network",
            # From the EU replaceable-battery article
            "right to repair", "repairability"
        ],
    ),

    "research": Topic(
        name="Scientific Research",
        description="Scientific discoveries, academic research, innovation, laboratories, cartography and multidisciplinary science.",
        keywords=[
            "research", "discovery",
            "science", "innovation",
            "breakthrough",
            # From the "Equal Earth" cartographer article
            "cartography", "map", "geography"
        ],
    ),

    "biology": Topic(
        name="Biology",
        description="Life sciences including genetics, microbiology, evolution, ecology and biotechnology.",
        keywords=[
            "biology", "DNA",
            "genetics", "microbiology",
            "evolution", "microbiome"
        ],
    ),

    # ==========================
    # Environment
    # ==========================

    "climate": Topic(
        name="Climate",
        description="Climate change, decarbonisation, emissions, environmental policy, climate activism and climate adaptation.",
        keywords=[
            "climate change", "global warming",
            "carbon", "net zero",
            "emissions",
            # From the Francisco Vera profile
            "climate activist", "youth activism"
        ],
    ),

    "nature": Topic(
        name="Nature & Biodiversity",
        description="Wildlife, biodiversity, conservation, ecosystems, marine life and protected natural areas.",
        keywords=[
            "wildlife", "biodiversity",
            "ecosystem", "species",
            "conservation",
            # From the Cristina Zenato shark-conservation article
            "shark", "marine life", "ocean conservation"
        ],
    ),

    "energy": Topic(
        name="Energy",
        description="Renewable energy, clean technologies, batteries, hydrogen and energy transition.",
        keywords=[
            "renewable energy",
            "solar", "wind",
            "battery", "hydrogen"
        ],
    ),

    "sustainability": Topic(
        name="Sustainability",
        description="Circular economy, sustainable production, plastic and microplastic pollution, responsible consumption and green innovation.",
        keywords=[
            "sustainability",
            "circular economy",
            "recycling",
            "green technology",
            "eco-friendly",
            # From the CSIC nanoplastics-cleaning-particle article
            "microplastics", "nanoplastics", "water pollution",
            "plastic pollution"
        ],
    ),

    "food": Topic(
        name="Food & Agriculture",
        description="Agriculture, food production, regenerative farming, sustainable food systems and oceans.",
        keywords=[
            "agriculture",
            "food production",
            "organic food",
            "marine",
            "ocean"
        ],
    ),

    # ==========================
    # Culture
    # ==========================

    "arts": Topic(
        name="Arts",
        description="Visual arts, museums, architecture, dance, theatre and artistic expression.",
        keywords=[
            "art", "museum",
            "architecture",
            "dance",
            "theatre"
        ],
    ),

    "entertainment": Topic(
        name="Entertainment",
        description="Cinema, television, music, festivals, animation, internet culture, viral trends and cultural productions.",
        keywords=[
            "movie", "film",
            "music", "concert",
            "festival",
            # From "Spider-Man Brand New Day" and the coyote/Wile E. Coyote
            # cultural-analysis piece
            "animation", "cartoon", "pop culture", "comic",
            # From "farmear aura" — viral public-space trend piece; the
            # existing topics had nothing for internet/social-media trends
            "viral trend", "internet culture", "social media trend"
        ],
    ),

    "heritage": Topic(
        name="History & Heritage",
        description="History, archaeology, historical discoveries, traditions and cultural heritage.",
        keywords=[
            "history",
            "archaeology",
            "heritage",
            "civilization"
        ],
    ),

    "literature": Topic(
        name="Literature",
        description="Books, authors, publishing, reading and literary events.",
        keywords=[
            "book",
            "author",
            "novel",
            "literature"
        ],
    ),

    "inspiration": Topic(
        name="Inspirational Stories",
        description="Success stories, acts of kindness, role models, inspiring people, activism and positive social initiatives.",
        keywords=[
            "success",
            "kindness",
            "volunteer",
            "achievement",
            "role model",
            # Recurring pattern across profiles like Francisco Vera and
            # Cristina Zenato: individual activists/advocates as protagonists
            "activist", "advocate", "humanitarian"
        ],
    ),

    # ==========================
    # Health
    # ==========================

    "medicine": Topic(
        name="Medicine",
        description="Healthcare, diseases, vaccines, treatments, clinical research, hospital innovation and medical innovation.",
        keywords=[
            "medicine",
            "healthcare",
            "vaccine",
            "therapy",
            "clinical trial",
            # From the King's College rooftop-ICU-garden article and the
            # Juegaterapia pediatric-cancer article
            "hospital innovation", "pediatric", "cancer treatment"
        ],
    ),

    "mental_health": Topic(
        name="Mental Health",
        description="Psychology, emotional wellbeing, neuroscience, online behaviour, stress management and mental health research.",
        keywords=[
            "mental health",
            "psychology",
            "wellbeing",
            "mindfulness",
            "depression",
            # From "Por qué la gente es más agresiva en internet"
            "online behavior", "internet aggression", "social media psychology"
        ],
    ),

    "nutrition": Topic(
        name="Nutrition",
        description="Healthy eating, nutrition, balanced diets, food science and healthy recipes.",
        keywords=[
            "nutrition",
            "healthy eating",
            "diet",
            "healthy recipes"
        ],
    ),

    "fitness": Topic(
        name="Fitness",
        description="Exercise, sports, physical activity, performance and healthy lifestyles.",
        keywords=[
            "fitness",
            "exercise",
            "gym",
            "running",
            "training"
        ],
    ),

    "public_health": Topic(
        name="Public Health",
        description="Health policies, epidemiology, prevention, healthcare systems and global health.",
        keywords=[
            "public health",
            "prevention",
            "epidemiology",
            "health policy",
            "WHO"
        ],
    ),
}

# The five groups this file is laid out in. The backend's one definition:
# ingestion discovers from the sources of up to three groups
# (src/services/ingestion_service.py, each source YAML's `groups`), and
# the evaluation balances its labelled facts over them, because 23 topics
# are too thin at 150 facts. labeller/ keeps its own copy - it imports
# nothing from backend/ - and tests/evaluation/test_harness_dataset.py
# holds the two equal and every topic above to exactly one group.
TOPIC_GROUPS = {
    "society": ["education", "community", "employment", "cities"],
    "science": ["space", "technology", "research", "biology"],
    "environment": ["climate", "nature", "energy", "sustainability", "food"],
    "culture": ["arts", "entertainment", "heritage", "literature", "inspiration"],
    "health": ["medicine", "mental_health", "nutrition", "fitness", "public_health"],
}

TOPIC_GROUP_NAMES = {
    "society": "Society",
    "science": "Science",
    "environment": "Environment",
    "culture": "Culture",
    "health": "Health",
}

GROUP_OF = {topic: group for group, topics in TOPIC_GROUPS.items() for topic in topics}


# Spanish words for each topic, read only by discovery's feed filter
# (src/services/scraper/strategies/rss.py) when a run is narrowed to some
# topic groups. TOPICS' keywords above are English: against a Spanish feed
# they kept 5 of El País's 149 entries, at random, so Spanish feeds were
# never filtered at all - and on 2026-10-05 an Environment round listed
# El País's and elDiario's election coverage. Matched against an item's
# title and categories, not its summary: a general feed's summaries are
# long, and a campaign speech mentions renewables, harvests and the
# political "clima" in passing (measured the same day: summaries let the
# elections through, titles did not). Written without accents and
# matched against accent-free text; each entry is the start of a word
# ("energ" is energía and energético), so short words that are the start
# of others (arte: artes, but also not "parte") are matched as whole words
# by ending them with a space. Kept apart from TOPICS so the classifier's
# keyword scoring is unchanged.
TOPIC_KEYWORDS_ES = {
    "education": ["educacion", "educativ", "escuela", "colegio", "universidad", "alumn", "estudiante", "profesor", "docente", "aprendizaje"],
    "community": ["solidari", "voluntari", "comunidad", "vecin", "ayuda humanitaria", "inclusion", "donacion", "donante", "beneficencia", "refugiad"],
    "employment": ["empleo", "laboral", "trabajador", "emprend", "contratacion", "salario"],
    "cities": ["ciudad", "urban", "vivienda", "movilidad", "transporte publico", "barrio", "municipal"],
    "space": ["espacial", "astronaut", "astronom", "satelite", "galaxia", "cohete", "telescopio", "marte ", "asteroide", "orbita"],
    "technology": ["tecnolog", "inteligencia artificial", "robot", "software", "digital", "ciberseguridad", "algoritmo", "innovacion"],
    # Not "investigacion" or "estudio": a police investigation and a
    # recording studio both matched.
    "research": ["investigador", "cientific", "descubr", "laboratorio", "ciencia"],
    "biology": ["biolog", "genetic", "genoma", "adn ", "especie", "celula", "bacteria", "evolucion", "microb"],
    # Not "clima" alone ("el clima político" is in every campaign), nor
    # "emisiones" (a concert's broadcasts matched).
    "climate": ["climatic", "cambio climatico", "calentamiento", "efecto invernadero", "co2 ", "carbono", "descarboniz", "sequia", "ola de calor", "medio ambiente", "medioambient"],
    "nature": ["naturaleza", "biodivers", "especie", "fauna", "flora", "animal", "bosque", "selva", "conservacion", "extincion", "aves ", "oceano", "humedal", "reforest"],
    "energy": ["energ", "renovable", "solar", "eolic", "hidrogeno", "bateria", "fotovoltaic", "electricidad"],
    "sustainability": ["sostenib", "reciclaj", "residuo", "plastico", "economia circular", "contaminacion", "reutiliz"],
    "food": ["agricult", "agrari", "alimentacion", "alimento", "cosecha", "ganader", "pesca", "cultivo", "agroecolog"],
    "arts": ["arte ", "artista", "museo", "exposicion", "pintor", "pintura", "escultur", "arquitect", "danza", "teatro"],
    "entertainment": ["cine ", "pelicula", "musica", "concierto", "festival", "documental"],
    "heritage": ["historia", "historic", "patrimonio", "arqueolog", "yacimiento", "tradicion", "monumento"],
    "literature": ["libro", "novela", "literatura", "escritor", "escritora", "poesia", "poeta", "lectura"],
    "inspiration": ["inspira", "superacion", "logro", "heroe", "heroina", "ejemplo"],
    "medicine": ["salud", "medic", "hospital", "enfermedad", "tratamiento", "vacuna", "cancer", "paciente", "terapia", "farmac"],
    "mental_health": ["salud mental", "psicolog", "ansiedad", "depresion", "bienestar", "estres", "emocional"],
    "nutrition": ["nutricion", "dieta", "alimentacion saludable", "receta", "vitamina", "azucar"],
    "fitness": ["ejercicio", "actividad fisica", "caminar", "entrenamiento", "gimnasio"],
    "public_health": ["salud publica", "epidemi", "prevencion", "sanidad", "oms ", "sanitari", "vacunacion", "pandemia"],
}


# ==========================
# The Devastating edition
# ==========================
#
# The other edition (src/config/editions.py, docs/decisions/editions.md):
# the news that is bad for humanity, with labels of its own. Separate
# dicts, not more entries in TOPICS, for two reasons: the positive
# classifier, the labeller's copy of the five groups and the evaluation's
# balance over them must not change, and a positive run must never label
# an article "Terrorism" - nor a devastating one "Inspirational Stories".
# Topic ids are distinct from TOPICS' so one lookup (editions.ALL_TOPICS)
# can find either edition's keywords for discovery's feed filter.
DEVASTATING_TOPICS = {

    # ==========================
    # Violence
    # ==========================

    "terrorism": Topic(
        name="Terrorism",
        description="Terrorist attacks, bombings, suicide bombers, extremist and jihadist groups, hostage-taking and attacks on civilians.",
        keywords=[
            "terrorism", "terrorist attack", "bombing", "suicide bomber",
            "extremist", "jihadist", "hostages", "car bomb", "terror",
            "militants", "explosion", "attack"
        ],
    ),

    "mass_killings": Topic(
        name="Mass Killings",
        description="Mass shootings, massacres, multiple homicides, serial killers, genocide and killings of many people at once.",
        keywords=[
            "mass shooting", "massacre", "gunman", "killed",
            "multiple homicide", "serial killer", "genocide", "death toll",
            "kills", "shooting", "stabbing", "murder", "dead"
        ],
    ),

    "war": Topic(
        name="War & Armed Conflict",
        description="Wars, invasions, airstrikes, shelling, drone attacks, civilian casualties, war crimes and refugees fleeing fighting.",
        keywords=[
            "war", "airstrike", "shelling", "invasion", "drone attack",
            "civilian casualties", "war crimes", "ceasefire collapse",
            "strike", "missile", "troops", "offensive", "fighting", "drone"
        ],
    ),

    # ==========================
    # Hate
    # ==========================

    "racism": Topic(
        name="Racism",
        description="Racism, racial discrimination, racist attacks and abuse, xenophobia, segregation and racial profiling by police or institutions.",
        keywords=[
            "racism", "racist", "racial discrimination", "xenophobia",
            "racial profiling", "segregation", "racial slur", "discrimination",
            "migrants", "white supremacist"
        ],
    ),

    "hate_crimes": Topic(
        name="Hate Crimes",
        description="Hate crimes and attacks on people for their religion, origin, sexuality or gender: antisemitism, islamophobia, homophobic and transphobic violence.",
        keywords=[
            "hate crime", "antisemitism", "islamophobia", "homophobic attack",
            "transphobic", "hate speech", "persecution", "hate", "antisemitic",
            "anti-Muslim"
        ],
    ),

    # ==========================
    # Despair
    # ==========================

    "suicide": Topic(
        name="Suicide & Self-harm",
        description="Suicide, suicide rates, self-harm and mental-health crises that end in death. Reported under safe-messaging guidelines.",
        keywords=[
            "suicide", "suicide rate", "self-harm", "took their own life",
            "mental health crisis", "suicides", "despair"
        ],
    ),

    "addiction": Topic(
        name="Addiction & Overdoses",
        description="Drug overdoses, the opioid and fentanyl crises, addiction deaths and drug cartels' violence.",
        keywords=[
            "overdose", "opioid crisis", "fentanyl", "addiction",
            "drug cartel", "drug deaths", "overdoses", "cartel", "gang",
            "drug trafficking"
        ],
    ),

    # ==========================
    # Catastrophe
    # ==========================

    "disasters": Topic(
        name="Disasters",
        description="Deadly natural and man-made disasters: earthquakes, floods, wildfires, hurricanes, building collapses, shipwrecks and industrial accidents.",
        keywords=[
            "earthquake", "flood", "wildfire", "hurricane",
            "collapse", "shipwreck", "explosion", "victims", "floods",
            "storm", "typhoon", "crash", "disaster", "fire"
        ],
    ),

    "famine": Topic(
        name="Famine & Epidemics",
        description="Famine, starvation, malnutrition, humanitarian catastrophes, deadly outbreaks and epidemics overwhelming health systems.",
        keywords=[
            "famine", "starvation", "malnutrition", "humanitarian catastrophe",
            "outbreak", "epidemic", "cholera", "hunger", "humanitarian crisis",
            "drought"
        ],
    ),

    # ==========================
    # Abuse of power
    # ==========================

    "corruption": Topic(
        name="Corruption",
        description="Corruption, bribery, embezzlement of public money, fraud by officials and companies, and cover-ups.",
        keywords=[
            "corruption", "bribery", "embezzlement", "fraud",
            "cover-up", "kickbacks", "money laundering", "corrupt",
            "scandal", "indicted"
        ],
    ),

    "human_rights": Topic(
        name="Human Rights Abuses",
        description="Torture, forced labour, human trafficking, child abuse, repression of protesters, political prisoners and enforced disappearances.",
        keywords=[
            "torture", "human trafficking", "forced labour", "child abuse",
            "repression", "political prisoners", "disappeared", "detained",
            "crackdown", "abuses", "executed"
        ],
    ),
}

DEVASTATING_TOPIC_GROUPS = {
    "violence": ["terrorism", "mass_killings", "war"],
    "hate": ["racism", "hate_crimes"],
    "despair": ["suicide", "addiction"],
    "catastrophe": ["disasters", "famine"],
    "abuse_of_power": ["corruption", "human_rights"],
}

DEVASTATING_TOPIC_GROUP_NAMES = {
    "violence": "Violence",
    "hate": "Hate",
    "despair": "Despair",
    "catastrophe": "Catastrophe",
    "abuse_of_power": "Abuse of Power",
}

DEVASTATING_GROUP_OF = {
    topic: group
    for group, topics in DEVASTATING_TOPIC_GROUPS.items()
    for topic in topics
}

# The Spanish feed filter's words for the devastating topics, written like
# TOPIC_KEYWORDS_ES: accent-free word starts, a trailing space for a
# whole word. Not "ataque" alone (a footballer's attack, a heart attack)
# nor "crisis" (every economic headline).
DEVASTATING_TOPIC_KEYWORDS_ES = {
    # Measured 2026-10-30 on a live Violence and Hate round: with the first
    # lists DW Español, ABC, El Mundo and Europa Press offered nothing -
    # "Nos han matado" and "arden en Ormuz" matched no word. Hence the
    # verbs ("mata", "muere"), "ataque" and "violencia". Not "crisis",
    # still: every economic headline.
    "terrorism": ["terroris", "atentado", "yihadis", "explosivo", "rehenes", "coche bomba", "extremista", "ataque", "bomba", "milicia", "secuestr"],
    "mass_killings": ["masacre", "matanza", "tiroteo", "asesin", "homicidio", "genocidio", "muertos", "muerto ", "mata ", "matan ", "matado", "muere", "mueren", "fallec", "apunal", "violencia", "victima"],
    "war": ["guerra", "bombarde", "ofensiva", "misil", "invasion", "crimenes de guerra", "dron", "victimas civiles", "ejercito", "tropas", "conflicto armado", "combate", "arden"],
    "racism": ["racismo", "racista", "xenofob", "discriminacion", "perfil racial", "segregacion", "migrantes", "inmigrantes"],
    "hate_crimes": ["delito de odio", "delitos de odio", "antisemit", "islamofob", "homofob", "transfob", "discurso de odio", "odio", "agresion", "persecucion"],
    "suicide": ["suicid", "autolesi", "se quito la vida", "salud mental", "acoso escolar"],
    "addiction": ["sobredosis", "opioide", "fentanilo", "adiccion", "cartel", "narcotrafic", "narco", "droga", "banda", "pandilla"],
    "disasters": ["terremoto", "inundacion", "incendio", "huracan", "derrumbe", "naufragio", "explosion", "dana ", "tormenta", "temporal", "accidente", "tragedia", "catastrofe", "sismo"],
    "famine": ["hambruna", "desnutricion", "hambre ", "catastrofe humanitaria", "brote", "epidemia", "colera", "crisis humanitaria", "sequia", "refugiad"],
    "corruption": ["corrupcion", "corrupto", "soborno", "malversacion", "fraude", "blanqueo", "comisiones ilegales", "imputad", "escandalo", "investigado", "detenido"],
    "human_rights": ["tortura", "trata de personas", "trabajo forzoso", "abuso infantil", "abusos", "represion", "presos politicos", "desaparecid", "derechos humanos", "detencion", "ejecutad", "carcel"],
}
