package com.example.myapplication

import android.app.Service
import android.content.Intent
import android.os.IBinder
import android.util.Log
import java.io.DataInputStream
import java.net.ServerSocket
import java.net.Socket
import kotlin.concurrent.thread

/**
 * BridgeService — LQIA precondition L2 (persistent out-of-process service).
 *
 * Declared in the manifest with android:process=":bridge" so it runs in a SEPARATE
 * process from the UI/worker and survives the host's Doze transitions independently,
 * mirroring the persistent WPF AppService provider (Pid2) in the Windows paper.
 *
 * Transport: a localhost (127.0.0.1) TCP socket. This deliberately AVOIDS the Binder
 * 1 MB transaction buffer (so arbitrarily large payloads are possible) and provides a
 * genuinely STATEFUL connection with realistic per-byte loopback + TCP framing cost —
 * the property that lowers the CCC critical payload P* into a measurable range.
 *
 * Protocol (length-prefixed, no per-chunk ACK so a payload is one logical unit):
 *   client connects -> sends 4-byte big-endian payload length N -> streams N bytes
 *   server reads exactly N bytes, then logs the measured receive duration.
 *
 * All measurement output is emitted as machine-parseable lines prefixed "CCCDATA".
 */
class BridgeService : Service() {

    companion object {
        private const val TAG = "CCCHarness"
        const val PORT = 38917            // arbitrary high port on loopback
        private const val READ_BUF = 64 * 1024
    }

    @Volatile private var running = false
    private var serverSocket: ServerSocket? = null

    override fun onCreate() {
        super.onCreate()
        startServer()
        Log.d(TAG, "CCCDATA service_created pid=${android.os.Process.myPid()}")
    }

    private fun startServer() {
        if (running) return
        running = true
        thread(name = "bridge-accept") {
            try {
                val ss = ServerSocket(PORT)
                serverSocket = ss
                Log.d(TAG, "CCCDATA server_listening port=$PORT pid=${android.os.Process.myPid()}")
                while (running) {
                    val client = try { ss.accept() } catch (e: Exception) { break }
                    handleClient(client)
                }
            } catch (e: Exception) {
                Log.e(TAG, "CCCDATA server_error msg=${e.message}")
            }
        }
    }

    /** Reads one length-prefixed payload and logs the measured server-side duration. */
    private fun handleClient(socket: Socket) {
        thread(name = "bridge-client") {
            socket.use { s ->
                try {
                    s.tcpNoDelay = true
                    val input = DataInputStream(s.getInputStream())
                    // 4-byte big-endian payload length
                    val payloadBytes = input.readInt()
                    val t0 = System.nanoTime()
                    var remaining = payloadBytes.toLong()
                    val buf = ByteArray(READ_BUF)
                    while (remaining > 0) {
                        val toRead = if (remaining > READ_BUF) READ_BUF else remaining.toInt()
                        val n = input.read(buf, 0, toRead)
                        if (n < 0) break
                        remaining -= n
                    }
                    val elapsedMs = (System.nanoTime() - t0) / 1_000_000.0
                    val mb = payloadBytes / (1024.0 * 1024.0)
                    // ACK one byte so the client can measure round-trip completion
                    s.getOutputStream().write(1)
                    s.getOutputStream().flush()
                    Log.d(
                        TAG,
                        "CCCDATA recv_complete payload_bytes=$payloadBytes payload_mb=%.4f server_recv_ms=%.3f"
                            .format(mb, elapsedMs)
                    )
                } catch (e: Exception) {
                    Log.e(TAG, "CCCDATA recv_error msg=${e.message}")
                }
            }
        }
    }

    override fun onBind(intent: Intent?): IBinder? = null  // socket transport; no Binder iface

    override fun onDestroy() {
        running = false
        try { serverSocket?.close() } catch (_: Exception) {}
        Log.d(TAG, "CCCDATA service_destroyed pid=${android.os.Process.myPid()}")
        super.onDestroy()
    }
}
