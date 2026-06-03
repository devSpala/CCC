package com.example.myapplication

import android.app.Application

/**
 * HarnessApp — registers the foreground tracker so the gated worker variant can consult
 * live foreground state. Reference from the manifest: android:name=".HarnessApp".
 */
class HarnessApp : Application() {
    override fun onCreate() {
        super.onCreate()
        registerActivityLifecycleCallbacks(AppForegroundTracker)
    }
}
