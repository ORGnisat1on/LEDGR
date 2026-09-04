"""
Module 1 — Data Ingestion

Per ARCHITECTURE.md:
- Gets transaction graph data into a common internal format from two distinct sources
- Elliptic/Elliptic++ static dataset (CSV/Parquet, Kaggle) — training and evaluation
- Live public Bitcoin block-explorer API (Blockstream.info, BlockCypher free tier) — demo-time tracing

Outputs two artifacts:
1. Normalized record stream (downstream interface for Modules 2, 3a, 3b)
2. Internal transaction index (for Module 5 clustering)
"""

from .types import (
    NormalizedRecord,
    InternalTx,
    TxIn,
    TxOut,
    SourceType,
    DirectionType,
)

from .elliptic_ingest import (
    EllipticIngestor,
    ingest_elliptic_dataset,
)

from .blockstream_client import (
    BlockstreamClient,
    BlockstreamConfig,
    fetch_address_data_blockstream,
)

from .blockcypher_client import (
    BlockCypherClient,
    BlockCypherConfig,
    fetch_address_data_blockcypher,
)

from .pipeline import (
    IngestionPipeline,
    IngestionConfig,
    DataSource,
    create_pipeline,
    ingest_training_data,
    ingest_reported_address,
)

__all__ = [
    # Types
    "NormalizedRecord",
    "InternalTx",
    "TxIn",
    "TxOut",
    "SourceType",
    "DirectionType",

    # Elliptic ingestion
    "EllipticIngestor",
    "ingest_elliptic_dataset",

    # Blockstream client
    "BlockstreamClient",
    "BlockstreamConfig",
    "fetch_address_data_blockstream",

    # BlockCypher client
    "BlockCypherClient",
    "BlockCypherConfig",
    "fetch_address_data_blockcypher",

    # Pipeline
    "IngestionPipeline",
    "IngestionConfig",
    "DataSource",
    "create_pipeline",
    "ingest_training_data",
    "ingest_reported_address",
]

__version__ = "0.1.0"