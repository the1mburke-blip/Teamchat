package com.icarus.shell

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.material.MaterialTheme
import androidx.lifecycle.lifecycleScope
import androidx.lifecycle.viewModelScope
import com.icarus.shell.ui.IcarusShellScreen
import com.icarus.shell.ui.IcarusShellRoute
import com.icarus.shell.ui.IcarusViewModel
import com.icarus.shell.ui.collectAsStateWithLifecycle
import com.icarus.shell.ui.onProblemChanged
import com.icarus.shell.ui.onVoiceToggle
import com.icarus.shell.ui.onSubmit
import com.icarus.shell.ui.onCancel
import com.icarus.shell.ui.onNewTask

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContent {
            MaterialTheme {
                IcarusShellRoute()
            }
        }
    }
}

@Composable
fun IcarusShellRoute(viewModel: IcarusViewModel = viewModel()) {
    val uiState by viewModel.uiState.collectAsStateWithLifecycle()

    IcarusShellScreen(
        onProblemChanged = { viewModel.onProblemChanged(it) },
        onVoiceToggle = { viewModel.onVoiceToggle() },
        onSubmit = { viewModel.onSubmit() },
        onCancel = { viewModel.onCancel() },
        onNewTask = { viewModel.onNewTask() },
        uiState = uiState
    )
}
