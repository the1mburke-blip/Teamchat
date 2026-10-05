package com.icarus.shell

import androidx.lifecycle.MutableStateFlow
import androidx.lifecycle.StateFlow
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
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

data class TaskResult(val stage: TaskStage, val summary: String, val proof: List<ProofItem> = emptyList())

interface ExecutionGateway {
    suspend fun submit(request: TaskRequest): TaskResult
    suspend fun cancel()
}

class FakeExecutionGateway : ExecutionGateway {
    override suspend fun submit(request: TaskRequest): TaskResult {
        return TaskResult(
            stage = TaskStage.SUBMITTING,
            summary = "DEMO: Submitting task",
            proof = listOf(ProofItem(label = "Label 1", value = "Value 1"))
        )
    }

    override suspend fun cancel() {
        // No-op
    }
}

data class IcarusUiState(
    val problem: String,
    val listening: Boolean,
    val stage: TaskStage,
    val result: String,
    val proof: List<ProofItem>,
    val error: String
)

class IcarusViewModel(private val executionGateway: ExecutionGateway) : ViewModel() {
    private val _uiState = MutableStateFlow(IcarusUiState(problem = "", listening = false, stage = TaskStage.IDLE, result = "", proof = emptyList(), error = ""))
    val uiState: StateFlow<IcarusUiState> = _uiState

    fun onProblemChanged(newProblem: String) {
        _uiState.value = _uiState.value.copy(problem = newProblem)
    }

    fun onVoiceToggle(isListening: Boolean) {
        _uiState.value = _uiState.value.copy(listening = isListening)
    }

    fun submit() {
        if (_uiState.value.stage == TaskStage.IDLE) {
            _uiState.value = _uiState.value.copy(stage = TaskStage.SUBMITTING)
            viewModelScope.launch {
                try {
                    val result = executionGateway.submit(TaskRequest(problem = _uiState.value.problem))
                    _uiState.value = _uiState.value.copy(
                        stage = result.stage,
                        result = result.summary,
                        proof = result.proof
                    )
                } catch (e: Exception) {
                    _uiState.value = _uiState.value.copy(
                        stage = TaskStage.FAILED,
                        error = e.message ?: "Unknown error"
                    )
                }
            }
        }
    }

    fun cancel() {
        _uiState.value = _uiState.value.copy(stage = TaskStage.CANCELLED)
        viewModelScope.launch {
            executionGateway.cancel()
        }
    }

    fun newTask() {
        _uiState.value = _uiState.value.copy(
            problem = "",
            stage = TaskStage.IDLE,
            result = "",
            proof = emptyList(),
            error = ""
        )
    }
}
