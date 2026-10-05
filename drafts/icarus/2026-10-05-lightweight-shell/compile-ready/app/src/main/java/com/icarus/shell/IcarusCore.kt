package com.icarus.shell

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import kotlinx.coroutines.delay
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

class FakeExecutionGateway : ExecutionGateway {
    override suspend fun submit(request: TaskRequest): TaskResult {
        delay(300)
        return TaskResult(
            stage = TaskStage.VERIFYING,
            summary = "DEMO: request accepted by local gateway stub",
            proof = listOf(
                ProofItem(
                    label = "DEMO: request",
                    value = "DEMO: ${request.problem.take(80)}"
                )
            )
        )
    }

    override suspend fun cancel() = Unit
}

data class IcarusUiState(
    val problem: String = "",
    val listening: Boolean = false,
    val stage: TaskStage = TaskStage.IDLE,
    val result: String = "",
    val proof: List<ProofItem> = emptyList(),
    val error: String = ""
)

class IcarusViewModel(
    private val executionGateway: ExecutionGateway = FakeExecutionGateway()
) : ViewModel() {
    private val _uiState = MutableStateFlow(IcarusUiState())
    val uiState: StateFlow<IcarusUiState> = _uiState.asStateFlow()

    fun onProblemChanged(problem: String) {
        _uiState.value = _uiState.value.copy(problem = problem, error = "")
    }

    fun onVoiceToggle() {
        _uiState.value = _uiState.value.copy(listening = !_uiState.value.listening)
    }

    fun submit() {
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

        viewModelScope.launch {
            try {
                val result = executionGateway.submit(TaskRequest(problem))
                _uiState.value = _uiState.value.copy(
                    stage = result.stage,
                    result = result.summary,
                    proof = result.proof
                )
            } catch (t: Throwable) {
                _uiState.value = _uiState.value.copy(
                    stage = TaskStage.FAILED,
                    error = t.message ?: "Execution failed."
                )
            }
        }
    }

    fun cancel() {
        viewModelScope.launch {
            executionGateway.cancel()
            _uiState.value = _uiState.value.copy(
                listening = false,
                stage = TaskStage.IDLE,
                result = "DEMO: task cancelled locally",
                proof = emptyList(),
                error = ""
            )
        }
    }

    fun newTask() {
        _uiState.value = IcarusUiState()
    }
}
