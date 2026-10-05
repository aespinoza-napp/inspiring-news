TOPIC_URL_PATTERNS = {

    # ==========================
    # Society
    # ==========================

    "education": (
        "/education/",
        "/schools/",
        "/school/",
        "/university/",
        "/universities/",
        "/learning/",
        "/students/",
    ),

    "community": (
        "/community/",
        "/communities/",
        "/society/",
        "/social/",
        "/charity/",
        "/volunteer/",
        "/nonprofit/",
    ),

    "employment": (
        "/jobs/",
        "/job/",
        "/careers/",
        "/career/",
        "/employment/",
        "/work/",
        "/business/",
        "/economy/",
    ),

    "cities": (
        "/cities/",
        "/city/",
        "/urban/",
        "/housing/",
        "/transport/",
        "/mobility/",
        "/infrastructure/",
    ),

    "fact_checking": (
        "/fact-check/",
        "/factcheck/",
        "/fact-checking/",
        "/verification/",
        "/misinformation/",
        "/fake-news/",
    ),

    # ==========================
    # Science
    # ==========================

    "space": (
        "/space/",
        "/astronomy/",
        "/astrophysics/",
        "/nasa/",
        "/esa/",
        "/spacex/",
        "/science/space/",
    ),

    "technology": (
        "/technology/",
        "/tech/",
        "/ai/",
        "/artificial-intelligence/",
        "/software/",
        "/cybersecurity/",
        "/robotics/",
        "/innovation/",
    ),

    "research": (
        "/science/",
        "/research/",
        "/discoveries/",
        "/innovation/",
        "/laboratory/",
        "/breakthrough/",
    ),

    "biology": (
        "/biology/",
        "/genetics/",
        "/genome/",
        "/dna/",
        "/microbiology/",
        "/biotechnology/",
        "/life-sciences/",
    ),

    # ==========================
    # Environment
    # ==========================

    "climate": (
        "/climate/",
        "/climate-change/",
        "/environment/",
        "/global-warming/",
        "/carbon/",
        "/weather/",
    ),

    "nature": (
        "/nature/",
        "/wildlife/",
        "/biodiversity/",
        "/ecosystem/",
        "/conservation/",
        "/animals/",
        "/species/",
    ),

    "energy": (
        "/energy/",
        "/renewable-energy/",
        "/renewables/",
        "/solar/",
        "/wind/",
        "/hydrogen/",
        "/electricity/",
    ),

    "sustainability": (
        "/sustainability/",
        "/sustainable/",
        "/green/",
        "/green-tech/",
        "/clean-tech/",
        "/recycling/",
        "/circular-economy/",
    ),

    "food": (
        "/food/",
        "/agriculture/",
        "/farming/",
        "/organic/",
        "/nutrition/",
        "/oceans/",
        "/marine/",
    ),

    # ==========================
    # Culture
    # ==========================

    "arts": (
        "/art/",
        "/arts/",
        "/museum/",
        "/architecture/",
        "/design/",
        "/dance/",
        "/theatre/",
        "/theater/",
    ),

    "entertainment": (
        "/entertainment/",
        "/movies/",
        "/movie/",
        "/film/",
        "/cinema/",
        "/music/",
        "/tv/",
        "/television/",
        "/streaming/",
    ),

    "heritage": (
        "/history/",
        "/heritage/",
        "/archaeology/",
        "/culture/",
        "/civilization/",
        "/historic/",
    ),

    "literature": (
        "/books/",
        "/book/",
        "/literature/",
        "/reading/",
        "/authors/",
        "/publishing/",
    ),

    "inspiration": (
        "/inspiration/",
        "/success/",
        "/good-news/",
        "/positive-news/",
        "/human-interest/",
        "/community/",
    ),

    # ==========================
    # Health
    # ==========================

    "medicine": (
        "/health/",
        "/medicine/",
        "/medical/",
        "/healthcare/",
        "/disease/",
        "/vaccines/",
        "/clinical-trials/",
    ),

    "mental_health": (
        "/mental-health/",
        "/psychology/",
        "/wellbeing/",
        "/mindfulness/",
        "/brain/",
        "/neuroscience/",
    ),

    "nutrition": (
        "/nutrition/",
        "/healthy-eating/",
        "/diet/",
        "/recipes/",
        "/food/",
    ),

    "fitness": (
        "/fitness/",
        "/exercise/",
        "/workout/",
        "/gym/",
        "/running/",
        "/sports-health/",
    ),

    "public_health": (
        "/public-health/",
        "/health-policy/",
        "/epidemiology/",
        "/who/",
        "/prevention/",
        "/global-health/",
    ),
}


# The section names Spanish outlets use for the same topics - El País has
# /ciencia/, not /science/. Only read to find *section pages* to crawl
# (strategies/topic_pages.py); deliberately not merged into
# TOPIC_URL_PATTERNS above, which also decides whether a feed link looks
# like an article, and whose behaviour on the English feeds is settled.
TOPIC_SECTION_PATTERNS_ES = {
    "education": ("/educacion/",),
    "community": ("/sociedad/", "/solidaridad/"),
    "employment": ("/economia/", "/empleo/", "/trabajo/"),
    "cities": ("/ciudades/", "/vivienda/", "/movilidad/"),
    "space": ("/espacio/", "/astronomia/"),
    "technology": ("/tecnologia/", "/ciencia-y-tecnologia/"),
    "research": ("/ciencia/", "/investigacion/"),
    "biology": ("/biologia/", "/genetica/"),
    "climate": ("/clima/", "/medio-ambiente/", "/medioambiente/", "/cambio-climatico/", "/clima-y-medio-ambiente/"),
    "nature": ("/naturaleza/", "/animales/", "/biodiversidad/"),
    "energy": ("/energia/",),
    "sustainability": ("/sostenibilidad/",),
    "food": ("/gastronomia/", "/alimentacion/", "/agricultura/"),
    "arts": ("/cultura/", "/arte/", "/arquitectura/"),
    "entertainment": ("/cine/", "/musica/", "/television/", "/series/"),
    "heritage": ("/historia/", "/patrimonio/", "/arqueologia/"),
    "literature": ("/libros/", "/literatura/"),
    "inspiration": ("/buenas-noticias/",),
    "medicine": ("/salud/", "/sanidad/", "/medicina/"),
    "mental_health": ("/salud-mental/", "/psicologia/", "/bienestar/"),
    "nutrition": ("/nutricion/", "/alimentacion/"),
    "fitness": ("/deporte-y-salud/",),
    "public_health": ("/salud-publica/",),
}

# Sections that are never this publication's subject, whatever topic was
# asked for: match reports, celebrity news, horoscopes, lotteries. A link
# filed under one is dropped at discovery, before anything is fetched or
# scored. On 2026-10-05 the labelling batch drew a La Vanguardia
# /deportes/ match report (Barça 7-0 Real Madrid), and the positive-impact
# score - which counts upbeat words - put it above an analysis of Chinese
# industry leaving fossil fuels (0.34 against 0.28). Each entry is a whole
# path segment, so the fitness sections "/sports-health/" and
# "/deporte-y-salud/" do not match.
OFF_MISSION_SECTIONS = (
    "/sport/",
    "/sports/",
    "/deportes/",
    "/deporte/",
    "/futbol/",
    "/football/",
    "/soccer/",
    "/motor/",
    "/motorsport/",
    "/formula1/",
    "/baloncesto/",
    "/tenis/",
    "/gente/",
    "/famosos/",
    "/celebrities/",
    "/celebrity/",
    "/corazon/",
    "/horoscopo/",
    "/horoscope/",
    "/horoscopes/",
    "/loterias/",
    "/loteria/",
    "/lottery/",
    "/apuestas/",
    "/betting/",
    # Forecast pages, not stories: BBC's /weather/<location> came back as
    # Environment candidates from its topic pages on 2026-10-05.
    "/weather/",
    "/el-tiempo/",
)
