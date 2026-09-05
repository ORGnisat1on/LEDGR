import pytest
from unittest.mock import patch, MagicMock
from ledgr.blockstream_client import BlockstreamClient
from ledgr.blockcypher_client import BlockCypherClient

# Synthetic Coinbase transaction
MOCK_COINBASE_TX_BLOCKSTREAM = {
    "txid": "1111111111111111111111111111111111111111111111111111111111111111",
    "version": 1,
    "locktime": 0,
    "vin": [{"txid": "0000000000000000000000000000000000000000000000000000000000000000", "vout": 4294967295, "is_coinbase": True}], # No prevout
    "vout": [{"scriptpubkey_address": "miner_address", "value": 5000000000}]
}

# Synthetic OP_RETURN transaction
MOCK_OP_RETURN_TX_BLOCKSTREAM = {
    "txid": "2222222222222222222222222222222222222222222222222222222222222222",
    "version": 1,
    "locktime": 0,
    "vin": [{"txid": "3333333333333333333333333333333333333333333333333333333333333333", "vout": 0, "prevout": {"scriptpubkey_address": "sender", "value": 10000}}],
    "vout": [{"scriptpubkey_type": "op_return", "value": 0}] # No scriptpubkey_address
}

MOCK_COINBASE_TX_BLOCKCYPHER = {
    "tx_hash": "1111111111111111111111111111111111111111111111111111111111111111",
    "inputs": [{"output_value": 0}], # no prev_hash, no addresses
    "outputs": [{"addresses": ["miner_address"], "value": 5000000000}]
}

MOCK_OP_RETURN_TX_BLOCKCYPHER = {
    "tx_hash": "2222222222222222222222222222222222222222222222222222222222222222",
    "inputs": [{"prev_hash": "3333333333333333333333333333333333333333333333333333333333333333", "output_index": 0, "addresses": ["sender"], "output_value": 10000}],
    "outputs": [{"value": 0}] # no addresses list
}

@patch("ledgr.blockstream_client.BlockstreamClient.get_address_txs")
@patch("ledgr.blockstream_client.BlockstreamClient.get_tx")
def test_blockstream_coinbase_and_op_return(mock_get_tx, mock_get_txs):
    client = BlockstreamClient()
    # Mock txs summary
    mock_get_txs.return_value = [
        {"txid": "1111111111111111111111111111111111111111111111111111111111111111", "status": {"block_height": 100, "block_time": 1000}},
        {"txid": "2222222222222222222222222222222222222222222222222222222222222222", "status": {"block_height": 100, "block_time": 1000}}
    ]
    # Mock full tx details
    def get_tx_side_effect(txid):
        if txid == "1111111111111111111111111111111111111111111111111111111111111111": return MOCK_COINBASE_TX_BLOCKSTREAM
        if txid == "2222222222222222222222222222222222222222222222222222222222222222": return MOCK_OP_RETURN_TX_BLOCKSTREAM
        return {}
    mock_get_tx.side_effect = get_tx_side_effect

    # This should not crash
    txs = list(client.iter_address_internal_txs("any_address"))
    
    assert len(txs) == 2
    # Check Coinbase parsing
    cb_tx = txs[0]
    assert cb_tx.tx_hash == "1111111111111111111111111111111111111111111111111111111111111111"
    assert len(cb_tx.inputs) == 1
    assert cb_tx.inputs[0].address is None  # Optional missing address handled gracefully
    assert cb_tx.inputs[0].amount_sats is None
    
    # Check OP_RETURN parsing
    op_tx = txs[1]
    assert op_tx.tx_hash == "2222222222222222222222222222222222222222222222222222222222222222"
    assert len(op_tx.outputs) == 1
    assert op_tx.outputs[0].address is None
    assert op_tx.outputs[0].amount_sats is None or op_tx.outputs[0].amount_sats == 0

@patch("ledgr.blockcypher_client.BlockCypherClient.get_address_full")
@patch("ledgr.blockcypher_client.BlockCypherClient.get_tx")
def test_blockcypher_coinbase_and_op_return(mock_get_tx, mock_get_full):
    client = BlockCypherClient()
    mock_get_full.return_value = {
        "txrefs": [
            {"tx_hash": "1111111111111111111111111111111111111111111111111111111111111111", "block_height": 100, "confirmed": 1000},
            {"tx_hash": "2222222222222222222222222222222222222222222222222222222222222222", "block_height": 100, "confirmed": 1000}
        ]
    }
    
    def get_tx_side_effect(txid):
        if txid == "1111111111111111111111111111111111111111111111111111111111111111": return MOCK_COINBASE_TX_BLOCKCYPHER
        if txid == "2222222222222222222222222222222222222222222222222222222222222222": return MOCK_OP_RETURN_TX_BLOCKCYPHER
        return {}
    mock_get_tx.side_effect = get_tx_side_effect

    # This should not crash
    txs = list(client.iter_address_internal_txs("any_address"))
    
    assert len(txs) == 2
    
    # Check Coinbase parsing
    cb_tx = txs[0]
    assert cb_tx.tx_hash == "1111111111111111111111111111111111111111111111111111111111111111"
    assert len(cb_tx.inputs) == 1
    assert cb_tx.inputs[0].txid is None
    assert cb_tx.inputs[0].address is None
    
    # Check OP_RETURN parsing
    op_tx = txs[1]
    assert op_tx.tx_hash == "2222222222222222222222222222222222222222222222222222222222222222"
    assert len(op_tx.outputs) == 1
    assert op_tx.outputs[0].address is None
