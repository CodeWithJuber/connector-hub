use serde_json::Value;
use std::collections::HashMap;

use crate::NetError;
use crate::ssrf::SsrfPolicy;

pub struct NetClient {
    policy: SsrfPolicy,
    timeout_secs: u64,
}

impl NetClient {
    pub fn new(policy: SsrfPolicy) -> Self {
        Self {
            policy,
            timeout_secs: 30,
        }
    }

    pub fn with_timeout(mut self, secs: u64) -> Self {
        self.timeout_secs = secs;
        self
    }

    pub fn policy(&self) -> &SsrfPolicy {
        &self.policy
    }

    pub async fn execute(
        &self,
        method: &str,
        url: &str,
        _args: &Value,
        _headers: &HashMap<String, String>,
        provider: &str,
    ) -> Result<Value, NetError> {
        let _target = self.policy.validate_url(url)?;

        tracing::debug!(provider, method, url, "executing operation");

        // TODO: actual HTTP execution with IP pinning, retries, and streaming bounds
        Ok(serde_json::json!({
            "error": "HTTP execution not yet implemented",
            "provider": provider,
            "method": method,
            "url": url
        }))
    }
}
