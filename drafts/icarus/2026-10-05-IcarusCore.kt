package com.icarus.shell

import androidx.lifecycle.MutableStateFlow
import androidx.lifecycle.StateFlow
import androidx.lifecycle.ViewModel
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

data class ProofItem(
    val id: Int,
    val text: String
)

data class IcarusUiState(
    val problemText: String = "",
    val listening: Boolean = false,
    val stage: TaskStage = TaskStage.IDLE,
    val conciseResult: String = "",
    val proofList: List<ProofItem> = emptyList(),
    val error: String? = null
)

data class IcarusBackendResult(
    val success: Boolean,
    val evidence: String
)

interface IcarusGateway {
    suspend fun submit(problem: String): IcarusBackendResult
    suspend fun cancel(): Unit
}

class FakeIcarusGateway : IcarusGateway {
    override suspend fun submit(problem: String): IcarusBackendResult {
        delay(1000) // Simulate delay
        return IcarusBackendResult(true, "DEMO: Problem submitted")
    }

    override suspend fun cancel(): Unit {
        // No-op
    }
}

class IcarusViewModel : ViewModel() {
    private val _uiState = MutableStateFlow(IcarusUiState())
    val uiState: StateFlow<IcarusUiState> = _uiState

    fun onProblemChanged(newProblem: String) {
        _uiState.value = _uiState.value.copy(problemText = newProblem)
    }

    fun onVoiceToggle(isListening: Boolean) {
        _uiState.value = _uiState.value.copy(listening = isListening)
    }

    fun submit() {
        if (_uiState.value.problemText.isEmpty()) {
            _uiState.value = _uiState.value.copy(error = "Problem text cannot be empty")
            return
        }

        viewModelScope.launch {
            val result = try {
                IcarusGateway().submit(_uiState.value.problemText)
            } catch (e: Exception) {
                e.printStackTrace()
                return@launch
            }

            if (result.success) {
                _uiState.value = _uiState.value.copy(
                    stage = TaskStage.PASS,
                    conciseResult = result.evidence
                )
            } else {
                _uiState.value = _uiState.value.copy(
                    stage = TaskStage.FAILED,
                    conciseResult = result.evidence
                )
            }
        }
    }

    fun cancel() {
        viewModelScope.launch {
            IcarusGateway().cancel()
        }
    }

    fun newTask() {
        _uiState.value = _uiState.value.copy(
            problemText = "",
            listening = false,
            stage = TaskStage.IDLE,
            conciseResult = "",
            proofList = emptyList(),
            error = null
        )
    }
}
