from __future__ import annotations

import json
from pathlib import Path
import time
from urllib.request import Request, urlopen


CITY_CATALOG_URL = "https://www.zhipin.com/wapi/zpCommon/data/cityGroup.json"
CITY_CACHE_PATH = Path("data/recruitment_city_catalog.json")
CITY_CACHE_TTL_SECONDS = 7 * 24 * 3600

FALLBACK_CITIES = {
    "北京": "101010100", "上海": "101020100", "广州": "101280100",
    "深圳": "101280600", "杭州": "101210100", "南京": "101190100",
    "成都": "101270100", "武汉": "101200100", "西安": "101110100",
    "合肥": "101220100", "苏州": "101190400", "长沙": "101250100",
}


def recruitment_city_catalog(*, refresh: bool = False) -> dict[str, str]:
    """Return platform city names and BOSS city codes, excluding the nationwide pseudo-city."""
    if not refresh:
        cached = _read_cache()
        if cached:
            return cached

    try:
        request = Request(CITY_CATALOG_URL, headers={"User-Agent": "Mozilla/5.0"})
        with urlopen(request, timeout=15) as response:
            payload = json.load(response)
        groups = payload.get("zpData", {}).get("cityGroup", [])
        cities = {
            str(city["name"]).strip(): str(city["code"])
            for group in groups
            for city in group.get("cityList", [])
            if city.get("name") and city.get("code")
        }
        if cities:
            _write_cache(cities)
            return cities
    except (OSError, ValueError, KeyError, TypeError):
        pass
    return dict(FALLBACK_CITIES)


def _read_cache() -> dict[str, str]:
    try:
        if time.time() - CITY_CACHE_PATH.stat().st_mtime > CITY_CACHE_TTL_SECONDS:
            return {}
        value = json.loads(CITY_CACHE_PATH.read_text(encoding="utf-8"))
        return {str(name): str(code) for name, code in value.items() if name and code}
    except (OSError, ValueError, TypeError):
        return {}


def _write_cache(cities: dict[str, str]) -> None:
    CITY_CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    temporary = CITY_CACHE_PATH.with_suffix(".tmp")
    temporary.write_text(json.dumps(cities, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(CITY_CACHE_PATH)
