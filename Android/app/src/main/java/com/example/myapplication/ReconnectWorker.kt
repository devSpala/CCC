package com.example.myapplication

import android.content.Context
import android.util.Log
import androidx.work.CoroutineWorker
import androidx.work.WorkerParameters

/**
 * ReconnectWorker — LQIA preconditions L1 (quota-bounded context) and L3 (recovery logic).
 *
 * Runs as an EXPEDITED WorkManager worker. When the host is in Doze, the expedited
 * quota + maintenance window bounds the execution budget (L1). The worker attempts to
 * re-establish the L2 socket connection and stream a payload.
 *
 * Two variants selected by input data key "gated":
 *   gated = false  -> UNGUARDED (L3 present): stream payload with NO budget check.
 *                     If the payload cannot complete before the window closes, WorkManager
 *                     reschedules the worker -> re-entry at S4 -> the CCC cycle.
 *   gated = true   -> FOREGROUND-GATED (L3 corrected): only proceed if the app is in the
 *                     foreground; otherwise abandon immediately (Background Passivity).
 *
 * Emits CCCDATA lines marking worker start, the S-step reached, and completion/failure.
 * A worker that returns Result.retry() will be re-dispatched by WorkManager; counting
 * those re-dispatches (via the run_index passed back in) is how cycle re-entry is observed.
 */
class ReconnectWorker(
    appContext: Context,
    params: WorkerParameters
) : CoroutineWorker(appContext, params) {

    companion object {
        private const val TAG = "CCCHarness"
        const val KEY_PAYLOAD_BYTES = "payload_bytes"
        const val KEY_GATED = "gated"
        const val KEY_RUN_INDEX = "run_index"
        const val KEY_MAX_RETRIES = "max_retries"
    }

    override suspend fun doWork(): Result {
        val payloadBytes = inputData.getInt(KEY_PAYLOAD_BYTES, 10 * 1024 * 1024)
        val gated = inputData.getBoolean(KEY_GATED, false)
        val runIndex = inputData.getInt(KEY_RUN_INDEX, 0)
        val maxRetries = inputData.getInt(KEY_MAX_RETRIES, 20)
        val mb = payloadBytes / (1024.0 * 1024.0)

        val tStart = System.currentTimeMillis()
        Log.d(TAG, "CCCDATA worker_start step=S4 run_index=$runIndex gated=$gated " +
                "payload_mb=%.4f attempt=$runAttemptCount".format(mb))

        // ---- L3 correction: Background Passivity (gated variant) ----
        if (gated && !AppForegroundTracker.isForeground) {
            Log.d(TAG, "CCCDATA worker_gated_skip step=S4 run_index=$runIndex " +
                    "reason=not_foreground")
            return Result.success()   // abandon: no reconnection in background
        }

        // ---- S5: recovery / payload stream ----
        Log.d(TAG, "CCCDATA worker_recovery step=S5 run_index=$runIndex")
        val tag = if (gated) "bg_worker_gated" else "bg_worker_unguarded"
        val elapsed = SocketTransport.sendPayload(payloadBytes, tag)

        val windowMs = System.currentTimeMillis() - tStart
        Log.d(TAG, "CCCDATA worker_window_observed run_index=$runIndex " +
                "observed_window_ms=$windowMs send_result_ms=%.3f".format(elapsed))

        return if (elapsed < 0) {
            // Transfer failed (e.g. connection frozen / window closed mid-stream) -> S6 preemption
            if (runIndex >= maxRetries) {
                Log.d(TAG, "CCCDATA worker_retry_cap run_index=$runIndex cap=$maxRetries " +
                        "note=stopping_to_bound_experiment")
                Result.failure()
            } else {
                // S7: cycle re-entry — WorkManager re-dispatches; we re-enqueue with index+1
                Log.d(TAG, "CCCDATA worker_reentry step=S7 next_run_index=${runIndex + 1}")
                WorkEnqueuer.enqueueReconnect(applicationContext, payloadBytes, gated,
                    runIndex + 1, maxRetries)
                Result.retry()
            }
        } else {
            Log.d(TAG, "CCCDATA worker_complete run_index=$runIndex outcome=success " +
                    "send_ms=%.3f".format(elapsed))
            Result.success()
        }
    }
}
