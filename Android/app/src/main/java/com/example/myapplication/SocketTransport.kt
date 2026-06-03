package com.example.myapplication

import android.util.Log
import java.io.DataOutputStream
import java.net.InetSocketAddress
import java.net.Socket

/**
 * SocketTransport — client side of the L2 connection.
 *
 * One call = one logical payload (connect, length-prefix, stream N bytes, await 1-byte ACK).
 * Returns the measured client-side wall time in milliseconds, or -1.0 on failure.
 *
 * T_conn (connection establishment) and T_payload (streaming) are logged SEPARATELY as
 * CCCDATA lines so the analysis script can fit T_payload(P) = kappa * P^alpha and feed
 * T_conn into the trigger condition independently.
 */
object SocketTransport {

    private const val TAG = "CCCHarness"
    private const val CONNECT_TIMEOUT_MS = 5000
    private const val WRITE_BUF = 64 * 1024

    /**
     * Sends a payload of [payloadBytes] bytes to the bridge service.
     * @param tag a label written into the log line (e.g. "fg_sweep" or "bg_worker")
     * @return total client wall time in ms, or -1.0 on failure.
     */
    fun sendPayload(payloadBytes: Int, tag: String): Double {
        val socket = Socket()
        return try {
            // ---- T_conn ----
            val c0 = System.nanoTime()
            socket.connect(InetSocketAddress("127.0.0.1", BridgeService.PORT), CONNECT_TIMEOUT_MS)
            socket.tcpNoDelay = true
            val connMs = (System.nanoTime() - c0) / 1_000_000.0

            // ---- T_payload (stream) ----
            val out = DataOutputStream(socket.getOutputStream())
            val p0 = System.nanoTime()
            out.writeInt(payloadBytes)                 // 4-byte big-endian length prefix
            val chunk = ByteArray(WRITE_BUF)           // content is irrelevant; zeros are fine
            var sent = 0L
            val total = payloadBytes.toLong()
            while (sent < total) {
                val n = if (total - sent > WRITE_BUF) WRITE_BUF else (total - sent).toInt()
                out.write(chunk, 0, n)
                sent += n
            }
            out.flush()
            // await 1-byte ACK = server finished reading
            val ack = socket.getInputStream().read()
            val payloadMs = (System.nanoTime() - p0) / 1_000_000.0
            val totalMs = connMs + payloadMs
            val mb = payloadBytes / (1024.0 * 1024.0)

            Log.d(
                TAG,
                ("CCCDATA send_complete tag=%s ack=%d payload_bytes=%d payload_mb=%.4f " +
                 "t_conn_ms=%.3f t_payload_ms=%.3f t_total_ms=%.3f")
                    .format(tag, ack, payloadBytes, mb, connMs, payloadMs, totalMs)
            )
            totalMs
        } catch (e: Exception) {
            Log.e(TAG, "CCCDATA send_error tag=$tag payload_bytes=$payloadBytes msg=${e.message}")
            -1.0
        } finally {
            try { socket.close() } catch (_: Exception) {}
        }
    }
}
