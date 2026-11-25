"""User-approved competitions, their season boundaries and score providers."""

from datetime import date

# Names and provider slugs are stable identifiers. The month defines which
# results belong to a season, rather than the date of its first fixture.
APPROVED_LEAGUES = {
    "tr.1": ("Türkiye Süper Lig", "tur.1", 7, "openfootball"),
    "en.1": ("England Premier League", "eng.1", 7, "openfootball"),
    "de.1": ("Germany Bundesliga", "ger.1", 7, "openfootball"),
    "de.2": ("Germany Bundesliga 2", "ger.2", 7, "openfootball"),
    "es.1": ("Spain La Liga", "esp.1", 7, "openfootball"),
    "it.1": ("Italy Serie A", "ita.1", 7, "openfootball"),
    "fr.1": ("France Ligue 1", "fra.1", 7, "openfootball"),
    "nl.1": ("Netherlands Eredivisie", "ned.1", 7, "openfootball"),
    "nl.2": ("Netherlands Eerste Divisie", "ned.2", 7, "espn"),
    "pt.1": ("Portugal Primeira Liga", "por.1", 7, "openfootball"),
    "be.1": ("Belgium Pro League", "bel.1", 7, "openfootball"),
    "no.1": ("Norway Eliteserien", "nor.1", 1, "espn"),
    "UCL": ("UEFA Champions League", "uefa.champions", 7, "espn"),
}

# Existing ingestion clients may still explicitly request Championship.
LEGACY_INGESTION = {"en.2": "England Championship"}


def season_bounds(league, day):
    month = APPROVED_LEAGUES[league][2] if league in APPROVED_LEAGUES else 7
    year = day.year - (day.month < month)
    return date(year, month, 1), date(year - 1, month, 1)


def season_range(league, label):
    year = int(label[:4])
    month = APPROVED_LEAGUES[league][2]
    expected = f"{year}-{(year + 1) % 100:02d}"
    if label != expected and not (month == 1 and label == str(year)):
        raise ValueError("Unexpected league season label")
    return date(year, month, 1), date(year + 1, month, 1)
