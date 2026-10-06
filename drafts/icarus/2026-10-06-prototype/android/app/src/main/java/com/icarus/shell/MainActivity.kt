package com.aistudio.icarus.appsscript

import android.os.Bundle
import android.app.Activity
import androidx.compose.ui.platform.LocalContext
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.material3.MaterialTheme
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContent { MaterialTheme { IcarusShellRoute() } }
    }
}

@Composable
fun IcarusShellRoute(viewModel: IcarusViewModel = viewModel()) {
    val state by viewModel.uiState.collectAsStateWithLifecycle()
    val activity = LocalContext.current as Activity
    IcarusShellScreen(
        state = state,
        onBackendUrlChanged = viewModel::onBackendUrlChanged,
        onDeviceIdChanged = viewModel::onDeviceIdChanged,
        onRecoveryTokenChanged = viewModel::onRecoveryTokenChanged,
        onRecover = viewModel::recover,
        onGoogleConnect = { viewModel.connectWithGoogle(activity) },
        onProblemChanged = viewModel::onProblemChanged,
        onVoiceToggle = viewModel::onVoiceToggle,
        onSubmit = viewModel::submit,
        onCancel = viewModel::cancel,
        onNewTask = viewModel::newTask,
        onRefresh = viewModel::refreshTask
    )
}
