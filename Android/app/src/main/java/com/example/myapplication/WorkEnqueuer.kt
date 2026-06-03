package com.example.myapplication

import android.content.Context
import androidx.work.BackoffPolicy
import androidx.work.Data
import androidx.work.ExistingWorkPolicy
import androidx.work.OneTimeWorkRequestBuilder
import androidx.work.OutOfQuotaPolicy
import androidx.work.WorkManager
import java.util.concurrent.TimeUnit

/**
 * WorkEnqueuer — enqueues the expedited ReconnectWorker (LQIA L1 context).
 *
 * setExpedited(...) requests expedited execution; under Doze this is bounded by the
 * expedited quota / maintenance window, establishing the quota-bounded context (L1).
 */
object WorkEnqueuer {

    const val UNIQUE_NAME = "ccc_reconnect"

    fun enqueueReconnect(
        context: Context,
        payloadBytes: Int,
        gated: Boolean,
        runIndex: Int = 0,
        maxRetries: Int = 20
    ) {
        val data = Data.Builder()
            .putInt(ReconnectWorker.KEY_PAYLOAD_BYTES, payloadBytes)
            .putBoolean(ReconnectWorker.KEY_GATED, gated)
            .putInt(ReconnectWorker.KEY_RUN_INDEX, runIndex)
            .putInt(ReconnectWorker.KEY_MAX_RETRIES, maxRetries)
            .build()

        val req = OneTimeWorkRequestBuilder<ReconnectWorker>()
            .setInputData(data)
            .setExpedited(OutOfQuotaPolicy.RUN_AS_NON_EXPEDITED_WORK_REQUEST)
            .setBackoffCriteria(BackoffPolicy.LINEAR, 1, TimeUnit.SECONDS)
            .build()

        // REPLACE so each re-entry is the single active worker under the unique name.
        WorkManager.getInstance(context)
            .enqueueUniqueWork(UNIQUE_NAME, ExistingWorkPolicy.REPLACE, req)
    }
}
