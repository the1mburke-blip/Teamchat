package com.aistudio.icarus.appsscript

import android.app.Application
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch

enum class TaskStage { RECOVERY_REQUIRED, IDLE, SUBMITTING, EXECUTING, AWAITING_OWNER, COMPLETE, FAILED, BLOCKED }

data class ProofItem(val label: String, val value: String)

data class IcarusUiState(
    val recoveryToken: String = "",
    val problem: String = "",
    val stage: TaskStage = TaskStage.RECOVERY_REQUIRED,
    val result: String = "",
    val proof: List<ProofItem> = emptyList(),
    val error: String = "",
    val runtime: String = ""
)

class IcarusViewModel(application: Application) : AndroidViewModel(application) {
    private val store = RecoveryStore(application)
    private val api = IcarusApiClient(store::endpoint) { RecoveryStore.DEVICE_ID }
    private val _uiState = MutableStateFlow(
        IcarusUiState(stage = if (store.token().isBlank()) TaskStage.RECOVERY_REQUIRED else TaskStage.IDLE)
    )
    val uiState: StateFlow<IcarusUiState> = _uiState.asStateFlow()

    fun onProblemChanged(problem: String) {
        _uiState.value = _uiState.value.copy(problem = problem, error = "")
    }

    fun onRecoveryTokenChanged(value: String) {
        _uiState.value = _uiState.value.copy(recoveryToken = value, error = "")
    }

    fun activateRecovery() {
        val token = _uiState.value.recoveryToken.trim()
        if (token.length < 24) {
            _uiState.value = _uiState.value.copy(error = "Enter the recovery token supplied with this build.")
            return
        }
        _uiState.value = _uiState.value.copy(stage = TaskStage.SUBMITTING, error = "")
        viewModelScope.launch {
            try {
                val runtime = api.runtime(token)
                store.saveToken(token)
                _uiState.value = _uiState.value.copy(
                    recoveryToken = "",
                    stage = TaskStage.IDLE,
                    runtime = "${runtime.runtimeVersion} / ${runtime.environment}",
                    result = "Device recovered. Ready for a new task.",
                    error = ""
                )
            } catch (t: Throwable) {
                _uiState.value = _uiState.value.copy(
                    stage = TaskStage.RECOVERY_REQUIRED,
                    error = t.message ?: "Recovery failed"
                )
            }
        }
    }

    fun submit() {
        val problem = _uiState.value.problem.trim()
        val token = store.token()
        if (token.isBlank()) {
            _uiState.value = _uiState.value.copy(
                stage = TaskStage.RECOVERY_REQUIRED,
                error = "Recovery token required."
            )
            return
        }
        if (problem.isBlank()) {
            _uiState.value = _uiState.value.copy(error = "Describe the task first.")
            return
        }

        _uiState.value = _uiState.value.copy(
            stage = TaskStage.SUBMITTING,
            result = "",
            proof = emptyList(),
            error = ""
        )

        viewModelScope.launch {
            try {
                val task = api.submit(token, problem)
                _uiState.value = _uiState.value.copy(
                    stage = mapStage(task.status),
                    result = task.resultText.ifBlank { task.evidence.ifBlank { task.status } },
                    proof = listOf(
                        ProofItem("Task", task.taskId),
                        ProofItem("Backend status", task.status),
                        ProofItem("Evidence", task.evidence)
                    ).filter { it.value.isNotBlank() },
                    error = ""
                )
            } catch (t: Throwable) {
                _uiState.value = _uiState.value.copy(
                    stage = TaskStage.FAILED,
                    error = t.message ?: "Execution failed"
                )
            }
        }
    }

    fun resetUi() {
        _uiState.value = _uiState.value.copy(
            problem = "",
            stage = TaskStage.IDLE,
            result = "",
            proof = emptyList(),
            error = ""
        )
    }

    fun forgetRecovery() {
        store.clearToken()
        _uiState.value = IcarusUiState(stage = TaskStage.RECOVERY_REQUIRED)
    }

    private fun mapStage(status: String): TaskStage = when (status.uppercase()) {
        "BLOCKED" -> TaskStage.BLOCKED
        "FAIL", "FAILED", "PARTIAL" -> TaskStage.FAILED
        "PASS" -> TaskStage.COMPLETE
        "WORK_COMPLETE_AWAITING_OWNER_VERIFICATION" -> TaskStage.AWAITING_OWNER
        "QUEUED", "INSPECTING", "REASONING", "EXECUTING", "VERIFYING", "PENDING_AUTH", "WAITING_REASONING_CAPACITY" -> TaskStage.EXECUTING
        else -> TaskStage.COMPLETE
    }
}
