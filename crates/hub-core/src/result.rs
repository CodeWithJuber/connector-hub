use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(tag = "state")]
pub enum ExecutionOutcome {
    #[serde(rename = "succeeded")]
    Succeeded {
        executed: bool,
        data: serde_json::Value,
    },
    #[serde(rename = "dry_run")]
    DryRun {
        would_execute: String,
        mutation_class: String,
    },
    #[serde(rename = "configuration_required")]
    ConfigurationRequired {
        provider: String,
        missing: Vec<String>,
    },
    #[serde(rename = "permission_denied")]
    PermissionDenied {
        provider: String,
        operation: String,
        reason: String,
    },
    #[serde(rename = "confirmation_required")]
    ConfirmationRequired {
        provider: String,
        operation: String,
        token_format: String,
    },
    #[serde(rename = "upstream_failure")]
    UpstreamFailure {
        provider: String,
        status: Option<u16>,
        error: String,
    },
}

impl ExecutionOutcome {
    pub fn is_success(&self) -> bool {
        matches!(self, Self::Succeeded { executed: true, .. })
    }

    pub fn executed(&self) -> bool {
        matches!(self, Self::Succeeded { executed: true, .. })
    }
}

#[derive(Debug, thiserror::Error)]
pub enum OperationError {
    #[error("unknown operation: {0}")]
    UnknownOperation(String),
    #[error("invalid arguments: {0}")]
    InvalidArguments(String),
    #[error("network error: {0}")]
    Network(#[from] hub_net::NetError),
    #[error("auth error: {0}")]
    Auth(#[from] hub_auth::AuthError),
    #[error("policy denied: {0}")]
    Policy(#[from] hub_policy::PolicyError),
}
