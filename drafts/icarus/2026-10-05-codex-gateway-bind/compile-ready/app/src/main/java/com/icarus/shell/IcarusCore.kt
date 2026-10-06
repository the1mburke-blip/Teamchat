package com.icarus.shell

import android.app.Application
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.Job
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch

enum class TaskStage {
    IDLE,
    SUBMITTING,
    EXECUTING,
    VERIFYING,
    PASS,
    FAILED,
    BLOCKED
}

data class TaskRequest(val problem: String)

data class ProofItem(val label: String, val value: String)

data class TaskResult(
    val stage: TaskStage,
    val summary: String,
    val proof: List<ProofItem> = emptyList()
)

interface ExecutionGateway {
    suspend fun submit(request: TaskRequest): TaskResult
    suspend fun cancel()
}

data class IcarusUiState(
    val backendUrl: String = "",
    val pairingCode: String = "",
    val paired: Boolean = false,
    val connectionStatus: String = "Not paired",
    val connecting: Boolean = false,
    val problem: String = "",
    val listening: Boolean = false,
    val stage: TaskStage = TaskStage.IDLE,
    val result: String = "",
    val proof: List<ProofItem> = emptyList(),
    val error: String = ""
)

class IcarusViewModel(app: Application) : AndroidViewModel(app) {
    private val executionGateway = AppsScriptExecutionGateway(app)
    private var taskJob: Job? = null

    private val _uiState = MutableStateFlow(
        IcarusUiState(
            backendUrl = executionGateway.backendUrl(),
            paired = executionGateway.isPaired(),
            connectionStatus = if (executionGateway.isPaired()) "Paired" else "Not paired"
        )
    )
    val uiState: StateFlow<IcarusUiState> = _uiState.asStateFlow()

    fun onBackendUrlChanged(value: String) {
        if (taskJob?.isActive == true) return
        _uiState.value = _uiState.value.copy(
            backendUrl = value,
            paired = false,
            connectionStatus = "Not paired",
            error = ""
        )
    }

    fun onPairingCodeChanged(value: String) {
        _uiState.value = _uiState.value.copy(pairingCode = value, error = "")
    }

    fun pair() {
        if (_uiState.value.connecting || taskJob?.isActive == true) return

        val state = _uiState.value
        val uri = runCatching { java.net.URI(state.backendUrl.trim()) }.getOrNull()
        if (
            uri == null ||
            uri.scheme != "https" ||
            uri.host.isNullOrBlank() ||
            state.pairingCode.isBlank()
        ) {
            _uiState.value = state.copy(
                error = "HTTPS endpoint and pairing code required."
            )
            return
        }

        _uiState.value = state.copy(connecting = true, error = "")
        viewModelScope.launch {
            try {
                executionGateway.setBackendUrl(state.backendUrl)
                executionGateway.pair(state.pairingCode.trim())
                _uiState.value = _uiState.value.copy(
                    paired = true,
                    pairingCode = "",
                    connecting = false,
                    connectionStatus = "Paired",
                    error = ""
                )
            } catch (t: Throwable) {
                _uiState.value = _uiState.value.copy(
                    paired = executionGateway.isPaired(),
                    connecting = false,
                    connectionStatus =
                        if (executionGateway.isPaired()) "Paired" else "Not paired",
                    error = (t.message ?: "Pair failed.").take(240)
                )
            }
        }
    }

    fun onProblemChanged(problem: String) {
        _uiState.value = _uiState.value.copy(problem = problem, error = "")
    }

    fun onVoiceToggle() {
        _uiState.value = _uiState.value.copy(
            listening = !_uiState.value.listening
        )
    }

    fun submit() {
        if (
            taskJob?.isActive == true ||
            !_uiState.value.paired ||
            _uiState.value.connecting
        ) {
            return
        }

        val problem = _uiState.value.problem.trim()
        if (problem.isEmpty()) {
            _uiState.value = _uiState.value.copy(
                error = "Describe the problem first."
            )
            return
        }

        _uiState.value = _uiState.value.copy(
            listening = false,
            stage = TaskStage.SUBMITTING,
            result = "",
            proof = emptyList(),
            error = ""
        )

        taskJob = viewModelScope.launch {
            try {
                val result = executionGateway.submit(TaskRequest(problem))
                _uiState.value = _uiState.value.copy(
                    stage = result.stage,
                    result = result.summary,
                    proof = result.proof,
                    error = ""
                )
            } catch (t: CancellationException) {
                throw t
            } catch (t: Throwable) {
                _uiState.value = _uiState.value.copy(
                    stage = TaskStage.FAILED,
                    result = "",
                    proof = emptyList(),
                    error =
                        (t.message
                            ?: "Gateway request failed; remote outcome may be unknown.")
                            .take(300)
                )
            } finally {
                taskJob = null
            }
        }
    }

    fun cancel() {
        viewModelScope.launch {
            executionGateway.cancel()
            taskJob?.cancel()
            taskJob = null
            _uiState.value = _uiState.value.copy(
                listening = false,
                stage = TaskStage.IDLE,
                result = "Stopped waiting locally; remote task may continue.",
                proof = emptyList(),
                error = ""
            )
        }
    }

    fun newTask() {
        if (_uiState.value.connecting) return
        if (taskJob?.isActive == true) {
            taskJob?.cancel()
            taskJob = null
        }

        val old = _uiState.value
        _uiState.value = IcarusUiState(
            backendUrl = old.backendUrl,
            paired = old.paired,
            connectionStatus = old.connectionStatus
        )
    }
}
