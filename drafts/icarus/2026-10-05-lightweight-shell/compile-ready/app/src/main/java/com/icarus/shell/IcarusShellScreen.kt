package com.aistudio.icarus.appsscript

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
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
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.unit.dp

@Composable
fun IcarusShellScreen(
    state: IcarusUiState,
    onProblemChanged: (String) -> Unit,
    onRecoveryTokenChanged: (String) -> Unit,
    onActivateRecovery: () -> Unit,
    onSubmit: () -> Unit,
    onReset: () -> Unit,
    onForgetRecovery: () -> Unit
) {
    Column(
        modifier = Modifier
            .fillMaxSize()
            .verticalScroll(rememberScrollState())
            .padding(24.dp),
        verticalArrangement = Arrangement.spacedBy(16.dp),
        horizontalAlignment = Alignment.CenterHorizontally
    ) {
        Text(
            "ICARUS",
            style = MaterialTheme.typography.headlineLarge,
            fontWeight = FontWeight.Bold
        )
        Text("Clean recovery build 0.5.0")

        if (state.stage == TaskStage.RECOVERY_REQUIRED) {
            Text("One-time recovery", fontWeight = FontWeight.Bold)
            Text("Enter the recovery token supplied with this APK. No pairing code is required.")

            OutlinedTextField(
                value = state.recoveryToken,
                onValueChange = onRecoveryTokenChanged,
                label = { Text("Recovery token") },
                visualTransformation = PasswordVisualTransformation(),
                modifier = Modifier.fillMaxWidth(),
                singleLine = true
            )

            Button(
                onClick = onActivateRecovery,
                modifier = Modifier.fillMaxWidth()
            ) {
                Text("Recover device")
            }
        } else {
            if (state.runtime.isNotBlank()) Text("Runtime: ${state.runtime}")

            OutlinedTextField(
                value = state.problem,
                onValueChange = onProblemChanged,
                label = { Text("Task") },
                placeholder = { Text("What should Icarus do?") },
                modifier = Modifier.fillMaxWidth(),
                minLines = 3
            )

            Button(
                onClick = onSubmit,
                enabled = state.stage !in setOf(TaskStage.SUBMITTING, TaskStage.EXECUTING),
                modifier = Modifier.fillMaxWidth()
            ) {
                Text(if (state.stage == TaskStage.SUBMITTING) "Submitting…" else "Submit")
            }

            Text(
                "STATUS: ${state.stage.name}",
                style = MaterialTheme.typography.titleMedium
            )

            if (state.result.isNotBlank()) {
                Text(state.result, modifier = Modifier.fillMaxWidth())
            }

            if (state.proof.isNotEmpty()) {
                Column(
                    modifier = Modifier.fillMaxWidth(),
                    verticalArrangement = Arrangement.spacedBy(6.dp)
                ) {
                    Text("Evidence", fontWeight = FontWeight.Bold)
                    state.proof.forEach { Text("${it.label}: ${it.value}") }
                }
            }

            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(12.dp)
            ) {
                Button(onClick = onReset, modifier = Modifier.weight(1f)) {
                    Text("New task")
                }
                Button(onClick = onForgetRecovery, modifier = Modifier.weight(1f)) {
                    Text("Reset device")
                }
            }
        }

        if (state.error.isNotBlank()) {
            Text(
                state.error,
                color = MaterialTheme.colorScheme.error,
                modifier = Modifier.fillMaxWidth()
            )
        }
    }
}
