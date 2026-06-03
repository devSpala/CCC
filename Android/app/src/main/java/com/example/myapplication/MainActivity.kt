package com.example.myapplication

import android.content.Intent
import android.os.Bundle
import android.util.Log
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import kotlin.concurrent.thread

/**
 * MainActivity — UI host and AppService consumer analogue (the Windows "Pid1").
 *
 * Responsibilities:
 *   1. Start BridgeService (the :bridge process L2 endpoint) on launch.
 *   2. Provide on-screen buttons that fire the same actions as the adb broadcasts,
 *      so the harness is runnable with or without a host PC.
 *   3. Show the most recent CCCDATA status lines on screen for quick sanity checks.
 *
 * IMPORTANT: the authoritative measurement data is the logcat CCCDATA stream captured
 * by run_experiment.sh — the on-screen text is only a convenience mirror.
 */
class MainActivity : ComponentActivity() {

    companion object { private const val TAG = "CCCHarness" }

    private var status by mutableStateOf("starting…")

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        // Start the persistent L2 service (separate :bridge process).
        startService(Intent(this, BridgeService::class.java))
        status = "BridgeService started. Loopback port ${BridgeService.PORT}."
        Log.d(TAG, "CCCDATA ui_started port=${BridgeService.PORT}")

        setContent {
            MaterialTheme {
                Scaffold(modifier = Modifier.fillMaxSize()) { pad ->
                    Column(
                        modifier = Modifier
                            .fillMaxSize()
                            .padding(pad)
                            .padding(16.dp)
                            .verticalScroll(rememberScrollState()),
                        verticalArrangement = Arrangement.spacedBy(8.dp)
                    ) {
                        Text("CCCHarness", style = MaterialTheme.typography.headlineSmall)
                        Text(
                            "LQIA / Call Cycle Creation — Android reproduction",
                            style = MaterialTheme.typography.bodyMedium
                        )
                        Spacer(Modifier.height(8.dp))

                        // ---- Phase A: foreground transport sweep (measures kappa, alpha) ----
                        Button(
                            onClick = {
                                status = "Sweep started (keep app in foreground)…"
                                ForegroundSweep.run(reps = 30)
                            },
                            modifier = Modifier.fillMaxWidth()
                        ) { Text("Phase A · Foreground sweep (κ, α)") }

                        // ---- Quick single-payload send (manual transport check) ----
                        Button(
                            onClick = {
                                status = "Sending one 10 MB payload (foreground)…"
                                thread {
                                    val ms = SocketTransport.sendPayload(10 * 1024 * 1024, "fg_manual")
                                    runOnUiThread {
                                        status = if (ms >= 0) "10 MB sent in %.1f ms".format(ms)
                                        else "10 MB send FAILED (see logcat)"
                                    }
                                }
                            },
                            modifier = Modifier.fillMaxWidth()
                        ) { Text("Send one 10 MB payload (sanity check)") }

                        // ---- Phase B: window probe (run under forced Doze via adb) ----
                        Button(
                            onClick = {
                                status = "Window probe enqueued (force Doze via adb first)…"
                                WorkEnqueuer.enqueueReconnect(
                                    this@MainActivity, 1 * 1024 * 1024,
                                    gated = false, runIndex = 0, maxRetries = 0
                                )
                            },
                            modifier = Modifier.fillMaxWidth()
                        ) { Text("Phase B · Window probe (1 MB, no retry)") }

                        // ---- Phase C: unguarded reconnect at a knee-bracketing payload ----
                        Button(
                            onClick = {
                                status = "Unguarded reconnect @100 MB enqueued (force Doze first)…"
                                WorkEnqueuer.enqueueReconnect(
                                    this@MainActivity, 100 * 1024 * 1024,
                                    gated = false, runIndex = 0, maxRetries = 20
                                )
                            },
                            modifier = Modifier.fillMaxWidth()
                        ) { Text("Phase C · Unguarded reconnect @100 MB") }

                        // ---- Phase D: gated reconnect (remedy → no re-entry) ----
                        Button(
                            onClick = {
                                status = "Gated reconnect @100 MB enqueued…"
                                WorkEnqueuer.enqueueReconnect(
                                    this@MainActivity, 100 * 1024 * 1024,
                                    gated = true, runIndex = 0, maxRetries = 20
                                )
                            },
                            modifier = Modifier.fillMaxWidth()
                        ) { Text("Phase D · Gated reconnect @100 MB (remedy)") }

                        Spacer(Modifier.height(12.dp))
                        Text("Status", style = MaterialTheme.typography.titleSmall)
                        Text(
                            status,
                            fontFamily = FontFamily.Monospace,
                            fontSize = 12.sp
                        )
                        Spacer(Modifier.height(12.dp))
                        Text(
                            "All measurements are the CCCDATA lines in logcat. Capture with:\n" +
                                    "adb logcat -s CCCHarness:D",
                            fontFamily = FontFamily.Monospace,
                            fontSize = 11.sp
                        )
                    }
                }
            }
        }
    }
}
