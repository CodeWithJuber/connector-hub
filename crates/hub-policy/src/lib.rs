mod grants;
mod ledger;
mod mutation_class;
mod policy;

pub use grants::{Effect, Grant, GrantDecision};
pub use ledger::{AuditEntry, AuditLedger};
pub use mutation_class::MutationClass;
pub use policy::Policy;

#[derive(Debug, thiserror::Error)]
pub enum PolicyError {
    #[error("permission denied: provider={provider} operation={operation} reason={reason}")]
    Denied {
        provider: String,
        operation: String,
        reason: String,
    },
    #[error("policy file error: {0}")]
    FileError(String),
    #[error("invalid policy: {0}")]
    Invalid(String),
}
