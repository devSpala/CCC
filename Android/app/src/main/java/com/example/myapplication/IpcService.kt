package com.example.myapplication

import android.app.Service
import android.content.Intent
import android.os.Bundle
import android.os.Handler
import android.os.IBinder
import android.os.Looper
import android.os.Message
import android.os.Messenger
import android.util.Log
import java.io.ByteArrayOutputStream

class IpcService : Service() {

    companion object {
        private const val TAG = "IpcService"
        const val MSG_HELLO = 1
        const val MSG_CHUNK_START = 2
        const val MSG_CHUNK = 3
        const val MSG_CHUNK_END = 4
        const val MSG_CHUNK_ACK = 5

        const val KEY_MESSAGE = "key_message"
        const val KEY_CHUNK_DATA = "key_chunk_data"
        const val KEY_CHUNK_INDEX = "key_chunk_index"
        const val KEY_TOTAL_CHUNKS = "key_total_chunks"
        const val KEY_START_TIME = "key_start_time"
    }

    private var expectedChunks = 0
    private var receivedChunksCount = 0
    private var dataStream: ByteArrayOutputStream? = null
    private var startTimeMillis = 0L

    private val incomingHandler = object : Handler(Looper.getMainLooper()) {
        override fun handleMessage(msg: Message) {
            when (msg.what) {
                MSG_HELLO -> {
                    val data = msg.data
                    val message = data.getString(KEY_MESSAGE)
                    Log.d(TAG, "Received message in IPC process (PID ${android.os.Process.myPid()}): $message")
                }
                MSG_CHUNK_START -> {
                    val totalChunks = msg.data.getInt(KEY_TOTAL_CHUNKS)
                    startTimeMillis = msg.data.getLong(KEY_START_TIME, 0L)
                    expectedChunks = totalChunks
                    receivedChunksCount = 0
                    dataStream = ByteArrayOutputStream()
                    Log.d(TAG, "Starting chunked transfer in IPC process (PID ${android.os.Process.myPid()}). Expected chunks: $expectedChunks")
                    
                    // Acknowledge the start
                    sendAck(msg.replyTo, -1)
                }
                MSG_CHUNK -> {
                    val chunkIndex = msg.data.getInt(KEY_CHUNK_INDEX)
                    val chunkData = msg.data.getByteArray(KEY_CHUNK_DATA)
                    if (chunkData != null) {
                        dataStream?.write(chunkData)
                        receivedChunksCount++
                        Log.d(TAG, "Received chunk $chunkIndex of size ${chunkData.size} bytes. Total received so far: $receivedChunksCount / $expectedChunks")
                    }
                    
                    // Send ACK for this chunk
                    sendAck(msg.replyTo, chunkIndex)
                }
                MSG_CHUNK_END -> {
                    val endTimeMillis = System.currentTimeMillis()
                    val finalData = dataStream?.toByteArray()
                    val finalSize = finalData?.size ?: 0
                    val durationMs = if (startTimeMillis > 0) endTimeMillis - startTimeMillis else 0
                    Log.d(TAG, "Finished chunked transfer. Total size of reconstructed byte array in IPC process: $finalSize bytes (approx. ${finalSize / (1024.0 * 1024.0)} MB)")
                    Log.d(TAG, "Total transmission time (from send start to receive end): $durationMs ms")
                    
                    // Reset state
                    dataStream = null
                    expectedChunks = 0
                    receivedChunksCount = 0
                    startTimeMillis = 0L
                }
                else -> super.handleMessage(msg)
            }
        }
    }

    private fun sendAck(replyTo: Messenger?, chunkIndex: Int) {
        if (replyTo == null) return
        val reply = Message.obtain(null, MSG_CHUNK_ACK)
        reply.data = Bundle().apply {
            putInt(KEY_CHUNK_INDEX, chunkIndex)
        }
        try {
            replyTo.send(reply)
        } catch (e: Exception) {
            Log.e(TAG, "Failed to send ACK for chunk $chunkIndex", e)
        }
    }

    private lateinit var messenger: Messenger

    override fun onCreate() {
        super.onCreate()
        messenger = Messenger(incomingHandler)
        Log.d(TAG, "IpcService created in process: ${android.os.Process.myPid()}")
    }

    override fun onBind(intent: Intent?): IBinder? {
        Log.d(TAG, "IpcService bound in process: ${android.os.Process.myPid()}")
        return messenger.binder
    }
}
