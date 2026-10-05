package com.icarus.shell

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.text.Text
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp

@Composable
fun IcarusShellScreen(
    state: IcarusUiState,
    onProblemChanged: (String) -> Unit,
    onVoiceToggle: () -> Unit,
    onSubmit: () -> Unit,
    onCancel: () -> Unit,
    onNewTask: () -> Unit
) {
    val context = LocalContext.current
    val isSubmitting = remember { mutableStateOf(false) }

    Column(
        modifier = Modifier.fillMaxSize(),
        verticalArrangement = Arrangement.Center,
        horizontalAlignment = Alignment.Center
    ) {
        Text(
            text = "ICARUS",
            style = TextStyle(fontSize = 48.sp, fontWeight = FontWeight.Bold),
            modifier = Modifier.padding(16.dp)
        )

        VoiceButton(
            text = if (state.stage == IcarusStage.SPEAKING) "Listening…" else "Speak to Icarus",
            onClick = onVoiceToggle,
            modifier = Modifier.padding(16.dp)
        )

        OutlinedTextField(
            value = state.textFallback,
            onValueChange = { onProblemChanged(it) },
            placeholder = { Text(text = "Enter your problem") },
            modifier = Modifier.padding(16.dp)
        )

        SubmitButton(
            onClick = {
                if (state.stage == IcarusStage.SPEAKING) {
                    onVoiceToggle()
                    isSubmitting.value = true
                } else {
                    onSubmit()
                }
            },
            modifier = Modifier.padding(16.dp)
        )

        ResultSection(
            result = state.result,
            modifier = Modifier.padding(16.dp)
        )

        ProofEvidenceSection(
            proof = state.proof,
            modifier = Modifier.padding(16.dp)
        )

        ErrorText(
            error = state.error,
            modifier = Modifier.padding(16.dp)
        )

        if (state.stage == IcarusStage.SUBMITTING || state.stage == IcarusStage.EXECUTING || state.stage == IcarusStage.VERIFYING) {
            CancelButton(
                onClick = onCancel,
                modifier = Modifier.padding(16.dp)
            )
        } else if (state.stage == IcarusStage.PASS || state.stage == IcarusStage.FAILED || state.stage == IcarusStage.BLOCKED) {
            NewTaskButton(
                onClick = onNewTask,
                modifier = Modifier.padding(16.dp)
            )
        }
    }
}

@Composable
fun VoiceButton(
    text: String,
    onClick: () -> Unit,
    modifier: Modifier = Modifier
) {
    Button(
        onClick = onClick,
        modifier = modifier,
        shape = RoundedCornerShape(8.dp),
        colors = ButtonDefaults.buttonColors(
            containerColor = MaterialTheme.colorScheme.primary,
            contentColor = MaterialTheme.colorScheme.onPrimary
        )
    ) {
        Text(text = text)
    }
}

@Composable
fun OutlinedTextField(
    value: String,
    onValueChange: (String) -> Unit,
    placeholder: @Composable () -> Unit,
    modifier: Modifier = Modifier
) {
    OutlinedTextField(
        value = value,
        onValueChange = onValueChange,
        placeholder = placeholder,
        modifier = modifier
    )
}

@Composable
fun SubmitButton(
    onClick: () -> Unit,
    modifier: Modifier = Modifier
) {
    Button(
        onClick = onClick,
        modifier = modifier,
        shape = RoundedCornerShape(8.dp),
        colors = ButtonDefaults.buttonColors(
            containerColor = MaterialTheme.colorScheme.primary,
            contentColor = MaterialTheme.colorScheme.onPrimary
        )
    ) {
        Text(text = "Submit")
    }
}

@Composable
fun ResultSection(
    result: String,
    modifier: Modifier = Modifier
) {
    if (result.isNotBlank()) {
        Text(
            text = result,
            style = TextStyle(fontSize = 24.sp, fontWeight = FontWeight.Bold),
            modifier = modifier
        )
    }
}

@Composable
fun ProofEvidenceSection(
    proof: List<String>,
    modifier: Modifier = Modifier
) {
    if (proof.isNotEmpty()) {
        Column(modifier = modifier) {
            proof.forEachIndexed { index, text ->
                Text(
                    text = "$index. $text",
                    style = TextStyle(fontSize = 16.sp),
                    modifier = Modifier.padding(8.dp)
                )
            }
        }
    }
}

@Composable
fun ErrorText(
    error: String,
    modifier: Modifier = Modifier
) {
    if (error.isNotBlank()) {
        Text(
            text = error,
            style = TextStyle(fontSize = 16.sp, color = MaterialTheme.colorScheme.error),
            modifier = modifier
        )
    }
}

@Composable
fun CancelButton(
    onClick: () -> Unit,
    modifier:
