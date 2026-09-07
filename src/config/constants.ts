/**
 * Shared frontend/Node config constants.
 *
 * LIVE_FETCH_TIMEOUT_SECONDS mirrors `backend/ledgr/config.py`'s
 * `LIVE_FETCH_TIMEOUT_SECONDS` (the live-trace fetch cap) and MUST be
 * kept in sync with it if either side changes. The Python-side per-request
 * HTTP timeout lives separately as `BlockstreamConfig.timeout_seconds`
 * in `blockstream_client.py` (default 30 s**.
 *
 * CLUSTERS_FETCH_TIMEOUT_SECONDS and MEMPOOL_FETCH_TIMEOUT_SECONDS are
 * Node-server-only timeouts (no Python-side counterpart; 4 s each**.
 */
export const LIVE_FETCH_TIMEOUT_SECONDS =  30;
export const CLUSTERS_FETCH_TIMEOUT_SECONDS =  4;
export const MEMPOOL_FETCH_TIMEOUT_SECONDS =  4;