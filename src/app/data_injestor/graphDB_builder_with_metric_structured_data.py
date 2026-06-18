import os
import json
import logging
import pandas as pd
import numpy as np
from datetime import datetime
from config import get_config

try:
    from neo4j import GraphDatabase
    NEO4J_AVAILABLE = True
except ImportError:
    NEO4J_AVAILABLE = False
    print("Neo4j driver not available. Neo4j features will be skipped.")

config = get_config()


class GraphDatabaseBuilder:

    def __init__(self, neo4j_uri=None, neo4j_user=None, neo4j_password=None):
        logging.basicConfig(level=logging.INFO)
        self.logger = logging.getLogger(__name__)

        self.neo4j_driver = None
        if neo4j_uri and neo4j_user and neo4j_password and NEO4J_AVAILABLE:
            try:
                self.neo4j_driver = GraphDatabase.driver(neo4j_uri, auth=(neo4j_user, neo4j_password))
                self.logger.info("Connected to Neo4j database")
            except Exception as e:
                self.logger.error(f"Failed to connect to Neo4j: {e}")

        self.data = {}
        self.processed_data = {}


    # ----------------- CSV loading & cleaning -----------------
    def load_csv_data(self, csv_key, file_path):
        self.logger.info(f"Loading CSV file for '{csv_key}' from {file_path}...")
        encodings = ['utf-8', 'latin-1', 'windows-1252', 'iso-8859-1', 'cp1252']

        df = None
        for encoding in encodings:
            try:
                df = pd.read_csv(file_path, encoding=encoding)
                self.logger.info(f"Successfully loaded '{csv_key}' using {encoding}")
                break
            except Exception:
                continue

        if df is None:
            self.logger.error(f"Could not load CSV file: {file_path}")
            return

        df = self.clean_dataframe(df)
        self.data[csv_key] = df.to_dict('records')
        self.logger.info(f"Loaded {len(self.data[csv_key])} records for '{csv_key}'")

    def clean_dataframe(self, df):
        df.columns = df.columns.str.strip()
        df = df.where(pd.notnull(df), None)
        return df

    # ----------------- Helpers -----------------
    @staticmethod
    def _is_valid_scalar(value) -> bool:
        if value is None:
            return False
        if value == "":
            return False
        if isinstance(value, float) and (np.isnan(value) or np.isinf(value)):
            return False
        return True

    @staticmethod
    def _sanitize_prop_key(key: str) -> str:
        """Neo4j property keys are strings, but for querying it's helpful to keep them simple."""
        if key is None:
            return ""
        key = str(key).strip()
        # Keep underscores, letters, digits. Replace common separators with underscore.
        key = key.replace(" ", "_")
        key = key.replace("-", "_")
        key = key.replace("/", "_")
        key = key.replace(".", "_")
        key = key.replace("%", "Pct")
        return key

    def _add_node(self, label: str, metric_key: str, properties: dict):
        self.processed_data.setdefault('nodes_by_label', {})
        self.processed_data['nodes_by_label'].setdefault(label, {})
        self.processed_data['nodes_by_label'][label][metric_key] = properties

    def _add_relationship(self, rel_type: str, label: str, metric_key: str, ticker: str):
        self.processed_data.setdefault('rels', [])
        self.processed_data['rels'].append({
            'relType': rel_type,
            'label': label,
            'metricKey': metric_key,
            'ticker': ticker,
        })


    # ----------------- Metric nodes (multiple datasets) -----------------
    def build_graph_from_dicts_for_metric_data(self, ticker: str, csv_key: str):
        """Build graph-ready node/rel batches for ONE uploaded metrics CSV.

        New structure (requested):
          Row-based datasets are stored under shared labels:
            - :Metric (historical)
            - :MetricPredicted (predicted)
          Single-node datasets remain dataset-specific:
            - :Metric_ValuationForecastDriverValues
            - :Metric_ValuationSummary

        """

        self.logger.info(f"Building graph from dictionary data for dataset '{csv_key}'...")

        if csv_key not in self.data:
            self.logger.warning(f"No data loaded for '{csv_key}'. Skipping.")
            return

        current_year = datetime.now().year
        records = self.data[csv_key]

        # ------------------------
        # MultiplesTable (single node; store {Type, Value} under each property)
        # ------------------------
        if csv_key == "MultiplesTable":
            label = "Metric_MultiplesTable"
            metric_key = f"MultiplesTable:{ticker}"
            props: dict = {
                "ticker": ticker,
                "metricName": "MultiplesTable",
            }

            def _coerce_value(v):
                # Keep strings like "Call_API" but convert numeric strings to float.
                if v is None:
                    return None
                if isinstance(v, str):
                    s = v.strip()
                    if s == "":
                        return None
                    try:
                        return float(s)
                    except Exception:
                        return s
                # numeric
                try:
                    if isinstance(v, float) and (np.isnan(v) or np.isinf(v)):
                        return None
                except Exception:
                    pass
                return v

            for record in records:
                if not isinstance(record, dict) or not record:
                    continue
                name = record.get("Name")
                if name is None:
                    # fallback to first column
                    first_key = list(record.keys())[0]
                    name = record.get(first_key)

                if not self._is_valid_scalar(name):
                    continue

                prop_name = self._sanitize_prop_key(name)
                type_v = record.get("Type")
                value_v = _coerce_value(record.get("Value"))

                # Store "Type" and "Value" as a JSON-encoded dict (Neo4j properties cannot store maps).
                props[prop_name] = {
                    "Type": type_v,
                    "Value": value_v,
                }

            self._add_node(label, metric_key, props)
            self._add_relationship("HAS_MULTIPLES_TABLE", label, metric_key, ticker)
            self.logger.info(f"Prepared MultiplesTable node with {len(props)} properties")
            return

        # ------------------------
        # Row-based datasets
        # ------------------------




        # Dataset storage rules (requested):
        #   - 3StatementModel: historical + predicted + DriverValue
        #   - FreeCashFlows: historical + predicted
        #   - InvestedCapital: historical + predicted
        #   - Performance: historical + predicted
        #   - HistoricalCagrAvg: PERF_AVG_COLS and PERF_CAGR_COLS only (no years)
        #   - ExtractedItems: historical year values only
        #   - ReportedFinancials: statementType + historical year values
        row_based_with_predicted = {"3StatementModel", "InvestedCapital", "Performance", "FreeCashFlows"}
        row_based_predicted_only = set()
        row_based_historical_only = {"ExtractedItems", "ReportedFinancials"}
        extras_only_no_years = {"HistoricalCagrAvg"}

        # HistoricalCagrAvg-derived columns to keep (Last* AVG/CAGR)
        PERF_AVG_COLS = {
            "Last1Y_AVG",
            "Last2Y_AVG",
            "Last3Y_AVG",
            "Last4Y_AVG",
            "Last5Y_AVG",
            "Last10Y_AVG",
            "Last15Y_AVG",
        }
        PERF_CAGR_COLS = {
            "Last1Y_CAGR",
            "Last2Y_CAGR",
            "Last3Y_CAGR",
            "Last4Y_CAGR",
            "Last5Y_CAGR",
            "Last10Y_CAGR",
            "Last15Y_CAGR",
        }

        if (
            csv_key in row_based_with_predicted
            or csv_key in row_based_predicted_only
            or csv_key in row_based_historical_only
            or csv_key in extras_only_no_years
        ):
            # IMPORTANT: all row-based historical metrics go into :Metric
            #            all row-based predicted metrics go into :MetricPredicted
            base_label = "Metric"
            predicted_label = "MetricPredicted"

            for record in records:
                first_key = list(record.keys())[0]
                metric_name = record.get(first_key)
                if not metric_name:
                    continue

                metric_name = str(metric_name).strip()
                statement_type = record.get('statementType')

                # Common properties
                common_props = {
                    'ticker': ticker,
                    'metricName': metric_name,
                }
                if statement_type is not None:
                    common_props['statementType'] = statement_type

                # Extra non-year columns to keep (DriverValue in 3StatementModel)
                extra_props = {}
                if csv_key == "3StatementModel":
                    if self._is_valid_scalar(record.get('DriverValue')):
                        extra_props['DriverValue'] = record.get('DriverValue')

                # HistoricalCagrAvg extra columns to keep (Last* AVG/CAGR)
                # NOTE: These are NOT year columns, but we want them stored as well.
                if csv_key == "HistoricalCagrAvg":
                    for k, v in record.items():
                        if not isinstance(k, str):
                            continue
                        if k in PERF_AVG_COLS or k in PERF_CAGR_COLS:
                            if self._is_valid_scalar(v):
                                extra_props[k] = v

                # Historical node
                # IMPORTANT: Merge across datasets by using metricKey that does NOT include datasetKey.
                # This means the same (ticker, metricName) from different CSVs will be merged into 1 node.
                hist_metric_key = f"{ticker}:{metric_name}"
                hist_props = dict(common_props)
                hist_props.update(extra_props)

                # Predicted node (only for the datasets that require it)
                pred_metric_key = f"{ticker}:{metric_name}:predicted"
                pred_props = dict(common_props)
                pred_props.update(extra_props)

                has_hist = False
                has_pred = False

                # HistoricalCagrAvg stores only the Last* columns (no years)
                if csv_key in extras_only_no_years:
                    if extra_props:
                        self._add_node(base_label, hist_metric_key, hist_props)
                        self._add_relationship('HAS_METRIC', base_label, hist_metric_key, ticker)
                    continue

                for k, v in record.items():
                    if not (isinstance(k, str) and k.isdigit() and len(k) == 4):
                        continue
                    if not self._is_valid_scalar(v):
                        continue
                    year = int(k)

                    # ReportedFinancials + ExtractedItems: historical only
                    if csv_key in row_based_historical_only:
                        if csv_key == "ReportedFinancials" and year >= current_year:
                            continue
                        hist_props[f"year_{k}"] = v
                        has_hist = True
                        continue

                    # All other row_based_with_predicted: split by current_year
                    if year < current_year:
                        hist_props[f"year_{k}"] = v
                        has_hist = True
                    else:
                        pred_props[f"year_{k}"] = v
                        has_pred = True

                if has_hist:
                    self._add_node(base_label, hist_metric_key, hist_props)
                    self._add_relationship('HAS_METRIC', base_label, hist_metric_key, ticker)

                if (csv_key in row_based_with_predicted or csv_key in row_based_predicted_only) and has_pred:
                    self._add_node(predicted_label, pred_metric_key, pred_props)
                    self._add_relationship('HAS_PREDICTED_METRIC', predicted_label, pred_metric_key, ticker)

            self.logger.info(
                f"Prepared nodes for '{csv_key}': "
                f"{len(self.processed_data.get('nodes_by_label', {}).get(base_label, {}))} historical rows, "
                f"{len(self.processed_data.get('nodes_by_label', {}).get(predicted_label, {})) if csv_key in row_based_with_predicted else 0} predicted rows"
            )
            return

        # ------------------------
        # ValuationForecastDriverValues (single node; use first row only)
        # ------------------------
        if csv_key == "ValuationForecastDriverValues":
            label = "Metric_ValuationForecastDriverValues"
            if not records:
                return
            first_row = records[0]
            metric_key = f"ValuationForecastDriverValues:{ticker}"
            props = {
                'ticker': ticker,
                'metricName': 'ValuationForecastDriverValues',
            }
            # Keep extraction time if present
            if self._is_valid_scalar(first_row.get('ExtractionTime')):
                props['ExtractionTime'] = first_row.get('ExtractionTime')

            for k, v in first_row.items():
                if k == 'ExtractionTime':
                    continue
                if not self._is_valid_scalar(v):
                    continue
                props[self._sanitize_prop_key(k)] = v

            self._add_node(label, metric_key, props)
            self._add_relationship('HAS_VALUATION_FORECAST_DRIVER_VALUES', label, metric_key, ticker)
            self.logger.info(f"Prepared ValuationForecastDriverValues node with {len(props)} properties")
            return

        # ------------------------
        # ValuationSummary (single node; flatten rows)
        # ------------------------
        if csv_key == "ValuationSummary":
            label = "Metric_ValuationSummary"
            metric_key = f"ValuationSummary:{ticker}"
            props = {
                'ticker': ticker,
                'metricName': 'ValuationSummary',
            }

            for record in records:
                row_name_key = list(record.keys())[0]
                row_name = record.get(row_name_key)
                if not row_name:
                    continue
                row_name = self._sanitize_prop_key(row_name)
                for col, v in record.items():
                    if col == row_name_key:
                        continue
                    if not self._is_valid_scalar(v):
                        continue
                    col_s = self._sanitize_prop_key(col)
                    prop_key = f"{row_name}_{col_s}"
                    props[prop_key] = v

            self._add_node(label, metric_key, props)
            self._add_relationship('HAS_VALUATION_SUMMARY', label, metric_key, ticker)
            self.logger.info(f"Prepared ValuationSummary node with {len(props)} properties")
            return

        self.logger.warning(
            f"Unsupported csv_key '{csv_key}'. Expected one of: "
            "3StatementModel, FreeCashFlows, ReportedFinancials, InvestedCapital, Performance, HistoricalCagrAvg, "
            "ValuationForecastDriverValues, ValuationSummary"
        )


    # ----------------- Metric nodes batch (new multi-dataset labels) -----------------
    def create_neo4j_nodes_batch(self):
        if not self.neo4j_driver:
            return

        nodes_by_label = self.processed_data.get('nodes_by_label', {})
        if not nodes_by_label:
            return

        # Create nodes label-by-label (Cypher doesn't allow parameterized labels)
        for label, nodes in nodes_by_label.items():
            batch = []
            for metric_key, props in nodes.items():
                batch.append({
                    'metricKey': metric_key,
                    'properties': self.clean_properties_for_neo4j(props)
                })

            if not batch:
                continue

            query = f"""
            UNWIND $batch AS item
            MERGE (n:`{label}` {{metricKey: item.metricKey}})
            SET n += item.properties
            """
            with self.neo4j_driver.session() as session:
                session.run(query, batch=batch)
            self.logger.info(f"Created/updated {len(batch)} nodes with label :{label}")

    # ----------------- Clean properties -----------------
    def clean_properties_for_neo4j(self, properties):
        cleaned = {}
        for key, value in properties.items():
            if value is None:
                continue
            if isinstance(value, dict):
                cleaned[key] = json.dumps(value, ensure_ascii=False)
            elif not (isinstance(value, float) and (np.isnan(value) or np.isinf(value))):
                if isinstance(value, np.integer):
                    cleaned[key] = int(value)
                elif isinstance(value, np.floating):
                    cleaned[key] = float(value)
                elif isinstance(value, np.bool_):
                    cleaned[key] = bool(value)
                else:
                    cleaned[key] = value
        return cleaned

    # ----------------- Company → (all new metric node types) -----------------
    def create_neo4j_relationships_batch(self, ticker):
        if not self.neo4j_driver:
            return

        rels = self.processed_data.get('rels', [])
        if not rels:
            return

        # Group by (label, relType) because label is used in Cypher MATCH
        grouped: dict[tuple[str, str], list[dict]] = {}
        for r in rels:
            grouped.setdefault((r['label'], r['relType']), []).append(r)

        for (label, rel_type), batch_rels in grouped.items():
            query = f"""
            UNWIND $batch AS item
            MATCH (c:Company {{ticker: item.ticker}})
            MATCH (n:`{label}` {{metricKey: item.metricKey}})
            MERGE (c)-[:{rel_type}]->(n)
            """
            with self.neo4j_driver.session() as session:
                session.run(query, batch=batch_rels)
            self.logger.info(f"Created {len(batch_rels)} relationships :{rel_type} to nodes :{label}")

    # ----------------- Sync all -----------------
    def sync_to_neo4j(self, ticker):
        if not self.neo4j_driver:
            self.logger.warning("Neo4j driver not available")
            return

        self.logger.info("Syncing data to Neo4j...")
        self.create_neo4j_nodes_batch()                # all dataset-specific nodes
        self.create_neo4j_relationships_batch(ticker)  # Company relationships
        self.logger.info("Neo4j sync completed!")

    def close(self):
        if self.neo4j_driver:
            self.neo4j_driver.close()


# ----------------- Helper function -----------------
def store_structured_metric_data(file_path, csv_key, ticker):
    response = {
        "status": "success",
        "message": "",
        "error": None,
        "http_status": 200
    }
    try:
        builder = GraphDatabaseBuilder(
            neo4j_uri=config.NEO4J_URI,
            neo4j_user=config.NEO4J_USERNAME,
            neo4j_password=config.NEO4J_PASSWORD
        )
    except Exception as e:
        response["status"] = "error"
        response["error"] = f"Failed to initialize Neo4j: {e}"
        response["http_status"] = 500
        return response
    
    # Expected new keys (validated at the router layer)
    valid_keys = {
        "3StatementModel",
        "FreeCashFlows",
        "ReportedFinancials",
        "InvestedCapital",
        "Performance",
        "HistoricalCagrAvg",
        "ExtractedItems",
        "ValuationForecastDriverValues",
        "ValuationSummary",
        "MultiplesTable",
    }
    key = csv_key
    if key not in valid_keys:
        return {
            "status": "error",
            "message": "",
            "error": f"Invalid key '{csv_key}'. Allowed keys: {', '.join(sorted(valid_keys))}",
            "http_status": 400
        }
    try:
        builder.load_csv_data(key, file_path)

        if key not in builder.data:
            return {
                "status": "error",
                "message": "",
                "error": f"Failed to load CSV content. Possibly corrupted file: '{os.path.basename(file_path)}'",
                "http_status": 500
            }
        
        # Build graph-ready batches for this dataset
        builder.build_graph_from_dicts_for_metric_data(ticker, key)
        builder.sync_to_neo4j(ticker)

    except Exception as e:
        return {
            "status": "error",
            "message": "",
            "error": f"Backend error while processing '{os.path.basename(file_path)}': {str(e)}",
            "http_status": 500
        }

    finally:
        builder.close()

    response["message"] = f"File '{os.path.basename(file_path)}' processed successfully"
    return response
