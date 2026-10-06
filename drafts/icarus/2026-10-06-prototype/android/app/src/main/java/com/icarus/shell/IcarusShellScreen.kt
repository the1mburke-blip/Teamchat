package com.aistudio.icarus.appsscript

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
import androidx.compose.runtime.getValue
import androidx.compose.runtime.setValue
import androidx.compose.runtime.remember
import androidx.compose.runtime.mutableStateOf
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.unit.dp

@Composable
fun IcarusShellScreen(
    state: IcarusUiState,
    onBackendUrlChanged: (String) -> Unit,
    onDeviceIdChanged: (String) -> Unit,
    onRecoveryTokenChanged: (String) -> Unit,
    onRecover: () -> Unit,
    onGoogleConnect: () -> Unit,
    onProblemChanged: (String) -> Unit,
    onVoiceToggle: () -> Unit,
    onSubmit: () -> Unit,
    onCancel: () -> Unit,
    onNewTask: () -> Unit,
    onGoogleRefresh: () -> Unit,
    onGoogleAuthorize: (String) -> Unit,
    onRefresh: () -> Unit
) {
    Column(
        modifier = Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(24.dp),
        verticalArrangement = Arrangement.spacedBy(16.dp),
        horizontalAlignment = Alignment.CenterHorizontally
    ) {
        Spacer(Modifier.height(8.dp))
        Text("ICARUS", style = MaterialTheme.typography.headlineLarge, fontWeight = FontWeight.Bold)
        Text("State a problem. Icarus handles the execution behind this shell.", style = MaterialTheme.typography.bodyMedium)

        Text("Connection: ${state.connectionStatus}")
        if (!state.provisioned) {
            Button(onClick = onGoogleConnect, enabled = !state.connecting, modifier = Modifier.fillMaxWidth()) { Text("Sign in with Google") }
            Text("Use your authorized Google account to connect this phone.")
            var showRecovery by remember { mutableStateOf(false) }
            Button(onClick = { showRecovery = !showRecovery }, enabled = !state.connecting) { Text("Existing device recovery") }
            if (showRecovery) {
            OutlinedTextField(value = state.backendUrl, onValueChange = onBackendUrlChanged, label = { Text("Apps Script HTTPS endpoint") }, modifier = Modifier.fillMaxWidth(), enabled = !state.connecting)
            OutlinedTextField(value = state.deviceId, onValueChange = onDeviceIdChanged, label = { Text("Device ID") }, modifier = Modifier.fillMaxWidth(), enabled = !state.connecting)
            OutlinedTextField(value = state.recoveryToken, onValueChange = onRecoveryTokenChanged, label = { Text("Recovery token") }, visualTransformation = PasswordVisualTransformation(), modifier = Modifier.fillMaxWidth(), enabled = !state.connecting)
            Button(onClick = onRecover, enabled = !state.connecting, modifier = Modifier.fillMaxWidth()) { Text("Recover connection") }
            }
        }



        if (state.provisioned) {
            Text("Google connections", fontWeight = FontWeight.Bold)
            Text(state.googleConnectionMessage)
            Button(onClick = onGoogleRefresh) { Text("Refresh Google connections") }
            state.googleConnections.forEach { connection ->
                Text("${connection.service}: ${connection.state} ${connection.reason}")
                if (connection.service in setOf("gmail", "drive") && connection.state in setOf("MISSING", "EXPIRED", "REVOKED")) {
                    Button(onClick = { onGoogleAuthorize(connection.service) }) {
                        Text(if (connection.state == "MISSING") "Authorize ${connection.service}" else "Reconnect ${connection.service}")
                    }
                }
            }
        }

        OutlinedTextField(value = state.problem, onValueChange = onProblemChanged, label = { Text("Task") }, placeholder = { Text("Describe the problem") }, modifier = Modifier.fillMaxWidth(), minLines = 3)

        val active = state.stage in setOf(TaskStage.SUBMITTING, TaskStage.EXECUTING)
        Button(onClick = onSubmit, enabled = state.provisioned && state.problem.isNotBlank() && !state.connecting && !active, modifier = Modifier.fillMaxWidth()) { Text("Submit") }

        if (state.provisioned) Button(onClick = onRefresh, enabled = !active, modifier = Modifier.fillMaxWidth()) { Text("Refresh saved task") }

        Text("STATUS: ${state.stage.name}", style = MaterialTheme.typography.titleMedium)

        if (state.result.isNotBlank()) Text(state.result, modifier = Modifier.fillMaxWidth())

        if (state.proof.isNotEmpty()) {
            Column(modifier = Modifier.fillMaxWidth(), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                Text("Proof", fontWeight = FontWeight.Bold)
                state.proof.forEach { proof -> Text("${proof.label}: ${proof.value}") }
            }
        }

        if (state.error.isNotBlank()) Text(state.error, color = MaterialTheme.colorScheme.error, modifier = Modifier.fillMaxWidth())

        Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(12.dp)) {
            if (state.stage in setOf(TaskStage.SUBMITTING, TaskStage.EXECUTING)) {
                Button(onClick = onCancel, modifier = Modifier.weight(1f)) { Text("Stop waiting") }
            }
            if (state.stage in setOf(TaskStage.VERIFYING, TaskStage.PASS, TaskStage.FAILED, TaskStage.BLOCKED, TaskStage.OUTCOME_UNKNOWN)) {
                Button(onClick = onNewTask, modifier = Modifier.weight(1f)) { Text("New Task") }
            }
        }
    }
}
