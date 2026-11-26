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
    "UEL": ("UEFA Europa League", "uefa.europa", 7, "espn"),
    "UECL": ("UEFA Conference League", "uefa.europa.conf", 7, "espn"),
}

UEFA_CUPS = frozenset(("UCL", "UEL", "UECL"))
# Archived domestic histories used as inputs for the newly approved UEFA cups.
# These leagues are not independently eligible for daily capture or prediction.
CUP_HISTORY_SLUGS = {"en.2": "eng.2", "at.1": "aut.1", "gr.1": "gre.1", "cz.1": "cze.1",
                     "sco.1": "sco.1", "dk.1": "den.1", "se.1": "swe.1",
                     "ch.1": "sui.1", "pl.1": "pol.1", "fi.1": "fin.1", "ro.1": "rou.1"}
CALENDAR_YEAR_LEAGUES = frozenset(("no.1", "se.1", "fi.1"))

# Existing ingestion clients may still explicitly request Championship.
LEGACY_INGESTION = {"en.2": "England Championship"}


def season_bounds(league, day):
    month = APPROVED_LEAGUES[league][2] if league in APPROVED_LEAGUES else 1 if league in CALENDAR_YEAR_LEAGUES else 7
    year = day.year - (day.month < month)
    return date(year, month, 1), date(year - 1, month, 1)


def season_range(league, label):
    year = int(label[:4])
    month = APPROVED_LEAGUES[league][2]
    expected = f"{year}-{(year + 1) % 100:02d}"
    if label != expected and not (month == 1 and label == str(year)):
        raise ValueError("Unexpected league season label")
    return date(year, month, 1), date(year + 1, month, 1)
