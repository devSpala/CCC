package com.example.myapplication

import android.util.Log
import kotlin.concurrent.thread

/**
 * ForegroundSweep — measures the transport cost curve in the FOREGROUND (no Doze).
 *
 * For each payload size, performs [reps] sends and logs each one as a CCCDATA send_complete
 * line (tag=fg_sweep). The analysis script fits T_payload(P) = kappa * P^alpha across the
 * per-rep medians, with variance from the reps — supplying the repeated-trial statistics
 * the single-trial Windows characterisation lacked.
 *
 * Default sweep brackets the expected knee; adjust PAYLOADS_MB to taste.
 */
object ForegroundSweep {

    private const val TAG = "CCCHarness"
    // Bracket a wide range; the knee for loopback TCP under a shrunken Doze window
    // typically lands somewhere in here. Extend upward if your measured knee is higher.
    private val PAYLOADS_MB = intArrayOf(1, 2, 5, 10, 25, 50, 100, 150, 200)

    @Volatile private var busy = false

    fun run(reps: Int = 30) {
        if (busy) { Log.d(TAG, "CCCDATA sweep_busy"); return }
        busy = true
        thread(name = "fg-sweep") {
            Log.d(TAG, "CCCDATA sweep_start reps=$reps sizes_mb=${PAYLOADS_MB.joinToString(",")}")
            for (mb in PAYLOADS_MB) {
                val bytes = mb * 1024 * 1024
                for (r in 0 until reps) {
                    SocketTransport.sendPayload(bytes, "fg_sweep")
                    Thread.sleep(50)   // small gap so transfers don't queue
                }
                Log.d(TAG, "CCCDATA sweep_size_done payload_mb=$mb reps=$reps")
            }
            Log.d(TAG, "CCCDATA sweep_done")
            busy = false
        }
    }
}
