"""Search and filter rules shared by the map page and the JSON API (E01 US02–US05).

Every filter reads an official NYC Open Data field (see the E01 Data and Field
Mapping wiki page). Filters combine with AND, and leaving a parameter blank
removes that filter.
"""
from urllib.parse import urlencode

from django.db.models import Q

from .models import Hotspot

# Fields matched by the free-text location search (US02): landmark/site name,
# street address or description, neighborhood, borough and ZIP code.
SEARCH_FIELDS = [
    "name",
    "location_description",
    "neighborhood_name",
    "borough",
    "zip_code",
]

# URL parameter -> (model field, label shown to people).
FILTERS = {
    "borough": ("borough", "Borough"),  # US03, source column boroname
    "neighborhood": ("neighborhood_name", "Neighborhood"),  # US03, 2010 NTA name
    "provider": ("provider", "Provider"),  # US04
    "type": ("access_type", "Access type"),  # US05, source column type
}

PARAMETERS = ["q", *FILTERS]
MAX_QUERY_LENGTH = 100


def read_params(params):
    """Return the cleaned search/filter values from a QueryDict, blanks removed."""
    values = {}
    query = " ".join(params.get("q", "").split())[:MAX_QUERY_LENGTH]
    if query:
        values["q"] = query
    for name in FILTERS:
        value = params.get(name, "").strip()
        if value:
            values[name] = value
    return values


def apply_filters(queryset, values):
    """Narrow a Hotspot queryset with the values returned by read_params."""
    query = values.get("q")
    if query:
        # Each word must appear in at least one location field, so
        # "bryant park" and "park bryant" both find Bryant Park.
        for word in query.split():
            match = Q()
            for field in SEARCH_FIELDS:
                match |= Q(**{f"{field}__icontains": word})
            queryset = queryset.filter(match)
    for name, (field, _label) in FILTERS.items():
        if name in values:
            queryset = queryset.filter(**{f"{field}__iexact": values[name]})
    return queryset


def filter_options(queryset):
    """Choices for each dropdown, built from every active hotspot (not only the
    current results) so a filter can always be changed to another value."""
    def distinct(field):
        return list(
            queryset.exclude(**{field: ""})
            .order_by(field)
            .values_list(field, flat=True)
            .distinct()
        )

    neighborhoods = {}
    for borough, neighborhood in (
        queryset.exclude(neighborhood_name="")
        .order_by("borough", "neighborhood_name")
        .values_list("borough", "neighborhood_name")
        .distinct()
    ):
        neighborhoods.setdefault(borough, []).append(neighborhood)

    present_types = set(distinct("access_type"))
    return {
        "borough": distinct("borough"),
        "neighborhood": [
            {"borough": borough, "names": names} for borough, names in neighborhoods.items()
        ],
        "provider": distinct("provider"),
        "type": [value for value, _ in Hotspot.AccessType.choices if value in present_types],
    }


def active_filter_chips(values, base_url):
    """One removable chip per applied search/filter, each linking to the same
    results without that one value."""
    chips = []
    for name in PARAMETERS:
        if name not in values:
            continue
        remaining = {key: value for key, value in values.items() if key != name}
        label = "Search" if name == "q" else FILTERS[name][1]
        chips.append({
            "name": name,
            "label": label,
            "value": values[name],
            "remove_url": f"{base_url}?{urlencode(remaining)}" if remaining else base_url,
        })
    return chips
