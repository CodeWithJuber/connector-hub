use serde_json::Value;
use std::collections::HashMap;
use std::time::Duration;

use crate::NetError;
use crate::ssrf::SsrfPolicy;

/// The User-Agent every outbound request carries.
///
/// reqwest sends no User-Agent by default. GitHub rejects such requests
/// outright with `403 Request forbidden by administrative rules`, and several
/// WAF-fronted provider APIs do the same, so this is not cosmetic — without it
/// entire providers are unreachable no matter how good the credentials are.
const USER_AGENT: &str = concat!(
    "connector-hub/",
    env!("CARGO_PKG_VERSION"),
    " (+https://github.com/CodeWithJuber/connector-hub)"
);

fn build_client(timeout_secs: u64) -> reqwest::Client {
    reqwest::Client::builder()
        .timeout(Duration::from_secs(timeout_secs))
        .redirect(reqwest::redirect::Policy::none())
        .user_agent(USER_AGENT)
        .build()
        .expect("failed to build HTTP client")
}

pub struct NetClient {
    policy: SsrfPolicy,
    timeout_secs: u64,
    client: reqwest::Client,
}

impl NetClient {
    pub fn new(policy: SsrfPolicy) -> Self {
        let client = build_client(30);

        Self {
            policy,
            timeout_secs: 30,
            client,
        }
    }

    pub fn with_timeout(mut self, secs: u64) -> Self {
        self.timeout_secs = secs;
        self.client = build_client(secs);
        self
    }

    pub fn policy(&self) -> &SsrfPolicy {
        &self.policy
    }

    pub async fn execute(
        &self,
        method: &str,
        url: &str,
        args: &Value,
        headers: &HashMap<String, String>,
        provider: &str,
    ) -> Result<Value, NetError> {
        let target = self.policy.validate_url(url)?;

        tracing::debug!(provider, method, url = target.url, "executing operation");

        let reqwest_method = method
            .parse::<reqwest::Method>()
            .map_err(|e| NetError::InvalidUrl(format!("invalid method: {e}")))?;

        let mut request = self.client.request(reqwest_method.clone(), &target.url);

        // Apply auth/custom headers
        for (name, value) in headers {
            request = request.header(name.as_str(), value.as_str());
        }

        // For methods that take a body, send args as JSON
        match method.to_uppercase().as_str() {
            "POST" | "PUT" | "PATCH" if !args.is_null() => {
                request = request
                    .header("Content-Type", "application/json")
                    .json(args);
            }
            "POST" | "PUT" | "PATCH" => {}
            "GET" | "HEAD" | "DELETE" => {
                // GET/HEAD/DELETE: if args has query-like params, append as query string
                if let Some(obj) = args.as_object() {
                    let query_params: Vec<(String, String)> = obj
                        .iter()
                        .filter_map(|(k, v)| {
                            let val = match v {
                                Value::String(s) => Some(s.clone()),
                                Value::Number(n) => Some(n.to_string()),
                                Value::Bool(b) => Some(b.to_string()),
                                _ => None,
                            };
                            val.map(|v| (k.clone(), v))
                        })
                        .collect();
                    if !query_params.is_empty() {
                        request = request.query(&query_params);
                    }
                }
            }
            _ => {}
        }

        let response = request.send().await.map_err(|e| {
            if e.is_timeout() {
                NetError::Timeout(self.timeout_secs)
            } else {
                NetError::Connection(e.to_string())
            }
        })?;

        let status = response.status().as_u16();

        // Enforce response size limit
        if let Some(len) = response.content_length()
            && len > self.policy.max_response_bytes as u64
        {
            return Err(NetError::ResponseTooLarge {
                size: len as usize,
                limit: self.policy.max_response_bytes,
            });
        }

        let bytes = response
            .bytes()
            .await
            .map_err(|e| NetError::Connection(e.to_string()))?;

        if bytes.len() > self.policy.max_response_bytes {
            return Err(NetError::ResponseTooLarge {
                size: bytes.len(),
                limit: self.policy.max_response_bytes,
            });
        }

        if status >= 400 {
            let body = String::from_utf8_lossy(&bytes).to_string();
            return Err(NetError::HttpError { status, body });
        }

        // Try to parse as JSON, fall back to wrapping raw text
        let value: Value = serde_json::from_slice(&bytes).unwrap_or_else(|_| {
            serde_json::json!({
                "raw_response": String::from_utf8_lossy(&bytes).to_string()
            })
        });

        Ok(value)
    }
}
