mod client;
pub mod mail;
mod redact;
mod ssrf;

pub use client::NetClient;
pub use redact::redact_secrets;
pub use ssrf::{SsrfPolicy, ValidatedTarget};

use std::net::IpAddr;

#[derive(Debug, thiserror::Error)]
pub enum NetError {
    #[error("SSRF blocked: {0}")]
    SsrfBlocked(String),
    #[error("non-public address blocked: {0}")]
    NonPublicAddress(IpAddr),
    #[error("cloud metadata endpoint blocked")]
    MetadataBlocked,
    #[error("redirect limit exceeded")]
    RedirectLimit,
    #[error("response too large: {size} bytes (limit {limit})")]
    ResponseTooLarge { size: usize, limit: usize },
    #[error("request timeout after {0}s")]
    Timeout(u64),
    #[error("DNS resolution failed for {host}: {reason}")]
    DnsFailure { host: String, reason: String },
    #[error("HTTP error {status}: {body}")]
    HttpError { status: u16, body: String },
    #[error("connection error: {0}")]
    Connection(String),
    #[error("invalid URL: {0}")]
    InvalidUrl(String),
}
