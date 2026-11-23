"""Search and filter rules shared by the map page and the JSON API (E01 US02–US05).

Every filter reads an official NYC Open Data field (see the E01 Data and Field
Mapping wiki page). Filters combine with AND, and leaving a parameter blank
removes that filter.
"""

from urllib.parse import urlencode

from django.db.models import Q

from .models import Hotspot
from .sorting import SORTS

# Fields matched by the free-text location search (US02): landmark/site name,
# provider (also used in display names), address, neighborhood, borough and ZIP.
SEARCH_FIELDS = [
    "name",
    "provider",
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
    if "borough" in values and "neighborhood" in values:
        # A shared link or a borough change can carry the previous neighborhood.
        boroughs = (
            Hotspot.objects.filter(
                is_active=True, neighborhood_name__iexact=values["neighborhood"]
            )
            .order_by()
            .values_list("borough", flat=True)
            .distinct()
        )
        owners = {borough.casefold() for borough in boroughs}
        if owners and values["borough"].casefold() not in owners:
            del values["neighborhood"]
    sort = params.get("sort", "").strip()
    if sort in SORTS:
        values["sort"] = sort  # US24; not a filter, so it never narrows results
    return values


def apply_filters(queryset, values):
    """Narrow a Hotspot queryset with the values returned by read_params."""
    query = values.get("q")
    if query:
        # Each word must appear in at least one location field, so
        # "bryant park" and "park bryant" both find Bryant Park.
        for word in query.replace(" — ", " ").split():
            match = Q()
            for field in SEARCH_FIELDS:
                match |= Q(**{f"{field}__icontains": word})
            queryset = queryset.filter(match)
    for name, (field, _label) in FILTERS.items():
        if name in values:
            queryset = queryset.filter(**{f"{field}__iexact": values[name]})
    return queryset


def filter_options(queryset, borough=None):
    """Neighborhoods belong to the selected borough; other choices stay citywide."""

    def distinct(field):
        return list(
            queryset.exclude(**{field: ""})
            .order_by(field)
            .values_list(field, flat=True)
            .distinct()
        )

    locations = queryset.filter(borough__iexact=borough) if borough else queryset
    neighborhoods = {}
    for borough, neighborhood in (
        locations.exclude(neighborhood_name="")
        .order_by("borough", "neighborhood_name")
        .values_list("borough", "neighborhood_name")
        .distinct()
    ):
        neighborhoods.setdefault(borough, []).append(neighborhood)

    present_types = set(distinct("access_type"))
    return {
        "borough": distinct("borough"),
        "neighborhood": [
            {"borough": borough, "names": names}
            for borough, names in neighborhoods.items()
        ],
        "provider": distinct("provider"),
        "type": [
            value for value, _ in Hotspot.AccessType.choices if value in present_types
        ],
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
        chips.append(
            {
                "name": name,
                "label": label,
                "value": values[name],
                "remove_url": (
                    f"{base_url}?{urlencode(remaining)}" if remaining else base_url
                ),
            }
        )
    return chips
