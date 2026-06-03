package com.example.myapplication

import android.app.Activity
import android.app.Application
import android.os.Bundle

/**
 * AppForegroundTracker — the Android foreground-gate analogue of CoreWindow.Activated.
 *
 * Tracks whether any Activity is currently resumed. The gated ReconnectWorker consults
 * [isForeground] to implement Background Passivity (LQIA L3 correction): reconnection is
 * permitted only in the foreground, exactly mirroring the Windows solution's
 * Creation Isolation via CoreWindow.Activated.
 *
 * Register from Application.onCreate():
 *     registerActivityLifecycleCallbacks(AppForegroundTracker)
 */
object AppForegroundTracker : Application.ActivityLifecycleCallbacks {

    @Volatile var isForeground: Boolean = false
        private set

    private var resumedCount = 0

    override fun onActivityResumed(activity: Activity) {
        resumedCount++
        isForeground = resumedCount > 0
    }

    override fun onActivityPaused(activity: Activity) {
        resumedCount = (resumedCount - 1).coerceAtLeast(0)
        isForeground = resumedCount > 0
    }

    override fun onActivityCreated(a: Activity, s: Bundle?) {}
    override fun onActivityStarted(a: Activity) {}
    override fun onActivityStopped(a: Activity) {}
    override fun onActivitySaveInstanceState(a: Activity, o: Bundle) {}
    override fun onActivityDestroyed(a: Activity) {}
}
