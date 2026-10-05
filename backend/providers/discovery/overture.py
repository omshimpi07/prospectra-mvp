"""Overture Maps Discovery Provider via DuckDB GeoParquet.

Connects to remote Overture Places GeoParquet on AWS S3 via DuckDB httpfs,
utilizing spatial bounding-box predicate pushdown to discover business candidates.
"""

import asyncio
import logging
from typing import Any

import duckdb
import httpx

from backend.middleware.errors import AppError
from backend.providers.discovery.base import DiscoveredCandidate
from backend.providers.discovery.taxonomy_map import map_overture_category
from backend.schemas.search import SearchSpecification

logger = logging.getLogger(__name__)

# Fallback release if STAC discovery is unreachable and no release is pinned
FALLBACK_OVERTURE_RELEASE = "2026-09-23.1"


class OvertureDuckDBDiscoveryProvider:
    """DiscoveryProvider implementation using DuckDB against Overture Maps GeoParquet."""

    def __init__(
        self,
        s3_bucket: str = "overturemaps-us-west-2",
        stac_url: str = "https://stac.overturemaps.org/catalog.json",
        pinned_release: str | None = None,
        timeout_seconds: float = 60.0,
        parquet_path_override: str | None = None,
    ) -> None:
        self.s3_bucket = s3_bucket
        self.stac_url = stac_url
        self.pinned_release = pinned_release
        self.timeout_seconds = timeout_seconds
        self.parquet_path_override = parquet_path_override
        self._cached_release: str | None = pinned_release

    async def get_latest_release(self) -> str:
        """Resolve the latest Overture release ID dynamically from STAC catalog."""
        if self._cached_release:
            return self._cached_release

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                res = await client.get(self.stac_url)
                if res.status_code == 200:
                    catalog_data = res.json()
                    # STAC catalog links contain release child catalogs, e.g. "2026-09-23.1"
                    links = catalog_data.get("links", [])
                    child_releases: list[str] = []
                    for link in links:
                        if link.get("rel") == "child" and "href" in link:
                            parts = [
                                p
                                for p in link["href"].strip("/").split("/")
                                if p and not p.endswith(".json")
                            ]
                            if parts:
                                child_releases.append(parts[-1])
                    if child_releases:
                        # Sort to pick the latest release identifier
                        latest = sorted(child_releases, reverse=True)[0]
                        logger.info("Dynamically resolved latest Overture release: %s", latest)
                        self._cached_release = latest
                        return latest
        except Exception as exc:
            logger.warning(
                "Failed to resolve latest Overture release via STAC (%s); using fallback", exc
            )

        self._cached_release = FALLBACK_OVERTURE_RELEASE
        return self._cached_release

    def _sync_query(
        self,
        parquet_path: str,
        min_lon: float,
        max_lon: float,
        min_lat: float,
        max_lat: float,
        limit: int,
    ) -> list[dict[str, Any]]:
        """Synchronously execute DuckDB query with httpfs and bounding box pushdown."""
        con = duckdb.connect(database=":memory:")
        try:
            # Install and configure httpfs for remote S3 access
            con.execute("INSTALL httpfs;")
            con.execute("LOAD httpfs;")
            con.execute("SET s3_region='us-west-2';")

            query = """
                SELECT 
                    id,
                    names.primary AS name,
                    taxonomy.primary AS overture_category,
                    bbox.ymin AS latitude,
                    bbox.xmin AS longitude,
                    addresses[1].freeform AS address,
                    addresses[1].locality AS city,
                    addresses[1].postcode AS postal_code,
                    telephones[1] AS phone,
                    websites[1] AS website,
                    confidence
                FROM read_parquet(?, filename=false, hive_partitioning=1)
                WHERE bbox.xmin BETWEEN ? AND ?
                  AND bbox.ymin BETWEEN ? AND ?
                LIMIT ?;
            """
            result = con.execute(
                query,
                [parquet_path, min_lon, max_lon, min_lat, max_lat, limit * 3],
            ).fetchall()

            columns = [
                "id",
                "name",
                "overture_category",
                "latitude",
                "longitude",
                "address",
                "city",
                "postal_code",
                "phone",
                "website",
                "confidence",
            ]
            rows: list[dict[str, Any]] = [dict(zip(columns, row, strict=False)) for row in result]
            return rows
        finally:
            con.close()

    async def discover_businesses(
        self,
        specification: SearchSpecification,
    ) -> list[DiscoveredCandidate]:
        """Query Overture GeoParquet using DuckDB and return normalized candidate businesses."""
        bbox = specification.bounding_box

        if self.parquet_path_override:
            parquet_path = self.parquet_path_override
        else:
            release = await self.get_latest_release()
            parquet_path = f"s3://{self.s3_bucket}/release/{release}/theme=places/type=place/*"

        try:
            # Execute DuckDB query in a worker thread with timeout
            raw_rows = await asyncio.wait_for(
                asyncio.to_thread(
                    self._sync_query,
                    parquet_path,
                    bbox.min_lon,
                    bbox.max_lon,
                    bbox.min_lat,
                    bbox.max_lat,
                    specification.limit,
                ),
                timeout=self.timeout_seconds,
            )
        except asyncio.TimeoutError as exc:
            logger.error("DuckDB Overture query timed out after %s seconds", self.timeout_seconds)
            raise AppError(
                "DISCOVERY_PROVIDER_TIMEOUT",
                "Overture Places query timed out.",
                status_code=504,
            ) from exc
        except Exception as exc:
            logger.error("DuckDB query failed: %s", exc)
            raise AppError(
                "DISCOVERY_PROVIDER_ERROR",
                f"Discovery provider query failed: {exc}",
                status_code=502,
            ) from exc

        # Process and map candidates against target canonical categories
        target_cats = set(specification.target_categories)
        candidates: list[DiscoveredCandidate] = []

        for row in raw_rows:
            raw_cat = row.get("overture_category")
            canonical_cat = map_overture_category(raw_cat)
            if not canonical_cat or canonical_cat not in target_cats:
                # Place does not match the target canonical categories
                continue

            name = (row.get("name") or "").strip()
            if not name:
                continue

            candidates.append(
                DiscoveredCandidate(
                    external_id=str(row["id"]),
                    name=name,
                    canonical_category=canonical_cat,
                    raw_category=raw_cat,
                    latitude=float(row["latitude"]),
                    longitude=float(row["longitude"]),
                    address=row.get("address"),
                    city=row.get("city") or specification.city,
                    postal_code=row.get("postal_code"),
                    phone=row.get("phone"),
                    website=row.get("website"),
                    confidence=float(row.get("confidence") or 1.0),
                    raw_metadata={"provider": "overture", "release": self._cached_release},
                )
            )

            if len(candidates) >= specification.limit:
                break

        return candidates
