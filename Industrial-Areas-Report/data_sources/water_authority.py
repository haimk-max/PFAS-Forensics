"""
Water Authority Data Source
Connects to Israel Water Authority data via data.gov.il CKAN API
"""

import requests
import pandas as pd
from datetime import datetime
from typing import Dict, List, Optional
from ckanapi import RemoteCKAN


class WaterAuthorityDataSource:
    """Fetch water quality data from Israel Water Authority via data.gov.il"""

    def __init__(self, api_url: str = "https://data.gov.il"):
        """
        Initialize connection to data.gov.il

        Args:
            api_url: Base URL for data.gov.il API
        """
        self.api_url = api_url
        self.client = RemoteCKAN(api_url)
        self.dataset_id = "borehole_quality_history"

    def get_dataset_metadata(self) -> Dict:
        """Get metadata about the borehole quality history dataset"""
        try:
            return self.client.action.package_show(id=self.dataset_id)
        except Exception as e:
            print(f"Error fetching dataset metadata: {e}")
            return {}

    def get_borehole_data(
        self,
        industrial_area: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        limit: int = 1000
    ) -> pd.DataFrame:
        """
        Fetch borehole water quality data

        Args:
            industrial_area: Filter by industrial area name
            start_date: Start date (YYYY-MM-DD format)
            end_date: End date (YYYY-MM-DD format)
            limit: Maximum number of records

        Returns:
            DataFrame with borehole data
        """
        try:
            # Get resource ID from dataset
            dataset = self.client.action.package_show(id=self.dataset_id)
            if not dataset.get("resources"):
                print("No resources found in dataset")
                return pd.DataFrame()

            resource_id = dataset["resources"][0]["id"]

            # Build query filters
            filters = {}
            if industrial_area:
                filters["industrial_area"] = industrial_area
            if start_date:
                filters["date"] = {">=": start_date}
            if end_date:
                filters["date"] = {"<=": end_date}

            # Query datastore
            result = self.client.action.datastore_search(
                resource_id=resource_id,
                limit=limit,
                filters=filters if filters else None
            )

            # Convert to DataFrame
            if result.get("records"):
                df = pd.DataFrame(result["records"])
                return df
            else:
                print(f"No records found for {industrial_area or 'all areas'}")
                return pd.DataFrame()

        except Exception as e:
            print(f"Error fetching borehole data: {e}")
            return pd.DataFrame()

    def get_raanana_data(self) -> pd.DataFrame:
        """Fetch data specifically for Raanana industrial area"""
        return self.get_borehole_data(industrial_area="raanana")

    def get_boreholes_by_area(self, area_name: str) -> List[Dict]:
        """Get list of monitoring boreholes in specific area"""
        try:
            dataset = self.client.action.package_show(id=self.dataset_id)
            resource_id = dataset["resources"][0]["id"]

            result = self.client.action.datastore_search(
                resource_id=resource_id,
                filters={"area": area_name},
                limit=500
            )

            # Extract unique boreholes
            boreholes = []
            if result.get("records"):
                df = pd.DataFrame(result["records"])
                boreholes = df.groupby("borehole_id").agg({
                    "latitude": "first",
                    "longitude": "first",
                    "depth": "first"
                }).reset_index().to_dict("records")

            return boreholes

        except Exception as e:
            print(f"Error fetching boreholes: {e}")
            return []

    def get_parameter_trend(
        self,
        borehole_id: str,
        parameter: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> pd.DataFrame:
        """
        Get time series data for specific parameter in a borehole

        Args:
            borehole_id: Borehole identifier
            parameter: Parameter name (e.g., 'TCE', 'Chlorides')
            start_date: Start date
            end_date: End date

        Returns:
            DataFrame with date and parameter values
        """
        try:
            dataset = self.client.action.package_show(id=self.dataset_id)
            resource_id = dataset["resources"][0]["id"]

            filters = {"borehole_id": borehole_id, "parameter": parameter}

            result = self.client.action.datastore_search(
                resource_id=resource_id,
                filters=filters,
                limit=5000,
                sort="date asc"
            )

            if result.get("records"):
                df = pd.DataFrame(result["records"])
                df["date"] = pd.to_datetime(df["date"])
                df["value"] = pd.to_numeric(df["value"], errors="coerce")
                return df[["date", "value"]].dropna()
            else:
                return pd.DataFrame(columns=["date", "value"])

        except Exception as e:
            print(f"Error fetching parameter trend: {e}")
            return pd.DataFrame()
