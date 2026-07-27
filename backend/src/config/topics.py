from src.models.topics import Topic


TOPICS = {

    # ==========================
    # Environment
    # ==========================

    "wildlife": Topic(
        name="Wildlife",
        description="News about wildlife, animal species, conservation projects, endangered species, habitats and biodiversity protection.",
        keywords=["wildlife", "fauna", "animals", "species", "conservation"],
    ),

    "climate_change": Topic(
        name="Climate Change",
        description="News about climate change, global warming, greenhouse gases, carbon emissions, climate policy and decarbonization.",
        keywords=["climate change", "global warming", "carbon emissions", "net zero"],
    ),

    "circular_economy": Topic(
        name="Circular Economy",
        description="News related to recycling, reuse, waste reduction, sustainable production, resource efficiency and circular economy initiatives.",
        keywords=["circular economy", "recycling", "reuse", "zero waste"],
    ),

    "environmental_discoveries": Topic(
        name="Environmental Discoveries",
        description="Scientific discoveries about nature, ecosystems, geology, environmental research and ecological breakthroughs.",
        keywords=["environment", "discovery", "nature", "research"],
    ),

    "green_innovation": Topic(
        name="Green Innovation",
        description="Innovations, startups and technologies focused on sustainability, renewable solutions and environmental engineering.",
        keywords=["green technology", "clean technology", "innovation"],
    ),

    "agriculture": Topic(
        name="Agriculture",
        description="News about farming, crops, food production, agronomy, livestock and sustainable agriculture.",
        keywords=["agriculture", "crop", "soil", "food production"],
    ),

    "oceans": Topic(
        name="Oceans",
        description="Marine ecosystems, oceans, coral reefs, fisheries, coastal environments and marine biodiversity.",
        keywords=["ocean", "marine", "sea", "coral reef"],
    ),

    "social_movements": Topic(
        name="Social Movements",
        description="Community initiatives, activism, volunteering, NGOs, civic engagement and social impact.",
        keywords=["community", "activism", "volunteering", "social impact"],
    ),

    "employment": Topic(
        name="Employment",
        description="Jobs, careers, labour market, employment policies, recruitment, workplace and professional skills.",
        keywords=["employment", "jobs", "career", "workforce"],
    ),

    "education": Topic(
        name="Education",
        description="Schools, universities, education systems, teaching, students, educational research and learning.",
        keywords=["education", "school", "university", "student"],
    ),

    "energy": Topic(
        name="Energy",
        description="Renewable energy, solar power, wind energy, batteries, hydrogen, electricity and energy transition.",
        keywords=["renewable energy", "solar", "wind", "hydrogen"],
    ),

    "industry": Topic(
        name="Industry",
        description="Manufacturing, industrial production, factories, industrial innovation and supply chains.",
        keywords=["industry", "manufacturing", "factory"],
    ),

    "ecotourism": Topic(
        name="Ecotourism",
        description="Sustainable tourism, responsible travel, protected natural areas and eco-friendly tourism.",
        keywords=["ecotourism", "nature tourism", "sustainable tourism"],
    ),

    "sustainable_food": Topic(
        name="Sustainable Food",
        description="Organic food, regenerative agriculture, sustainable diets, food sustainability and responsible consumption.",
        keywords=["organic food", "plant-based", "regenerative agriculture"],
    ),

    "biodiversity": Topic(
        name="Biodiversity",
        description="Species diversity, ecosystems, habitats, biodiversity conservation and ecological restoration.",
        keywords=["biodiversity", "ecosystem", "habitat"],
    ),

    "sustainability_tips": Topic(
        name="Sustainability Tips",
        description="Practical advice about sustainable living, reducing carbon footprint, recycling and eco-friendly habits.",
        keywords=["eco-friendly", "green living", "carbon footprint"],
    ),

    "sustainable_transport": Topic(
        name="Sustainable Transport",
        description="Electric vehicles, cycling, public transport, sustainable mobility and green transportation.",
        keywords=["electric vehicle", "public transport", "cycling"],
    ),

    # ==========================
    # Science
    # ==========================

    "artificial_intelligence": Topic(
        name="Artificial Intelligence",
        description="Artificial intelligence, machine learning, large language models, robotics, generative AI and AI applications.",
        keywords=["AI", "machine learning", "GPT", "LLM", "OpenAI", "Anthropic"],
    ),

    "space": Topic(
        name="Space",
        description="Astronomy, astrophysics, satellites, space exploration, rockets, NASA, ESA and SpaceX missions.",
        keywords=["NASA", "ESA", "SpaceX", "Mars", "Moon"],
    ),

    "robotics": Topic(
        name="Robotics",
        description="Robots, automation, humanoids, drones, autonomous systems and industrial robotics.",
        keywords=["robot", "automation", "drone", "humanoid"],
    ),

    "computing": Topic(
        name="Computing",
        description="Software engineering, programming, cloud computing, cybersecurity, computer science and hardware.",
        keywords=["software", "programming", "cloud", "cybersecurity"],
    ),

    "emerging_technology": Topic(
        name="Emerging Technology",
        description="Quantum computing, nanotechnology, biotechnology and breakthrough technological innovations.",
        keywords=["quantum computing", "nanotechnology", "biotechnology"],
    ),

    "psychology": Topic(
        name="Psychology",
        description="Mental health, behaviour, cognition, wellbeing, neuroscience and psychological research.",
        keywords=["psychology", "mental health", "mindfulness"],
    ),

    "medicine": Topic(
        name="Medicine",
        description="Healthcare, clinical trials, diseases, treatments, vaccines, medical innovation and public health.",
        keywords=["medicine", "healthcare", "vaccine", "therapy"],
    ),

    "myths": Topic(
        name="Myths and Fact Checking",
        description="Fact-checking, misinformation, myths, urban legends and debunking false claims.",
        keywords=["fact check", "myth", "debunked"],
    ),

    "biology": Topic(
        name="Biology",
        description="Genetics, microbiology, evolution, cells, DNA and biological sciences.",
        keywords=["biology", "DNA", "genetics"],
    ),

    # ==========================
    # Lifestyle
    # ==========================

    "wellbeing": Topic(
        name="Wellbeing",
        description="Healthy lifestyles, wellness, quality of life, mental wellbeing and self-improvement.",
        keywords=["wellbeing", "wellness", "healthy lifestyle"],
    ),

    "fashion": Topic(
        name="Fashion",
        description="Fashion industry, clothing, designers, sustainable fashion and style trends.",
        keywords=["fashion", "designer", "clothing"],
    ),

    "travel": Topic(
        name="Travel",
        description="Travel destinations, tourism, holidays, cultural trips, adventure travel and visitor experiences.",
        keywords=["travel", "tourism", "vacation", "destination"],
    ),

    "healthy_food": Topic(
        name="Healthy Food",
        description="Nutrition, healthy recipes, balanced diets, superfoods and healthy eating habits.",
        keywords=["nutrition", "healthy recipes", "balanced diet"],
    ),

    "fitness": Topic(
        name="Fitness",
        description="Exercise, sports training, gyms, running, physical activity and personal fitness.",
        keywords=["fitness", "exercise", "gym", "running"],
    ),

    "home": Topic(
        name="Home",
        description="Interior design, home improvement, smart homes, decoration and sustainable housing.",
        keywords=["interior design", "smart home", "decor"],
    ),

    "gastronomy": Topic(
        name="Gastronomy",
        description="Cuisine, restaurants, chefs, recipes, culinary culture and food experiences.",
        keywords=["chef", "restaurant", "recipe"],
    ),

    "financial_wellbeing": Topic(
        name="Financial Wellbeing",
        description="Personal finance, savings, investing, budgeting and financial education.",
        keywords=["saving", "investing", "budgeting"],
    ),

    "beauty": Topic(
        name="Beauty",
        description="Skincare, cosmetics, beauty products, makeup and self-care.",
        keywords=["beauty", "skincare", "makeup"],
    ),

    "positive_living": Topic(
        name="Positive Living",
        description="Motivation, happiness, personal growth, inspiration and positive psychology.",
        keywords=["motivation", "happiness", "personal growth"],
    ),

    "city_life": Topic(
        name="City Life",
        description="Urban living, smart cities, communities, mobility and quality of life in cities.",
        keywords=["urban living", "smart city", "community"],
    ),

    # ==========================
    # Culture & Society
    # ==========================

    "cinema": Topic(
        name="Cinema",
        description="Films, directors, actors, movie releases, film festivals and the cinema industry.",
        keywords=["film", "movie", "director"],
    ),

    "music": Topic(
        name="Music",
        description="Artists, albums, concerts, festivals, music industry and musical culture.",
        keywords=["music", "concert", "artist"],
    ),

    "theatre": Topic(
        name="Theatre",
        description="Stage performances, theatre productions, actors and performing arts.",
        keywords=["theatre", "play", "performance"],
    ),

    "art": Topic(
        name="Art",
        description="Painting, sculpture, museums, exhibitions, artists and visual arts.",
        keywords=["art", "museum", "painting"],
    ),

    "dance": Topic(
        name="Dance",
        description="Dance, ballet, choreography, dance companies and live performances.",
        keywords=["dance", "ballet", "choreography"],
    ),

    "culture": Topic(
        name="Culture",
        description="Cultural heritage, traditions, local customs, festivals and cultural events.",
        keywords=["culture", "heritage", "tradition"],
    ),

    "literature": Topic(
        name="Literature",
        description="Books, novels, authors, poetry, publishing and literary events.",
        keywords=["book", "novel", "author"],
    ),

    "architecture": Topic(
        name="Architecture",
        description="Architecture, historic buildings, urban design, architects and restoration projects.",
        keywords=["architecture", "building", "architect"],
    ),

    "international_events": Topic(
        name="International Events",
        description="Global summits, international conferences, expos and worldwide events.",
        keywords=["summit", "conference", "world expo"],
    ),

    "national_events": Topic(
        name="National Events",
        description="National celebrations, festivals, commemorations and public events.",
        keywords=["festival", "celebration"],
    ),

    "history": Topic(
        name="History",
        description="Historical events, archaeology, civilizations, historical heritage and discoveries.",
        keywords=["history", "archaeology", "heritage"],
    ),

    "good_deeds": Topic(
        name="Good Deeds",
        description="Acts of kindness, volunteering, charity, solidarity and community service.",
        keywords=["charity", "volunteer", "kindness"],
    ),

    "sports": Topic(
        name="Sports",
        description="Sports competitions, athletes, football, basketball, tennis, Olympic sports and sporting events.",
        keywords=["football", "basketball", "tennis", "competition"],
    ),

    "social_stories": Topic(
        name="Social Stories",
        description="Human-interest stories, testimonials, inspiring communities and real-life experiences.",
        keywords=["human story", "testimonial", "community"],
    ),

    "quotes": Topic(
        name="Quotes",
        description="Inspirational quotes, famous quotations, speeches and motivational messages.",
        keywords=["quote", "inspirational quote"],
    ),

    "success_stories": Topic(
        name="Success Stories",
        description="Entrepreneurship, achievements, inspiring people, innovation and role models.",
        keywords=["entrepreneur", "achievement", "role model"],
    ),
}