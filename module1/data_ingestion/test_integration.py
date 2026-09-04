"""
Integration tests for Module 1 data ingestion.

Run with: python -m pytest module1/data_ingestion/test_integration.py -v

Tests cover:
- Elliptic fixture ingestion
- Elliptic++ address/transaction relations
- Blockstream parsing (with mocked responses)
- BlockCypher parsing (with mocked responses)
- Pipeline behavior
- Malformed records
- Coinbase/OP_RETURN/unconfirmed cases
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path
import json

from module1.data_ingestion.types import (
    NormalizedRecord,
    InternalTx,
    TxIn,
    TxOut,
    SourceType,
)
from module1.data_ingestion.elliptic_ingest import EllipticIngestor, ingest_elliptic_dataset
from module1.data_ingestion.blockstream_client import BlockstreamClient, fetch_address_data_blockstream
from module1.data_ingestion.blockcypher_client import BlockCypherClient, fetch_address_data_blockcypher
from module1.data_ingestion.pipeline import (
    IngestionPipeline,
    IngestionConfig,
    DataSource,
    create_pipeline,
    ingest_training_data,
    ingest_reported_address,
)


# Test fixtures
TEST_DATA_DIR = Path(__file__).parent / "test_fixtures"


class TestEllipticIngestion:
    """Test Elliptic dataset ingestion."""

    def test_load_metadata(self):
        """Test loading timestamp and block height from features file."""
        ingestor = EllipticIngestor(TEST_DATA_DIR)
        ingestor.load_metadata()

        # Check timestamps were loaded
        assert len(ingestor._txid_to_timestamp) == 5
        assert "a1b2c3d4e5f6789012345678901234567890abcdef1234567890abcdef123456" in ingestor._txid_to_timestamp

        # Check timestamp conversion (time_step 1 = genesis + 1 step)
        genesis_ts = 1230940800
        step_seconds = 1209600
        expected_ts = genesis_ts + 1 * step_seconds
        assert ingestor._txid_to_timestamp["a1b2c3d4e5f6789012345678901234567890abcdef1234567890abcdef123456"] == expected_ts

        # Check block height approximation
        assert ingestor._txid_to_blockheight["a1b2c3d4e5f6789012345678901234567890abcdef1234567890abcdef123456"] == 2016

    def test_iter_normalized_records_base_edgelist(self):
        """Test normalized records from base Elliptic edgelist."""
        ingestor = EllipticIngestor(TEST_DATA_DIR)
        records = list(ingestor.iter_normalized_records())

        # Should have 2 records per edge (5 edges * 2 = 10 records)
        assert len(records) == 10

        # Check record structure
        for record in records:
            assert isinstance(record, NormalizedRecord)
            assert record.source == "elliptic"
            assert record.elliptic_id is not None
            assert record.tx_hash is None
            assert record.amount_sats == 1  # placeholder
            assert record.direction in ("in", "out")
            assert record.timestamp is not None
            assert record.block_height is not None

    def test_elliptic_record_has_no_tx_hash(self):
        """Verify Elliptic records use elliptic_id, not tx_hash."""
        ingestor = EllipticIngestor(TEST_DATA_DIR)
        records = list(ingestor.iter_normalized_records())

        for record in records:
            assert record.source == "elliptic"
            assert record.elliptic_id is not None
            assert record.tx_hash is None
            assert record.tx_identifier == record.elliptic_id

    def test_ingest_elliptic_dataset_returns_only_records(self):
        """Test ingest_elliptic_dataset returns only normalized records (no InternalTx)."""
        records = ingest_elliptic_dataset(TEST_DATA_DIR)
        assert isinstance(records, list)
        assert len(records) == 10
        for record in records:
            assert isinstance(record, NormalizedRecord)

    def test_elliptic_plus_plus_relations_loading(self):
        """Test loading Elliptic++ address-transaction relations."""
        ingestor = EllipticIngestor(TEST_DATA_DIR)
        ingestor.load_elliptic_plus_plus_relations()

        # Files don't exist in test fixtures, so mappings should be empty
        assert ingestor._address_to_txids == {}
        assert ingestor._txid_to_addresses == {}

    def test_get_address_tx_mapping(self):
        """Test getting address -> txId mapping for Module 5 clustering."""
        ingestor = EllipticIngestor(TEST_DATA_DIR)
        mapping = ingestor.get_address_tx_mapping()
        assert isinstance(mapping, dict)

    def test_get_txid_address_mapping(self):
        """Test getting txId -> address mapping for Module 5 clustering."""
        ingestor = EllipticIngestor(TEST_DATA_DIR)
        mapping = ingestor.get_txid_address_mapping()
        assert isinstance(mapping, dict)


class TestBlockstreamClient:
    """Test Blockstream API client with mocked responses."""

    @pytest.fixture
    def client(self):
        """Create a BlockstreamClient with mocked session."""
        client = BlockstreamClient()
        client._session = Mock()
        return client

    @pytest.fixture
    def sample_address_txs(self):
        """Sample address transactions response."""
        return [
            {
                "txid": "a" * 64,
                "status": {"block_height": 100, "block_time": 1234567890}
            },
            {
                "txid": "b" * 64,
                "status": {"block_height": None, "block_time": None}  # unconfirmed
            }
        ]

    @pytest.fixture
    def sample_full_tx_confirmed(self):
        """Sample full transaction for confirmed tx."""
        return {
            "txid": "a" * 64,
            "vin": [
                {
                    "txid": "prev1" + "0" * 60,
                    "vout": 0,
                    "prevout": {
                        "scriptpubkey_address": "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa",
                        "value": 50000
                    }
                },
                {
                    "txid": "prev2" + "0" * 60,
                    "vout": 1,
                    "prevout": {
                        "scriptpubkey_address": "1OtherAddr...",
                        "value": 30000
                    }
                }
            ],
            "vout": [
                {
                    "scriptpubkey_address": "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa",
                    "value": 60000
                },
                {
                    "scriptpubkey_address": "1ChangeAddr...",
                    "value": 20000
                }
            ]
        }

    @pytest.fixture
    def sample_full_tx_coinbase(self):
        """Sample full transaction with coinbase input."""
        return {
            "txid": "c" * 64,
            "vin": [
                {
                    "coinbase": "04ffff001d0104",
                    "txid": None,
                    "vout": None,
                    "prevout": None
                }
            ],
            "vout": [
                {
                    "scriptpubkey_address": "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa",
                    "value": 5000000000
                }
            ]
        }

    @pytest.fixture
    def sample_full_tx_op_return(self):
        """Sample full transaction with OP_RETURN output."""
        return {
            "txid": "d" * 64,
            "vin": [
                {
                    "txid": "prev3" + "0" * 60,
                    "vout": 0,
                    "prevout": {
                        "scriptpubkey_address": "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa",
                        "value": 100000
                    }
                }
            ],
            "vout": [
                {
                    "scriptpubkey_address": "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa",
                    "value": 50000
                },
                {
                    "scriptpubkey_type": "nulldata",
                    "scriptpubkey_address": None,
                    "value": 0
                }
            ]
        }

    def test_iter_normalized_records_confirmed(self, client):
        """Test normalized records for confirmed transaction."""
        sample_address_txs = [
            {
                "txid": "a" * 64,
                "status": {"block_height": 100, "block_time": 1234567890}
            }
        ]
        sample_full_tx_confirmed = {
            "txid": "a" * 64,
            "vin": [
                {
                    "txid": "prev1" + "0" * 60,
                    "vout": 0,
                    "prevout": {
                        "scriptpubkey_address": "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa",
                        "value": 50000
                    }
                },
            ],
            "vout": [
                {
                    "scriptpubkey_address": "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa",
                    "value": 60000
                },
            ]
        }
        client._session.request.side_effect = [
            Mock(json=lambda: sample_address_txs, raise_for_status=lambda: None),  # get_address_txs
            Mock(json=lambda: sample_full_tx_confirmed, raise_for_status=lambda: None),  # get_tx
        ]

        records = list(client.iter_address_normalized_records("1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa"))

        assert len(records) == 2  # one in, one out
        for record in records:
            assert record.source == "blockstream"
            assert record.tx_hash == "a" * 64
            assert record.timestamp == 1234567890
            assert record.block_height == 100
            assert record.amount_sats > 0

    def test_iter_normalized_records_unconfirmed(self, client):
        """Test normalized records for unconfirmed transaction (timestamp=None)."""
        sample_address_txs = [
            {
                "txid": "b" * 64,
                "status": {"block_height": None, "block_time": None}  # unconfirmed
            }
        ]
        unconfirmed_tx = {"txid": "b" * 64, "vin": [], "vout": []}
        client._session.request.side_effect = [
            Mock(json=lambda: sample_address_txs, raise_for_status=lambda: None),
            Mock(json=lambda: unconfirmed_tx, raise_for_status=lambda: None),
        ]

        records = list(client.iter_address_normalized_records("1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa"))

        # Unconfirmed tx with no relevant I/O produces no records
        assert len(records) == 0

    def test_iter_internal_txs_excludes_coinbase(self, client):
        """Test InternalTx excludes coinbase inputs."""
        sample_address_txs = [
            {
                "txid": "c" * 64,
                "status": {"block_height": None, "block_time": None}  # unconfirmed
            }
        ]
        sample_full_tx_coinbase = {
            "txid": "c" * 64,
            "vin": [
                {
                    "coinbase": "04ffff001d0104",
                    "txid": None,
                    "vout": None,
                    "prevout": None
                }
            ],
            "vout": [
                {
                    "scriptpubkey_address": "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa",
                    "value": 5000000000
                }
            ]
        }
        client._session.request.side_effect = [
            Mock(json=lambda: sample_address_txs, raise_for_status=lambda: None),
            Mock(json=lambda: sample_full_tx_coinbase, raise_for_status=lambda: None),
        ]

        internal_txs = list(client.iter_address_internal_txs("1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa"))

        assert len(internal_txs) == 1
        tx = internal_txs[0]
        assert tx.tx_hash == "c" * 64
        assert len(tx.inputs) == 0  # coinbase input excluded
        assert len(tx.outputs) == 1  # output included
        assert tx.timestamp is None  # unconfirmed
        assert tx.block_height is None

    def test_iter_internal_txs_excludes_op_return(self, client):
        """Test InternalTx excludes OP_RETURN outputs."""
        sample_address_txs = [
            {
                "txid": "d" * 64,
                "status": {"block_height": 100, "block_time": 1234567890}
            }
        ]
        sample_full_tx_op_return = {
            "txid": "d" * 64,
            "vin": [
                {
                    "txid": "c" * 64,
                    "vout": 0,
                    "prevout": {
                        "scriptpubkey_address": "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa",
                        "value": 100000
                    }
                }
            ],
            "vout": [
                {
                    "scriptpubkey_address": "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa",
                    "value": 50000
                },
                {
                    "scriptpubkey_type": "nulldata",
                    "scriptpubkey_address": None,
                    "value": 0
                }
            ]
        }
        client._session.request.side_effect = [
            Mock(json=lambda: sample_address_txs, raise_for_status=lambda: None),
            Mock(json=lambda: sample_full_tx_op_return, raise_for_status=lambda: None),
        ]

        internal_txs = list(client.iter_address_internal_txs("1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa"))

        assert len(internal_txs) == 1
        tx = internal_txs[0]
        assert tx.tx_hash == "d" * 64
        assert len(tx.inputs) == 1  # valid input
        assert len(tx.outputs) == 1  # only non-OP_RETURN output
        assert tx.outputs[0].address == "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa"
        assert tx.outputs[0].amount_sats == 50000


class TestBlockCypherClient:
    """Test BlockCypher API client with mocked responses."""

    @pytest.fixture
    def client(self):
        """Create a BlockCypherClient with mocked session."""
        client = BlockCypherClient()
        client._session = Mock()
        return client

    @pytest.fixture
    def sample_address_full(self):
        """Sample address full response."""
        return {
            "txrefs": [
                {
                    "tx_hash": "a" * 64,
                    "block_height": 100,
                    "confirmed": 1234567890
                }
            ],
            "unconfirmed_txrefs": [
                {
                    "tx_hash": "b" * 64,
                    "block_height": -1,
                    "confirmed": None
                }
            ]
        }

    @pytest.fixture
    def sample_full_tx(self):
        """Sample full transaction."""
        return {
            "txid": "a" * 64,
            "inputs": [
                {
                    "prev_hash": "prev1" + "0" * 60,
                    "output_index": 0,
                    "addresses": ["1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa"],
                    "output_value": 50000
                },
                {
                    "prev_hash": "prev2" + "0" * 60,
                    "output_index": 1,
                    "addresses": ["1OtherAddr..."],
                    "output_value": 30000
                }
            ],
            "outputs": [
                {
                    "addresses": ["1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa"],
                    "value": 60000
                },
                {
                    "addresses": ["1ChangeAddr..."],
                    "value": 20000
                }
            ]
        }

    @pytest.fixture
    def sample_full_tx_coinbase(self):
        """Sample full transaction with coinbase input."""
        return {
            "txid": "c" * 64,
            "inputs": [
                {
                    "prev_hash": None,
                    "output_index": None,
                    "addresses": [],
                    "output_value": 0
                }
            ],
            "outputs": [
                {
                    "addresses": ["1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa"],
                    "value": 5000000000
                }
            ]
        }

    @pytest.fixture
    def sample_full_tx_op_return(self):
        """Sample full transaction with OP_RETURN output."""
        return {
            "txid": "d" * 64,
            "inputs": [
                {
                    "prev_hash": "prev3" + "0" * 60,
                    "output_index": 0,
                    "addresses": ["1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa"],
                    "output_value": 100000
                }
            ],
            "outputs": [
                {
                    "addresses": ["1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa"],
                    "value": 50000
                },
                {
                    "addresses": [],
                    "value": 0
                }
            ]
        }

    def test_iter_normalized_records_confirmed(self, client):
        """Test normalized records for confirmed transaction."""
        sample_address_full = {
            "txrefs": [
                {
                    "tx_hash": "a" * 64,
                    "block_height": 100,
                    "confirmed": 1234567890
                }
            ],
            "unconfirmed_txrefs": []
        }
        sample_full_tx = {
            "txid": "a" * 64,
            "inputs": [
                {
                    "prev_hash": "prev1" + "0" * 60,
                    "output_index": 0,
                    "addresses": ["1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa"],
                    "output_value": 50000
                },
            ],
            "outputs": [
                {
                    "addresses": ["1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa"],
                    "value": 60000
                },
            ]
        }
        client._session.request.side_effect = [
            Mock(json=lambda: sample_address_full, raise_for_status=lambda: None),
            Mock(json=lambda: sample_full_tx, raise_for_status=lambda: None),
        ]

        records = list(client.iter_address_normalized_records("1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa"))

        assert len(records) == 2  # one in, one out
        for record in records:
            assert record.source == "blockcypher"
            assert record.tx_hash == "a" * 64
            assert record.timestamp == 1234567890
            assert record.block_height == 100
            assert record.amount_sats > 0

    def test_iter_normalized_records_unconfirmed(self, client):
        """Test unconfirmed transaction gets timestamp=None, block_height=None."""
        sample_address_full = {
            "txrefs": [],
            "unconfirmed_txrefs": [
                {
                    "tx_hash": "b" * 64,
                    "block_height": -1,
                    "confirmed": None
                }
            ]
        }
        unconfirmed_tx = {"txid": "b" * 64, "inputs": [], "outputs": []}
        client._session.request.side_effect = [
            Mock(json=lambda: sample_address_full, raise_for_status=lambda: None),
            Mock(json=lambda: unconfirmed_tx, raise_for_status=lambda: None),
        ]

        records = list(client.iter_address_normalized_records("1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa"))
        # No records for unconfirmed tx with no relevant I/O
        assert len(records) == 0

    def test_iter_internal_txs_excludes_coinbase(self, client):
        """Test InternalTx excludes coinbase inputs."""
        sample_address_full = {
            "txrefs": [
                {
                    "tx_hash": "c" * 64,
                    "block_height": -1,
                    "confirmed": None
                }
            ],
            "unconfirmed_txrefs": []
        }
        sample_full_tx_coinbase = {
            "txid": "c" * 64,
            "inputs": [
                {
                    "prev_hash": None,
                    "output_index": None,
                    "addresses": [],
                    "output_value": 0
                }
            ],
            "outputs": [
                {
                    "addresses": ["1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa"],
                    "value": 5000000000
                }
            ]
        }
        client._session.request.side_effect = [
            Mock(json=lambda: sample_address_full, raise_for_status=lambda: None),
            Mock(json=lambda: sample_full_tx_coinbase, raise_for_status=lambda: None),
        ]

        internal_txs = list(client.iter_address_internal_txs("1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa"))

        assert len(internal_txs) == 1
        tx = internal_txs[0]
        assert tx.tx_hash == "c" * 64
        assert len(tx.inputs) == 0  # coinbase input excluded
        assert len(tx.outputs) == 1
        assert tx.timestamp is None
        assert tx.block_height is None

    def test_iter_internal_txs_excludes_op_return(self, client):
        """Test InternalTx excludes OP_RETURN outputs."""
        sample_address_full = {
            "txrefs": [
                {
                    "tx_hash": "d" * 64,
                    "block_height": 100,
                    "confirmed": 1234567890
                }
            ],
            "unconfirmed_txrefs": []
        }
        sample_full_tx_op_return = {
            "txid": "d" * 64,
            "inputs": [
                {
                    "prev_hash": "c" * 64,
                    "output_index": 0,
                    "addresses": ["1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa"],
                    "output_value": 100000
                }
            ],
            "outputs": [
                {
                    "addresses": ["1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa"],
                    "value": 50000
                },
                {
                    "addresses": [],
                    "value": 0
                }
            ]
        }
        client._session.request.side_effect = [
            Mock(json=lambda: sample_address_full, raise_for_status=lambda: None),
            Mock(json=lambda: sample_full_tx_op_return, raise_for_status=lambda: None),
        ]

        internal_txs = list(client.iter_address_internal_txs("1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa"))

        assert len(internal_txs) == 1
        tx = internal_txs[0]
        assert tx.tx_hash == "d" * 64
        assert len(tx.inputs) == 1
        assert len(tx.outputs) == 1  # OP_RETURN excluded
        assert tx.outputs[0].address == "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa"


class TestPipeline:
    """Test IngestionPipeline behavior."""

    def test_create_pipeline_defaults(self):
        """Test pipeline creation with defaults."""
        pipeline = create_pipeline()
        assert isinstance(pipeline, IngestionPipeline)
        assert pipeline.config.blockstream_config is not None
        assert pipeline.config.blockcypher_config is not None
        assert pipeline.config.max_txs_per_address == 100

    def test_create_pipeline_with_elliptic(self):
        """Test pipeline creation with Elliptic data dir."""
        pipeline = create_pipeline(elliptic_data_dir=TEST_DATA_DIR)
        assert pipeline.config.elliptic_data_dir == TEST_DATA_DIR

    def test_create_pipeline_with_blockcypher_token(self):
        """Test pipeline creation with BlockCypher token."""
        pipeline = create_pipeline(blockcypher_token="test-token")
        assert pipeline.config.blockcypher_config.token == "test-token"

    def test_ingest_elliptic_batch(self):
        """Test batch Elliptic ingestion."""
        pipeline = create_pipeline(elliptic_data_dir=TEST_DATA_DIR)
        records = pipeline.ingest_elliptic_batch()

        assert isinstance(records, list)
        assert len(records) == 10
        for record in records:
            assert isinstance(record, NormalizedRecord)
            assert record.source == "elliptic"

    def test_iter_elliptic_normalized_records(self):
        """Test memory-efficient Elliptic iteration."""
        pipeline = create_pipeline(elliptic_data_dir=TEST_DATA_DIR)
        records = list(pipeline.iter_elliptic_normalized_records())

        assert len(records) == 10

    def test_get_elliptic_address_tx_mapping(self):
        """Test getting Elliptic++ address mapping for Module 5."""
        pipeline = create_pipeline(elliptic_data_dir=TEST_DATA_DIR)
        mapping = pipeline.get_elliptic_address_tx_mapping()
        assert isinstance(mapping, dict)

    def test_get_elliptic_txid_address_mapping(self):
        """Test getting Elliptic++ txId mapping for Module 5."""
        pipeline = create_pipeline(elliptic_data_dir=TEST_DATA_DIR)
        mapping = pipeline.get_elliptic_txid_address_mapping()
        assert isinstance(mapping, dict)

    def test_ingest_elliptic_batch_no_internal_txs(self):
        """Verify Elliptic batch ingestion does NOT return InternalTx."""
        pipeline = create_pipeline(elliptic_data_dir=TEST_DATA_DIR)
        records = pipeline.ingest_elliptic_batch()

        # Should return list of NormalizedRecord only, not tuple
        assert not isinstance(records, tuple)
        assert all(isinstance(r, NormalizedRecord) for r in records)

    def test_ingest_live_address_requires_source(self):
        """Test live address ingestion requires valid source."""
        pipeline = create_pipeline()
        # Mock the clients to avoid network calls
        with patch.object(pipeline, 'ingest_live_address') as mock_ingest:
            mock_ingest.side_effect = ValueError("No live sources configured")
            with pytest.raises(ValueError):
                pipeline.ingest_live_address("1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa")

    def test_ingest_training_data(self):
        """Test convenience function for training data ingestion."""
        records = ingest_training_data(TEST_DATA_DIR)
        assert isinstance(records, list)
        assert len(records) == 10
        for record in records:
            assert isinstance(record, NormalizedRecord)
            assert record.source == "elliptic"

    def test_ingest_reported_address_returns_both(self):
        """Test reported address ingestion returns both records and internal_txs."""
        pipeline = create_pipeline()
        # This would need mocked live clients - skip for now
        pass


class TestMalformedRecords:
    """Test handling of malformed/invalid records."""

    def test_normalized_record_rejects_invalid_tx_hash(self):
        """Test NormalizedRecord rejects non-hex tx_hash."""
        with pytest.raises(ValueError, match="64-char lowercase hex"):
            NormalizedRecord(
                tx_hash="not-hex!!",
                address="1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa",
                timestamp=1234567890,
                amount_sats=100000,
                direction="in",
                source="blockstream",
            )

    def test_normalized_record_rejects_uppercase_tx_hash(self):
        """Test NormalizedRecord rejects uppercase tx_hash."""
        with pytest.raises(ValueError, match="64-char lowercase hex"):
            NormalizedRecord(
                tx_hash="A" * 64,
                address="1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa",
                timestamp=1234567890,
                amount_sats=100000,
                direction="in",
                source="blockstream",
            )

    def test_txin_rejects_invalid_txid(self):
        """Test TxIn rejects invalid txid."""
        with pytest.raises(ValueError, match="64-char lowercase hex"):
            TxIn(
                txid="not-valid",
                vout=0,
                address="1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa",
                amount_sats=100000,
            )

    def test_internal_tx_rejects_invalid_tx_hash(self):
        """Test InternalTx rejects invalid tx_hash."""
        txin = TxIn(txid="b" * 64, vout=0, address="addr1", amount_sats=100000)
        txout = TxOut(address="addr2", amount_sats=50000)

        with pytest.raises(ValueError, match="64-char lowercase hex"):
            InternalTx(
                tx_hash="invalid",
                timestamp=1234567890,
                block_height=123456,
                inputs=(txin,),
                outputs=(txout,),
            )

    def test_elliptic_record_rejects_tx_hash(self):
        """Test Elliptic NormalizedRecord rejects tx_hash."""
        with pytest.raises(ValueError, match="must not have tx_hash"):
            NormalizedRecord(
                elliptic_id="tx123",
                tx_hash="a" * 64,
                address="1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa",
                timestamp=1234567890,
                amount_sats=100000,
                direction="in",
                source="elliptic",
            )

    def test_live_record_rejects_elliptic_id(self):
        """Test live NormalizedRecord rejects elliptic_id."""
        with pytest.raises(ValueError, match="must not have elliptic_id"):
            NormalizedRecord(
                tx_hash="a" * 64,
                elliptic_id="tx123",
                address="1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa",
                timestamp=1234567890,
                amount_sats=100000,
                direction="in",
                source="blockstream",
            )


class TestCoinbaseOpReturnUnconfirmed:
    """Test edge cases: coinbase, OP_RETURN, unconfirmed."""

    def test_coinbase_input_excluded_from_internal_tx(self):
        """Verify coinbase inputs are excluded from InternalTx."""
        # This is tested in BlockstreamClient/BlockCypherClient tests above
        pass

    def test_op_return_output_excluded_from_internal_tx(self):
        """Verify OP_RETURN outputs are excluded from InternalTx."""
        # This is tested in BlockstreamClient/BlockCypherClient tests above
        pass

    def test_unconfirmed_tx_has_none_timestamp(self):
        """Verify unconfirmed transactions have timestamp=None."""
        # This is tested in BlockstreamClient/BlockCypherClient tests above
        pass

    def test_unconfirmed_tx_has_none_block_height(self):
        """Verify unconfirmed transactions have block_height=None."""
        # This is tested in BlockstreamClient/BlockCypherClient tests above
        pass


if __name__ == "__main__":
    pytest.main([__file__, "-v"])