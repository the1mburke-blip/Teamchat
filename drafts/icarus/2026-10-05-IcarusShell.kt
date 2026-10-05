package com.icarus.shell

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.Button
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsStateWithLifecycle
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.unit.dp

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContent { MaterialTheme { IcarusShellRoute() } }
    }
}

@Composable
fun IcarusShellRoute(viewModel: IcarusViewModel = viewModel()) {
    val uiState by viewModel.uiState.collectAsStateWithLifecycle()

    Column(
        modifier = Modifier.fillMaxSize(),
        verticalArrangement = Alignment.CenterVertically,
        horizontalAlignment = Alignment.CenterHorizontally
    ) {
        Text(
            text = "ICARUS",
            style = TextStyle(fontSize = 48.sp, fontWeight = FontWeight.Bold),
            color = MaterialTheme.colorScheme.primary
        )

        val buttonLabel = if (uiState.listening) "Stop Listening" else "Start Listening"
        Button(
            onClick = { viewModel.toggleListening() },
            modifier = Modifier.padding(16.dp)
        ) {
            Text(text = buttonLabel)
        }

        OutlinedTextField(
            value = uiState.textFallback,
            onValueChange = { viewModel.updateTextFallback(it) },
            placeholder = { Text(text = "Enter text") },
            modifier = Modifier.padding(16.dp)
        )

        Button(
            onClick = { viewModel.submit() },
            modifier = Modifier.padding(16.dp)
        ) {
            Text(text = "Submit")
        }

        if (uiState.taskStage == TaskStage.PASS) {
            Text(
                text = "Task Passed",
                style = TextStyle(fontSize = 24.sp, fontWeight = FontWeight.Bold),
                color = MaterialTheme.colorScheme.success
            )
        } else if (uiState.taskStage == TaskStage.FAILED) {
            Text(
                text = "Task Failed",
                style = TextStyle(fontSize = 24.sp, fontWeight = FontWeight.Bold),
                color = MaterialTheme.colorScheme.error
            )
        } else if (uiState.taskStage == TaskStage.BLOCKED) {
            Text(
                text = "Task Blocked",
                style = TextStyle(fontSize = 24.sp, fontWeight = FontWeight.Bold),
                color = MaterialTheme.colorScheme.warning
            )
        }

        if (uiState.result.isNotEmpty()) {
            Text(
                text = uiState.result,
                style = TextStyle(fontSize = 24.sp),
                color = MaterialTheme.colorScheme.primary
            )
        }

        if (uiState.evidence.isNotEmpty()) {
            Text(
                text = "Evidence/Proofs",
                style = TextStyle(fontSize = 24.sp, fontWeight = FontWeight.Bold),
                color = MaterialTheme.colorScheme.primary
            )
            // Render evidence/proof list here
        }

        if (uiState.error.isNotEmpty()) {
            Text(
                text = uiState.error,
                style = TextStyle(fontSize = 24.sp, fontWeight = FontWeight.Bold),
                color = MaterialTheme.colorScheme.error
            )
        }

        if (uiState.isSubmitting || uiState.isExecuting || uiState.isVerifying) {
            Button(
                onClick = { viewModel.cancel() },
                modifier = Modifier.padding(16.dp)
            ) {
                Text(text = "Cancel")
            }
        }

        Button(
            onClick = { viewModel.newTask() },
            modifier = Modifier.padding(16.dp)
        ) {
            Text(text = "New Task")
        }
    }
}
