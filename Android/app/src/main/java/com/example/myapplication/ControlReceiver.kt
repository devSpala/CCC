package com.example.myapplication

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.util.Log

/**
 * ControlReceiver — drives the harness entirely from adb (no screen interaction needed).
 *
 * Register in the manifest with android:exported="true". Trigger with:
 *
 *   # 1) Foreground transport sweep (measures kappa, alpha) -- keep app in foreground:
 *   adb shell am broadcast -a com.example.myapplication.SWEEP --es reps 30
 *
 *   # 2) Single background reconnect attempt at a given payload (used under forced Doze):
 *   adb shell am broadcast -a com.example.myapplication.RECONNECT \
 *        --ei payload_mb 50 --ez gated false --ei max_retries 20
 *
 *   # 3) Window-probe: tiny payload background worker to measure the usable Doze window:
 *   adb shell am broadcast -a com.example.myapplication.RECONNECT \
 *        --ei payload_mb 1 --ez gated false --ei max_retries 0
 */
class ControlReceiver : BroadcastReceiver() {

    companion object { private const val TAG = "CCCHarness" }

    override fun onReceive(context: Context, intent: Intent) {
        // Match on the action SUFFIX so the package prefix is irrelevant.
        // This avoids the class of bug where the manifest action and the compiled
        // string literal disagree after a package rename. Any action ending in
        // ".SWEEP" or ".RECONNECT" (or bare "SWEEP"/"RECONNECT") is accepted.
        val action = intent.action ?: ""
        when {
            action.endsWith("SWEEP") -> {
                val reps = intent.getIntExtra("reps", 30)
                Log.d(TAG, "CCCDATA cmd_sweep reps=$reps")
                ForegroundSweep.run(reps)
            }
            action.endsWith("RECONNECT") -> {
                val mb = intent.getIntExtra("payload_mb", 10)
                val gated = intent.getBooleanExtra("gated", false)
                val maxRetries = intent.getIntExtra("max_retries", 20)
                val bytes = mb * 1024 * 1024
                Log.d(TAG, "CCCDATA cmd_reconnect payload_mb=$mb gated=$gated max_retries=$maxRetries")
                WorkEnqueuer.enqueueReconnect(context, bytes, gated, runIndex = 0,
                    maxRetries = maxRetries)
            }
            else -> Log.d(TAG, "CCCDATA cmd_unknown action=${intent.action}")
        }
    }
}
