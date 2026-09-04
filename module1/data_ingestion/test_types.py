"""
Basic tests for Module 1 types and ingestion.
Run with: python -m pytest module1/data_ingestion/test_types.py -v
"""

import pytest
from module1.data_ingestion.types import (
    NormalizedRecord,
    InternalTx,
    TxIn,
    TxOut,
    SourceType,
    DirectionType,
    _validate_bitcoin_tx_hash,
    _validate_elliptic_id,
)


class TestValidationHelpers:
    """Test validation helper functions."""

    def test_validate_bitcoin_tx_hash_valid(self):
        """Test valid Bitcoin tx hash passes validation."""
        _validate_bitcoin_tx_hash("a" * 64)
        _validate_bitcoin_tx_hash("0" * 64)
        _validate_bitcoin_tx_hash("f" * 64)
        _validate_bitcoin_tx_hash("abcdef0123456789" * 4)

    def test_validate_bitcoin_tx_hash_invalid_length(self):
        """Test invalid length raises ValueError."""
        with pytest.raises(ValueError, match="64-char lowercase hex"):
            _validate_bitcoin_tx_hash("short")
        with pytest.raises(ValueError, match="64-char lowercase hex"):
            _validate_bitcoin_tx_hash("a" * 63)
        with pytest.raises(ValueError, match="64-char lowercase hex"):
            _validate_bitcoin_tx_hash("a" * 65)

    def test_validate_bitcoin_tx_hash_invalid_chars(self):
        """Test invalid hex characters raise ValueError."""
        with pytest.raises(ValueError, match="64-char lowercase hex"):
            _validate_bitcoin_tx_hash("g" * 64)  # g is not hex
        with pytest.raises(ValueError, match="64-char lowercase hex"):
            _validate_bitcoin_tx_hash("A" * 64)  # uppercase not allowed
        with pytest.raises(ValueError, match="64-char lowercase hex"):
            _validate_bitcoin_tx_hash("a" * 63 + "G")  # invalid char at end

    def test_validate_elliptic_id_valid(self):
        """Test valid Elliptic ID passes validation."""
        _validate_elliptic_id("tx123")
        _validate_elliptic_id("a1b2c3d4e5f6789012345678901234567890abcdef1234567890abcdef123456")
        _validate_elliptic_id("any-non-empty-string")

    def test_validate_elliptic_id_invalid(self):
        """Test empty Elliptic ID raises ValueError."""
        with pytest.raises(ValueError, match="non-empty string"):
            _validate_elliptic_id("")
        with pytest.raises(ValueError, match="non-empty string"):
            _validate_elliptic_id(None)  # type: ignore


class TestNormalizedRecord:
    """Test NormalizedRecord data type."""

    def test_elliptic_record_valid(self):
        """Test creating a valid Elliptic NormalizedRecord."""
        record = NormalizedRecord(
            elliptic_id="a1b2c3d4e5f6789012345678901234567890abcdef1234567890abcdef123456",
            address="1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa",
            timestamp=1234567890,
            amount_sats=100000,
            direction="in",
            source="elliptic",
            block_height=123456,
        )
        assert record.elliptic_id == "a1b2c3d4e5f6789012345678901234567890abcdef1234567890abcdef123456"
        assert record.tx_hash is None
        assert record.direction == "in"
        assert record.source == "elliptic"
        assert record.block_height == 123456
        assert record.tx_identifier == record.elliptic_id

    def test_blockstream_record_valid(self):
        """Test creating a valid Blockstream NormalizedRecord."""
        record = NormalizedRecord(
            tx_hash="a" * 64,
            address="1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa",
            timestamp=1234567890,
            amount_sats=100000,
            direction="in",
            source="blockstream",
            block_height=123456,
        )
        assert record.tx_hash == "a" * 64
        assert record.elliptic_id is None
        assert record.direction == "in"
        assert record.source == "blockstream"
        assert record.tx_identifier == record.tx_hash

    def test_blockcypher_record_valid(self):
        """Test creating a valid BlockCypher NormalizedRecord."""
        record = NormalizedRecord(
            tx_hash="b" * 64,
            address="1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa",
            timestamp=1234567890,
            amount_sats=100000,
            direction="out",
            source="blockcypher",
            block_height=None,
        )
        assert record.tx_hash == "b" * 64
        assert record.elliptic_id is None
        assert record.direction == "out"
        assert record.source == "blockcypher"
        assert record.block_height is None
        assert record.tx_identifier == record.tx_hash

    def test_elliptic_record_requires_elliptic_id(self):
        """Test Elliptic records must have elliptic_id."""
        with pytest.raises(ValueError, match="Elliptic records must have elliptic_id"):
            NormalizedRecord(
                address="1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa",
                timestamp=1234567890,
                amount_sats=100000,
                direction="in",
                source="elliptic",
            )

    def test_elliptic_record_forbids_tx_hash(self):
        """Test Elliptic records must not have tx_hash."""
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

    def test_live_record_requires_tx_hash(self):
        """Test live source records must have tx_hash."""
        with pytest.raises(ValueError, match="blockstream records must have tx_hash"):
            NormalizedRecord(
                address="1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa",
                timestamp=1234567890,
                amount_sats=100000,
                direction="in",
                source="blockstream",
            )

    def test_live_record_forbids_elliptic_id(self):
        """Test live source records must not have elliptic_id."""
        with pytest.raises(ValueError, match="blockstream records must not have elliptic_id"):
            NormalizedRecord(
                tx_hash="a" * 64,
                elliptic_id="tx123",
                address="1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa",
                timestamp=1234567890,
                amount_sats=100000,
                direction="in",
                source="blockstream",
            )

    def test_invalid_tx_hash_format(self):
        """Test that invalid tx_hash format raises ValueError."""
        with pytest.raises(ValueError, match="64-char lowercase hex"):
            NormalizedRecord(
                tx_hash="SHORT",
                address="1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa",
                timestamp=1234567890,
                amount_sats=100000,
                direction="in",
                source="blockstream",
            )
        with pytest.raises(ValueError, match="64-char lowercase hex"):
            NormalizedRecord(
                tx_hash="G" * 64,  # uppercase
                address="1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa",
                timestamp=1234567890,
                amount_sats=100000,
                direction="in",
                source="blockstream",
            )

    def test_invalid_direction(self):
        """Test that invalid direction raises ValueError."""
        with pytest.raises(ValueError, match="direction must be 'in' or 'out'"):
            NormalizedRecord(
                tx_hash="a" * 64,
                address="1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa",
                timestamp=1234567890,
                amount_sats=100000,
                direction="invalid",
                source="blockstream",
            )

    def test_invalid_source(self):
        """Test that invalid source raises ValueError."""
        with pytest.raises(ValueError, match="source must be elliptic/blockstream/blockcypher"):
            NormalizedRecord(
                tx_hash="a" * 64,
                address="1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa",
                timestamp=1234567890,
                amount_sats=100000,
                direction="in",
                source="invalid",
            )

    def test_invalid_amount(self):
        """Test that non-positive amount raises ValueError."""
        with pytest.raises(ValueError, match="amount_sats must be positive integer"):
            NormalizedRecord(
                tx_hash="a" * 64,
                address="1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa",
                timestamp=1234567890,
                amount_sats=0,
                direction="in",
                source="blockstream",
            )

    def test_timestamp_can_be_none(self):
        """Test that timestamp can be None (unknown timestamp)."""
        record = NormalizedRecord(
            tx_hash="a" * 64,
            address="1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa",
            timestamp=None,
            amount_sats=100000,
            direction="in",
            source="blockstream",
        )
        assert record.timestamp is None

    def test_timestamp_none_for_elliptic(self):
        """Test that Elliptic records can have None timestamp."""
        record = NormalizedRecord(
            elliptic_id="tx123",
            address="1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa",
            timestamp=None,
            amount_sats=100000,
            direction="in",
            source="elliptic",
        )
        assert record.timestamp is None

    def test_invalid_timestamp_negative(self):
        """Test that negative timestamp raises ValueError."""
        with pytest.raises(ValueError, match="positive integer or None"):
            NormalizedRecord(
                tx_hash="a" * 64,
                address="1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa",
                timestamp=-1,
                amount_sats=100000,
                direction="in",
                source="blockstream",
            )

    def test_block_height_can_be_none(self):
        """Test that block_height can be None."""
        record = NormalizedRecord(
            tx_hash="a" * 64,
            address="1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa",
            timestamp=1234567890,
            amount_sats=100000,
            direction="in",
            source="blockstream",
            block_height=None,
        )
        assert record.block_height is None


class TestTxIn:
    """Test TxIn data type."""

    def test_txin_valid(self):
        """Test creating a valid TxIn."""
        txin = TxIn(
            txid="b" * 64,
            vout=0,
            address="1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa",
            amount_sats=50000,
        )
        assert txin.txid == "b" * 64
        assert txin.vout == 0
        assert txin.amount_sats == 50000

    def test_txin_invalid_txid(self):
        """Test that invalid txid raises ValueError."""
        with pytest.raises(ValueError, match="64-char lowercase hex"):
            TxIn(
                txid="short",
                vout=0,
                address="1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa",
                amount_sats=50000,
            )
        with pytest.raises(ValueError, match="64-char lowercase hex"):
            TxIn(
                txid="G" * 64,
                vout=0,
                address="1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa",
                amount_sats=50000,
            )

    def test_txin_invalid_vout(self):
        """Test that negative vout raises ValueError."""
        with pytest.raises(ValueError, match="vout must be non-negative integer"):
            TxIn(
                txid="b" * 64,
                vout=-1,
                address="1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa",
                amount_sats=50000,
            )

    def test_txin_invalid_amount(self):
        """Test that non-positive amount raises ValueError."""
        with pytest.raises(ValueError, match="amount_sats must be positive integer"):
            TxIn(
                txid="b" * 64,
                vout=0,
                address="1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa",
                amount_sats=0,
            )


class TestTxOut:
    """Test TxOut data type."""

    def test_txout_valid(self):
        """Test creating a valid TxOut."""
        txout = TxOut(
            address="1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa",
            amount_sats=50000,
        )
        assert txout.amount_sats == 50000

    def test_txout_invalid_amount(self):
        """Test that non-positive amount raises ValueError."""
        with pytest.raises(ValueError, match="amount_sats must be positive integer"):
            TxOut(
                address="1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa",
                amount_sats=0,
            )


class TestInternalTx:
    """Test InternalTx data type."""

    def test_internal_tx_valid(self):
        """Test creating a valid InternalTx."""
        txin = TxIn(txid="b" * 64, vout=0, address="addr1", amount_sats=100000)
        txout = TxOut(address="addr2", amount_sats=50000)

        internal = InternalTx(
            tx_hash="c" * 64,
            timestamp=1234567890,
            block_height=123456,
            inputs=(txin,),
            outputs=(txout,),
        )
        assert len(internal.inputs) == 1
        assert len(internal.outputs) == 1
        assert internal.input_list == [txin]
        assert internal.output_list == [txout]
        assert internal.tx_hash == "c" * 64

    def test_internal_tx_timestamp_none(self):
        """Test InternalTx with None timestamp (unconfirmed)."""
        txin = TxIn(txid="b" * 64, vout=0, address="addr1", amount_sats=100000)
        txout = TxOut(address="addr2", amount_sats=50000)

        internal = InternalTx(
            tx_hash="c" * 64,
            timestamp=None,
            block_height=None,
            inputs=(txin,),
            outputs=(txout,),
        )
        assert internal.timestamp is None
        assert internal.block_height is None

    def test_internal_tx_invalid_tx_hash(self):
        """Test that invalid tx_hash raises ValueError."""
        txin = TxIn(txid="b" * 64, vout=0, address="addr1", amount_sats=100000)
        txout = TxOut(address="addr2", amount_sats=50000)

        with pytest.raises(ValueError, match="64-char lowercase hex"):
            InternalTx(
                tx_hash="SHORT",
                timestamp=1234567890,
                block_height=123456,
                inputs=(txin,),
                outputs=(txout,),
            )

    def test_internal_tx_invalid_inputs_type(self):
        """Test that inputs must be tuple."""
        txin = TxIn(txid="b" * 64, vout=0, address="addr1", amount_sats=100000)
        txout = TxOut(address="addr2", amount_sats=50000)

        with pytest.raises(ValueError, match="inputs must be tuple"):
            InternalTx(
                tx_hash="c" * 64,
                timestamp=1234567890,
                block_height=123456,
                inputs=[txin],  # list instead of tuple
                outputs=(txout,),
            )

    def test_internal_tx_empty_inputs_outputs(self):
        """Test InternalTx with empty inputs and outputs."""
        internal = InternalTx(
            tx_hash="c" * 64,
            timestamp=1234567890,
            block_height=123456,
            inputs=(),
            outputs=(),
        )
        assert len(internal.inputs) == 0
        assert len(internal.outputs) == 0


class TestSchemaCompliance:
    """Test that types match ARCHITECTURE.md schema exactly."""

    def test_normalized_record_schema_fields(self):
        """Verify NormalizedRecord has all required fields per ARCHITECTURE.md."""
        # Blockstream record
        record = NormalizedRecord(
            tx_hash="a" * 64,
            address="1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa",
            timestamp=1234567890,
            amount_sats=100000,
            direction="in",
            source="blockstream",
            block_height=123456,
        )
        assert isinstance(record.tx_hash, str)
        assert record.elliptic_id is None
        assert isinstance(record.address, str)
        assert isinstance(record.timestamp, int)
        assert isinstance(record.amount_sats, int)
        assert isinstance(record.direction, str)
        assert isinstance(record.source, str)
        assert record.block_height is None or isinstance(record.block_height, int)

    def test_normalized_record_elliptic_schema(self):
        """Verify Elliptic NormalizedRecord schema."""
        record = NormalizedRecord(
            elliptic_id="tx123",
            address="1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa",
            timestamp=None,
            amount_sats=100000,
            direction="in",
            source="elliptic",
            block_height=None,
        )
        assert record.tx_hash is None
        assert isinstance(record.elliptic_id, str)
        assert isinstance(record.address, str)
        assert record.timestamp is None
        assert isinstance(record.amount_sats, int)
        assert isinstance(record.direction, str)
        assert isinstance(record.source, str)
        assert record.block_height is None

    def test_internal_tx_schema_fields(self):
        """Verify InternalTx has all required fields per ARCHITECTURE.md."""
        txin = TxIn(txid="b" * 64, vout=0, address="addr1", amount_sats=100000)
        txout = TxOut(address="addr2", amount_sats=50000)

        internal = InternalTx(
            tx_hash="c" * 64,
            timestamp=1234567890,
            block_height=123456,
            inputs=(txin,),
            outputs=(txout,),
        )
        assert isinstance(internal.tx_hash, str)
        assert internal.timestamp is None or isinstance(internal.timestamp, int)
        assert internal.block_height is None or isinstance(internal.block_height, int)
        assert isinstance(internal.inputs, tuple)
        assert isinstance(internal.outputs, tuple)
        for inp in internal.inputs:
            assert isinstance(inp, TxIn)
            assert isinstance(inp.txid, str)
            assert isinstance(inp.vout, int)
            assert isinstance(inp.address, str)
            assert isinstance(inp.amount_sats, int)
        for out in internal.outputs:
            assert isinstance(out, TxOut)
            assert isinstance(out.address, str)
            assert isinstance(out.amount_sats, int)

    def test_source_type_literal(self):
        """Test SourceType literal values."""
        assert "elliptic" in SourceType.__args__
        assert "blockstream" in SourceType.__args__
        assert "blockcypher" in SourceType.__args__

    def test_direction_type_literal(self):
        """Test DirectionType literal values."""
        assert "in" in DirectionType.__args__
        assert "out" in DirectionType.__args__


if __name__ == "__main__":
    pytest.main([__file__, "-v"])