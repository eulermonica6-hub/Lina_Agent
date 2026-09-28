import tomllib
from importlib.resources import files

from pydantic import TypeAdapter

from lina_agent.domain.weekly_monitoring import MonitoredJobSource


def load_company_catalog(catalog_text: str) -> tuple[MonitoredJobSource, ...]:
    catalog = tomllib.loads(catalog_text)
    if catalog.get("schema_version") != 1:
        raise ValueError("Unsupported company catalog schema version")

    sources = TypeAdapter(tuple[MonitoredJobSource, ...]).validate_python(catalog.get("companies"))
    if len({source.source_id for source in sources}) != len(sources):
        raise ValueError("Company catalog source_id values must be unique")
    if len({source.company.casefold() for source in sources}) != len(sources):
        raise ValueError("Company catalog company names must be unique")
    return sources


_CATALOG_RESOURCE = files("lina_agent.infrastructure.job_sources").joinpath("company_catalog.toml")
MONITORED_JOB_SOURCES = load_company_catalog(_CATALOG_RESOURCE.read_text(encoding="utf-8"))
