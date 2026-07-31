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
        description="Community initiatives, volunteering, NGOs, social innovation, inclusion, solidarity and civic engagement.",
        keywords=[
            "community", "volunteer", "charity",
            "social impact", "nonprofit", "activism"
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
        description="Urban development, smart cities, mobility, housing, quality of life and public services.",
        keywords=[
            "city", "urban", "housing",
            "mobility", "community", "transport"
        ],
    ),

    "fact_checking": Topic(
        name="Fact Checking",
        description="Verification of information, misinformation, fake news, myths and evidence-based journalism.",
        keywords=[
            "fact check", "misinformation",
            "fake news", "myth", "debunked"
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
        description="Computing, cybersecurity, software engineering, robotics and emerging technologies.",
        keywords=[
            "technology", "software",
            "robotics", "cybersecurity",
            "cloud", "automation"
        ],
    ),

    "research": Topic(
        name="Scientific Research",
        description="Scientific discoveries, academic research, innovation, laboratories and multidisciplinary science.",
        keywords=[
            "research", "discovery",
            "science", "innovation",
            "breakthrough"
        ],
    ),

    "biology": Topic(
        name="Biology",
        description="Life sciences including genetics, microbiology, evolution, ecology and biotechnology.",
        keywords=[
            "biology", "DNA",
            "genetics", "microbiology",
            "evolution"
        ],
    ),

    # ==========================
    # Environment
    # ==========================

    "climate": Topic(
        name="Climate",
        description="Climate change, decarbonisation, emissions, environmental policy and climate adaptation.",
        keywords=[
            "climate change", "global warming",
            "carbon", "net zero",
            "emissions"
        ],
    ),

    "nature": Topic(
        name="Nature & Biodiversity",
        description="Wildlife, biodiversity, conservation, ecosystems and protected natural areas.",
        keywords=[
            "wildlife", "biodiversity",
            "ecosystem", "species",
            "conservation"
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
        description="Circular economy, sustainable production, responsible consumption and green innovation.",
        keywords=[
            "sustainability",
            "circular economy",
            "recycling",
            "green technology",
            "eco-friendly"
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
        description="Cinema, television, music, festivals and cultural productions.",
        keywords=[
            "movie", "film",
            "music", "concert",
            "festival"
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
        description="Success stories, acts of kindness, role models, inspiring people and positive social initiatives.",
        keywords=[
            "success",
            "kindness",
            "volunteer",
            "achievement",
            "role model"
        ],
    ),

    # ==========================
    # Health
    # ==========================

    "medicine": Topic(
        name="Medicine",
        description="Healthcare, diseases, vaccines, treatments, clinical research and medical innovation.",
        keywords=[
            "medicine",
            "healthcare",
            "vaccine",
            "therapy",
            "clinical trial"
        ],
    ),

    "mental_health": Topic(
        name="Mental Health",
        description="Psychology, emotional wellbeing, neuroscience, stress management and mental health research.",
        keywords=[
            "mental health",
            "psychology",
            "wellbeing",
            "mindfulness",
            "depression"
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