package com.aistudio.icarus.appsscript

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
    BLOCKED,
    OUTCOME_UNKNOWN
}

data class TaskRequest(val problem: String)
data class ProofItem(val label: String, val value: String)
data class TaskResult(val stage: TaskStage, val summary: String, val proof: List<ProofItem> = emptyList())

interface ExecutionGateway {
    suspend fun submit(request: TaskRequest): TaskResult
    suspend fun cancel()
}

data class IcarusUiState(
    val backendUrl: String = "",
    val deviceId: String = "",
    val recoveryToken: String = "",
    val provisioned: Boolean = false,
    val connectionStatus: String = "Recovery required",
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
            deviceId = executionGateway.deviceId(),
            provisioned = executionGateway.isProvisioned(),
            connectionStatus = if (executionGateway.isProvisioned()) "Recovered" else "Recovery required"
        )
    )
    val uiState: StateFlow<IcarusUiState> = _uiState.asStateFlow()

    init {
        if (executionGateway.isProvisioned() && executionGateway.lastTaskId().isNotBlank()) refreshTask()
    }

    fun refreshTask() {
        if (taskJob?.isActive == true || !_uiState.value.provisioned) return
        taskJob = viewModelScope.launch {
            try {
                val result = executionGateway.refreshTask()
                _uiState.value = _uiState.value.copy(stage = result.stage, result = result.summary, proof = result.proof, error = "")
            } catch (t: CancellationException) {
                throw t
            } catch (t: Exception) {
                _uiState.value = _uiState.value.copy(stage = TaskStage.OUTCOME_UNKNOWN, error = "Could not refresh the saved task; no new task was submitted.")
            } finally {
                taskJob = null
            }
        }
    }

    fun onBackendUrlChanged(value: String) {
        if (!_uiState.value.provisioned && taskJob?.isActive != true) {
            _uiState.value = _uiState.value.copy(backendUrl = value, error = "")
        }
    }

    fun onDeviceIdChanged(value: String) {
        if (!_uiState.value.provisioned && taskJob?.isActive != true) {
            _uiState.value = _uiState.value.copy(deviceId = value, error = "")
        }
    }

    fun onRecoveryTokenChanged(value: String) {
        if (!_uiState.value.provisioned && taskJob?.isActive != true) {
            _uiState.value = _uiState.value.copy(recoveryToken = value, error = "")
        }
    }

    fun recover() {
        if (_uiState.value.connecting || taskJob?.isActive == true || _uiState.value.provisioned) return
        val state = _uiState.value
        if (state.backendUrl.isBlank() || state.deviceId.isBlank() || state.recoveryToken.isBlank()) {
            _uiState.value = state.copy(error = "Endpoint, device ID and recovery token are required.")
            return
        }
        _uiState.value = state.copy(connecting = true, error = "", connectionStatus = "Verifying recovery...")
        viewModelScope.launch {
            try {
                val runtime = executionGateway.recover(state.backendUrl, state.deviceId, state.recoveryToken)
                _uiState.value = _uiState.value.copy(
                    provisioned = true,
                    recoveryToken = "",
                    connecting = false,
                    connectionStatus = "Recovered - $runtime",
                    error = ""
                )
            } catch (_: Exception) {
                _uiState.value = _uiState.value.copy(
                    provisioned = false,
                    recoveryToken = "",
                    connecting = false,
                    connectionStatus = "Recovery failed",
                    error = "Recovery verification failed. Check the three recovery values before retrying."
                )
            }
        }
    }

    fun onProblemChanged(problem: String) {
        _uiState.value = _uiState.value.copy(problem = problem, error = "")
    }

    fun onVoiceToggle() {
        _uiState.value = _uiState.value.copy(listening = !_uiState.value.listening)
    }

    fun submit() {
        if (taskJob?.isActive == true || !_uiState.value.provisioned || _uiState.value.connecting) return
        val problem = _uiState.value.problem.trim()
        if (problem.isEmpty()) {
            _uiState.value = _uiState.value.copy(error = "Describe the problem first.")
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
            } catch (t: Exception) {
                _uiState.value = _uiState.value.copy(
                    stage = TaskStage.FAILED,
                    result = "",
                    error = t.message ?: "Gateway request failed."
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
            _uiState.value = _uiState.value.copy(
                listening = false,
                stage = TaskStage.OUTCOME_UNKNOWN,
                result = "Stopped waiting locally; the remote task may still continue.",
                proof = emptyList(),
                error = ""
            )
        }
    }

    fun newTask() {
        if (taskJob?.isActive == true || _uiState.value.connecting) return
        val old = _uiState.value
        _uiState.value = IcarusUiState(
            backendUrl = old.backendUrl,
            deviceId = old.deviceId,
            provisioned = old.provisioned,
            connectionStatus = old.connectionStatus
        )
    }
}
