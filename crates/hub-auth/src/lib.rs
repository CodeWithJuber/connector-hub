pub mod credential;
mod store;

pub use credential::Credential;
pub use store::AuthStore;

#[derive(Debug, thiserror::Error)]
pub enum AuthError {
    #[error("no credential found for provider={provider} account={account}")]
    NotFound { provider: String, account: String },
    #[error("credential expired for provider={provider} account={account}")]
    Expired { provider: String, account: String },
    #[error("token refresh failed for {provider}: {reason}")]
    RefreshFailed { provider: String, reason: String },
    #[error("keychain error: {0}")]
    Keychain(String),
    #[error("encrypted store error: {0}")]
    EncryptedStore(String),
}
