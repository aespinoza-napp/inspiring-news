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