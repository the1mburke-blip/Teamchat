package com.aistudio.icarus.appsscript

/**
 * Contract for future Hermes executor binding.
 * Pure data definitions, no runtime logic.
 */
object HermesExecutorContract {
    /** Represents a request from Icarus to Hermes */
    data class Request(
        val capability: String,
        val payload: Any?
    )

    /** Represents a response from Hermes back to Icarus */
    sealed class Response {
        data class Denied(val reason: String) : Response()
        data class Accepted(val result: Any?) : Response()
    }

    /** Marker interface for future executor implementations */
    interface Executor {
        fun execute(request: Request): Response
    }
}
