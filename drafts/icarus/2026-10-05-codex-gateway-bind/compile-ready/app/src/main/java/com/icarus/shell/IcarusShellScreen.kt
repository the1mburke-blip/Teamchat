package com.icarus.shell

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp

@Composable
fun IcarusShellScreen(
    state: IcarusUiState,
    onBackendUrlChanged: (String) -> Unit,
    onPairingCodeChanged: (String) -> Unit,
    onPair: () -> Unit,
    onProblemChanged: (String) -> Unit,
    onVoiceToggle: () -> Unit,
    onSubmit: () -> Unit,
    onCancel: () -> Unit,
    onNewTask: () -> Unit
) {
    Column(
        modifier = Modifier
            .fillMaxSize()
            .verticalScroll(rememberScrollState())
            .padding(24.dp),
        verticalArrangement = Arrangement.spacedBy(16.dp),
        horizontalAlignment = Alignment.CenterHorizontally
    ) {
        Spacer(Modifier.height(8.dp))
        Text(
            text = "ICARUS",
            style = MaterialTheme.typography.headlineLarge,
            fontWeight = FontWeight.Bold
        )
        Text(
            text = "State a problem. Icarus handles the execution behind this shell.",
            style = MaterialTheme.typography.bodyMedium
        )

        Text("Connection: ${state.connectionStatus}")
        if (!state.paired) {
            OutlinedTextField(value = state.backendUrl, onValueChange = onBackendUrlChanged, label = { Text("Apps Script HTTPS endpoint") }, modifier = Modifier.fillMaxWidth(), enabled = !state.connecting)
            OutlinedTextField(value = state.pairingCode, onValueChange = onPairingCodeChanged, label = { Text("One-time pairing code") }, visualTransformation = androidx.compose.ui.text.input.PasswordVisualTransformation(), modifier = Modifier.fillMaxWidth(), enabled = !state.connecting)
            Button(onClick = onPair, enabled = !state.connecting) { Text("Pair") }
        }
        Button(
            onClick = onVoiceToggle,
            enabled = false,
            modifier = Modifier
                .fillMaxWidth()
                .height(72.dp)
        ) {
            Text("Voice input unavailable")
        }

        OutlinedTextField(
            value = state.problem,
            onValueChange = onProblemChanged,
            label = { Text("Text fallback") },
            placeholder = { Text("Describe the problem") },
            modifier = Modifier.fillMaxWidth(),
            minLines = 3
        )

        Button(
            onClick = onSubmit,
            enabled = state.paired && state.problem.isNotBlank() && !state.connecting && state.stage !in setOf(
                TaskStage.SUBMITTING,
                TaskStage.EXECUTING,
                TaskStage.VERIFYING
            ),
            modifier = Modifier.fillMaxWidth()
        ) {
            Text("Submit")
        }

        Text(
            text = "STATUS: ${state.stage.name}",
            style = MaterialTheme.typography.titleMedium
        )

        if (state.result.isNotBlank()) {
            Text(
                text = state.result,
                modifier = Modifier.fillMaxWidth()
            )
        }

        if (state.proof.isNotEmpty()) {
            Column(
                modifier = Modifier.fillMaxWidth(),
                verticalArrangement = Arrangement.spacedBy(8.dp)
            ) {
                Text("Proof", fontWeight = FontWeight.Bold)
                state.proof.forEach { proof ->
                    Text("${proof.label}: ${proof.value}")
                }
            }
        }

        if (state.error.isNotBlank()) {
            Text(
                text = state.error,
                color = MaterialTheme.colorScheme.error,
                modifier = Modifier.fillMaxWidth()
            )
        }

        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.spacedBy(12.dp)
        ) {
            if (state.stage in setOf(
                    TaskStage.SUBMITTING,
                    TaskStage.EXECUTING,
                    TaskStage.VERIFYING
                )
            ) {
                Button(onClick = onCancel, modifier = Modifier.weight(1f)) {
                    Text("Stop waiting")
                }
            }

            if (state.stage in setOf(
                    TaskStage.VERIFYING,
                    TaskStage.PASS,
                    TaskStage.FAILED,
                    TaskStage.BLOCKED
                )
            ) {
                Button(onClick = onNewTask, modifier = Modifier.weight(1f)) {
                    Text("New Task")
                }
            }
        }
    }
}
