use std::collections::HashMap;
use std::sync::Arc;
use std::time::{SystemTime, UNIX_EPOCH};

use tokio::sync::RwLock;

use crate::AuthError;
use crate::credential::{AuthMethod, Credential};

#[derive(Clone)]
struct CachedToken {
    access_token: String,
    expires_at: u64,
}

impl CachedToken {
    fn is_expired(&self) -> bool {
        let now = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .unwrap_or_default()
            .as_secs();
        now >= self.expires_at.saturating_sub(60)
    }
}

pub struct ResolvedAuth {
    pub headers: HashMap<String, String>,
    pub base_url: String,
}

pub struct AuthStore {
    credentials: HashMap<(String, String), Credential>,
    token_cache: Arc<RwLock<HashMap<(String, String), CachedToken>>>,
    http: reqwest::Client,
}

impl AuthStore {
    pub fn new() -> Self {
        Self {
            credentials: HashMap::new(),
            token_cache: Arc::new(RwLock::new(HashMap::new())),
            http: reqwest::Client::builder()
                .timeout(std::time::Duration::from_secs(30))
                .build()
                .expect("failed to build HTTP client for auth"),
        }
    }

    pub fn add(&mut self, credential: Credential) {
        let key = (credential.provider.clone(), credential.account_id.clone());
        self.credentials.insert(key, credential);
    }

    pub fn get(&self, provider: &str, account: Option<&str>) -> Result<Credential, AuthError> {
        let account_id = account.unwrap_or("default");
        let key = (provider.to_string(), account_id.to_string());

        self.credentials
            .get(&key)
            .cloned()
            .ok_or(AuthError::NotFound {
                provider: provider.to_string(),
                account: account_id.to_string(),
            })
    }

    pub async fn resolve(
        &self,
        provider: &str,
        account: Option<&str>,
    ) -> Result<ResolvedAuth, AuthError> {
        let cred = self.get(provider, account)?;
        let base_url = cred.base_url.clone().unwrap_or_default();
        let mut headers = HashMap::new();

        match &cred.auth {
            AuthMethod::Bearer { token } => {
                headers.insert("Authorization".into(), format!("Bearer {token}"));
            }
            AuthMethod::Header { name, value } => {
                headers.insert(name.clone(), value.clone());
            }
            AuthMethod::Basic { username, password } => {
                let encoded = base64_encode(format!("{username}:{password}").as_bytes());
                headers.insert("Authorization".into(), format!("Basic {encoded}"));
            }
            AuthMethod::OAuth2 {
                client_id,
                client_secret,
                refresh_token,
                token_url,
                ..
            } => {
                let key = (
                    provider.to_string(),
                    account.unwrap_or("default").to_string(),
                );
                let access_token = self
                    .get_or_refresh_oauth2(
                        &key,
                        client_id,
                        client_secret,
                        refresh_token,
                        token_url,
                        provider,
                    )
                    .await?;
                headers.insert("Authorization".into(), format!("Bearer {access_token}"));
            }
            AuthMethod::PasswordGrant {
                client_id,
                client_secret,
                username,
                password,
                token_url,
            } => {
                let key = (
                    provider.to_string(),
                    account.unwrap_or("default").to_string(),
                );
                let access_token = self
                    .get_or_refresh_password_grant(
                        &key,
                        client_id,
                        client_secret,
                        username,
                        password,
                        token_url,
                        provider,
                    )
                    .await?;
                headers.insert("Authorization".into(), format!("Bearer {access_token}"));
            }
            AuthMethod::Hmac {
                app_key,
                consumer_key,
                ..
            } => {
                headers.insert("X-Ovh-Application".into(), app_key.clone());
                headers.insert("X-Ovh-Consumer".into(), consumer_key.clone());
            }
            AuthMethod::Smtp { .. } => {
                // SMTP auth is handled by the mail transport, not via HTTP headers
            }
        }

        Ok(ResolvedAuth { headers, base_url })
    }

    async fn get_or_refresh_oauth2(
        &self,
        key: &(String, String),
        client_id: &str,
        client_secret: &str,
        refresh_token: &str,
        token_url: &str,
        provider: &str,
    ) -> Result<String, AuthError> {
        {
            let cache = self.token_cache.read().await;
            if let Some(cached) = cache.get(key)
                && !cached.is_expired()
            {
                return Ok(cached.access_token.clone());
            }
        }

        tracing::info!(provider, "refreshing OAuth2 access token");

        let token = self
            .request_token(
                token_url,
                &[
                    ("grant_type", "refresh_token"),
                    ("client_id", client_id),
                    ("client_secret", client_secret),
                    ("refresh_token", refresh_token),
                ],
                provider,
            )
            .await?;

        let mut cache = self.token_cache.write().await;
        cache.insert(key.clone(), token.clone());
        Ok(token.access_token)
    }

    #[allow(clippy::too_many_arguments)]
    async fn get_or_refresh_password_grant(
        &self,
        key: &(String, String),
        client_id: &str,
        client_secret: &str,
        username: &str,
        password: &str,
        token_url: &str,
        provider: &str,
    ) -> Result<String, AuthError> {
        {
            let cache = self.token_cache.read().await;
            if let Some(cached) = cache.get(key)
                && !cached.is_expired()
            {
                return Ok(cached.access_token.clone());
            }
        }

        tracing::info!(provider, "refreshing password grant access token");

        let token = self
            .request_token(
                token_url,
                &[
                    ("grant_type", "password"),
                    ("client_id", client_id),
                    ("client_secret", client_secret),
                    ("username", username),
                    ("password", password),
                ],
                provider,
            )
            .await?;

        let mut cache = self.token_cache.write().await;
        cache.insert(key.clone(), token.clone());
        Ok(token.access_token)
    }

    async fn request_token(
        &self,
        token_url: &str,
        params: &[(&str, &str)],
        provider: &str,
    ) -> Result<CachedToken, AuthError> {
        let resp = self
            .http
            .post(token_url)
            .form(params)
            .send()
            .await
            .map_err(|e| AuthError::RefreshFailed {
                provider: provider.into(),
                reason: e.to_string(),
            })?;

        if !resp.status().is_success() {
            let status = resp.status().as_u16();
            let body = resp.text().await.unwrap_or_default();
            return Err(AuthError::RefreshFailed {
                provider: provider.into(),
                reason: format!("token endpoint returned {status}: {body}"),
            });
        }

        let body: serde_json::Value = resp.json().await.map_err(|e| AuthError::RefreshFailed {
            provider: provider.into(),
            reason: format!("invalid token response: {e}"),
        })?;

        let access_token = body
            .get("access_token")
            .and_then(|v| v.as_str())
            .ok_or_else(|| AuthError::RefreshFailed {
                provider: provider.into(),
                reason: "no access_token in response".into(),
            })?
            .to_string();

        let expires_in = body
            .get("expires_in")
            .and_then(|v| v.as_u64())
            .unwrap_or(3600);

        let expires_at = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .unwrap_or_default()
            .as_secs()
            + expires_in;

        Ok(CachedToken {
            access_token,
            expires_at,
        })
    }

    pub fn list_accounts(&self, provider: &str) -> Vec<&str> {
        self.credentials
            .keys()
            .filter(|(p, _)| p == provider)
            .map(|(_, a)| a.as_str())
            .collect()
    }

    pub fn providers(&self) -> Vec<&str> {
        let mut providers: Vec<&str> = self
            .credentials
            .keys()
            .map(|(p, _)| p.as_str())
            .collect::<std::collections::HashSet<_>>()
            .into_iter()
            .collect();
        providers.sort();
        providers
    }

    pub fn from_env() -> Self {
        let mut store = Self::new();

        if let Ok(token) = std::env::var("HETZNER_API_TOKEN") {
            store.add(Credential {
                provider: "hetzner".into(),
                account_id: "default".into(),
                base_url: Some("https://api.hetzner.cloud/v1".into()),
                auth: AuthMethod::Bearer { token },
            });
        }

        if let Ok(token) = std::env::var("GITHUB_TOKEN") {
            store.add(Credential {
                provider: "github".into(),
                account_id: "default".into(),
                base_url: Some("https://api.github.com".into()),
                auth: AuthMethod::Bearer { token },
            });
        }

        if let Ok(key) = std::env::var("OPENAI_API_KEY") {
            store.add(Credential {
                provider: "openai".into(),
                account_id: "default".into(),
                base_url: Some("https://api.openai.com/v1".into()),
                auth: AuthMethod::Bearer { token: key },
            });
        }

        if let Ok(key) = std::env::var("ANTHROPIC_API_KEY") {
            store.add(Credential {
                provider: "anthropic".into(),
                account_id: "default".into(),
                base_url: Some("https://api.anthropic.com/v1".into()),
                auth: AuthMethod::Header {
                    name: "x-api-key".into(),
                    value: key,
                },
            });
        }

        let gmail_client_id = std::env::var("GMAIL_CLIENT_ID").ok();
        let gmail_client_secret = std::env::var("GMAIL_CLIENT_SECRET").ok();

        if let (Some(client_id), Some(client_secret)) = (gmail_client_id, gmail_client_secret) {
            if let Ok(token) = std::env::var("GMAIL_REFRESH_TOKEN") {
                store.add(Credential {
                    provider: "gmail".into(),
                    account_id: "default".into(),
                    base_url: Some("https://gmail.googleapis.com".into()),
                    auth: AuthMethod::OAuth2 {
                        client_id: client_id.clone(),
                        client_secret: client_secret.clone(),
                        refresh_token: token,
                        token_url: "https://oauth2.googleapis.com/token".into(),
                        scopes: vec![],
                        access_token: None,
                        expires_at: None,
                    },
                });
            }

            for (key, val) in std::env::vars() {
                if let Some(label) = key
                    .strip_prefix("GMAIL_REFRESH_TOKEN_")
                    .filter(|l| !l.is_empty())
                {
                    store.add(Credential {
                        provider: "gmail".into(),
                        account_id: label.to_lowercase(),
                        base_url: Some("https://gmail.googleapis.com".into()),
                        auth: AuthMethod::OAuth2 {
                            client_id: client_id.clone(),
                            client_secret: client_secret.clone(),
                            refresh_token: val,
                            token_url: "https://oauth2.googleapis.com/token".into(),
                            scopes: vec![],
                            access_token: None,
                            expires_at: None,
                        },
                    });
                }
            }
        }

        // Linode
        if let Ok(token) = std::env::var("LINODE_API_TOKEN") {
            store.add(Credential {
                provider: "linode".into(),
                account_id: "default".into(),
                base_url: Some("https://api.linode.com/v4".into()),
                auth: AuthMethod::Bearer { token },
            });
        }

        // Kimi (Moonshot)
        if let Ok(key) =
            std::env::var("MOONSHOT_API_KEY").or_else(|_| std::env::var("KIMI_API_KEY"))
        {
            let base = std::env::var("MOONSHOT_BASE_URL")
                .unwrap_or_else(|_| "https://api.moonshot.cn/v1".into());
            store.add(Credential {
                provider: "kimi".into(),
                account_id: "default".into(),
                base_url: Some(base),
                auth: AuthMethod::Bearer { token: key },
            });
        }

        // Cloudflare AI
        if let (Ok(token), Ok(account_id)) = (
            std::env::var("CLOUDFLARE_API_TOKEN"),
            std::env::var("CLOUDFLARE_ACCOUNT_ID"),
        ) {
            store.add(Credential {
                provider: "cloudflare".into(),
                account_id: "default".into(),
                base_url: Some(format!(
                    "https://api.cloudflare.com/client/v4/accounts/{account_id}"
                )),
                auth: AuthMethod::Bearer { token },
            });
        }

        // OneProvider
        if let Ok(key) = std::env::var("ONEPROVIDER_API_KEY") {
            store.add(Credential {
                provider: "oneprovider".into(),
                account_id: "default".into(),
                base_url: Some("https://api.oneprovider.com".into()),
                auth: AuthMethod::Bearer { token: key },
            });
        }

        // Tawk.to
        if let Ok(key) = std::env::var("TAWK_API_KEY") {
            store.add(Credential {
                provider: "tawk".into(),
                account_id: "default".into(),
                base_url: Some("https://api.tawk.to/v1".into()),
                auth: AuthMethod::Bearer { token: key },
            });
        }

        // WHM
        if let (Ok(host), Ok(user), Ok(token)) = (
            std::env::var("WHM_HOST"),
            std::env::var("WHM_USER"),
            std::env::var("WHM_API_TOKEN"),
        ) {
            store.add(Credential {
                provider: "whm".into(),
                account_id: "default".into(),
                base_url: Some(format!("https://{host}:2087")),
                auth: AuthMethod::Header {
                    name: "Authorization".into(),
                    value: format!("whm {user}:{token}"),
                },
            });
        }

        // cPanel
        if let (Ok(host), Ok(user), Ok(token)) = (
            std::env::var("CPANEL_HOST"),
            std::env::var("CPANEL_USER"),
            std::env::var("CPANEL_API_TOKEN"),
        ) {
            store.add(Credential {
                provider: "cpanel".into(),
                account_id: "default".into(),
                base_url: Some(format!("https://{host}:2083")),
                auth: AuthMethod::Header {
                    name: "Authorization".into(),
                    value: format!("cpanel {user}:{token}"),
                },
            });
        }

        // WHMCS
        if let (Ok(url), Ok(identifier), Ok(secret)) = (
            std::env::var("WHMCS_URL"),
            std::env::var("WHMCS_API_IDENTIFIER"),
            std::env::var("WHMCS_API_SECRET"),
        ) {
            store.add(Credential {
                provider: "whmcs".into(),
                account_id: "default".into(),
                base_url: Some(format!("{}/includes/api.php", url.trim_end_matches('/'))),
                auth: AuthMethod::Basic {
                    username: identifier,
                    password: secret,
                },
            });
        }

        // UltaHost (WHMCS billing)
        if let (Ok(url), Ok(user), Ok(key)) = (
            std::env::var("ULTRAHOST_WHMCS_URL"),
            std::env::var("ULTRAHOST_API_USER"),
            std::env::var("ULTRAHOST_API_KEY"),
        ) {
            store.add(Credential {
                provider: "ultrahost".into(),
                account_id: "default".into(),
                base_url: Some(url),
                auth: AuthMethod::Basic {
                    username: user,
                    password: key,
                },
            });
        }

        // Claude/Anthropic auth is already registered above under "anthropic".
        // The spec file is named "claude.json" so the provider is "claude".
        // We need a mapping from "claude" to the anthropic credentials.
        if let Ok(key) = std::env::var("ANTHROPIC_API_KEY") {
            store.add(Credential {
                provider: "claude".into(),
                account_id: "default".into(),
                base_url: Some("https://api.anthropic.com/v1".into()),
                auth: AuthMethod::Header {
                    name: "x-api-key".into(),
                    value: key,
                },
            });
        }

        // Contabo password grant
        if let (Ok(client_id), Ok(client_secret), Ok(username), Ok(password)) = (
            std::env::var("CONTABO_CLIENT_ID"),
            std::env::var("CONTABO_CLIENT_SECRET"),
            std::env::var("CONTABO_USERNAME"),
            std::env::var("CONTABO_PASSWORD"),
        ) {
            store.add(Credential {
                provider: "contabo".into(),
                account_id: "default".into(),
                base_url: Some("https://api.contabo.com/v1".into()),
                auth: AuthMethod::PasswordGrant {
                    client_id,
                    client_secret,
                    username,
                    password,
                    token_url:
                        "https://auth.contabo.com/auth/realms/contabo/protocol/openid-connect/token"
                            .into(),
                },
            });
        }

        // OVH HMAC
        if let (Ok(app_key), Ok(app_secret), Ok(consumer_key)) = (
            std::env::var("OVH_APP_KEY"),
            std::env::var("OVH_APP_SECRET"),
            std::env::var("OVH_CONSUMER_KEY"),
        ) {
            store.add(Credential {
                provider: "ovh".into(),
                account_id: "default".into(),
                base_url: Some("https://api.ovh.com/1.0".into()),
                auth: AuthMethod::Hmac {
                    app_key,
                    app_secret,
                    consumer_key,
                },
            });
        }

        // SMTP email accounts: EMAIL_SMTP_HOST, EMAIL_SMTP_PORT, EMAIL_SMTP_USER,
        // EMAIL_SMTP_PASS, EMAIL_SMTP_FROM, EMAIL_SMTP_TLS for default account.
        // EMAIL_SMTP_HOST_<LABEL> etc. for named accounts.
        if let (Ok(host), Ok(user), Ok(pass), Ok(from)) = (
            std::env::var("EMAIL_SMTP_HOST"),
            std::env::var("EMAIL_SMTP_USER"),
            std::env::var("EMAIL_SMTP_PASS"),
            std::env::var("EMAIL_SMTP_FROM"),
        ) {
            let port = std::env::var("EMAIL_SMTP_PORT")
                .ok()
                .and_then(|p| p.parse().ok())
                .unwrap_or(587);
            let tls = std::env::var("EMAIL_SMTP_TLS")
                .map(|v| v != "0" && v.to_lowercase() != "false")
                .unwrap_or(true);
            store.add(Credential {
                provider: "email".into(),
                account_id: "default".into(),
                base_url: None,
                auth: AuthMethod::Smtp {
                    host,
                    port,
                    username: user,
                    password: pass,
                    tls,
                    from_address: from,
                },
            });
        }

        for (key, host) in std::env::vars() {
            if let Some(label) = key
                .strip_prefix("EMAIL_SMTP_HOST_")
                .filter(|l| !l.is_empty())
            {
                let label_upper = label.to_uppercase();
                let user = std::env::var(format!("EMAIL_SMTP_USER_{label_upper}")).ok();
                let pass = std::env::var(format!("EMAIL_SMTP_PASS_{label_upper}")).ok();
                let from = std::env::var(format!("EMAIL_SMTP_FROM_{label_upper}")).ok();
                if let (Some(user), Some(pass), Some(from)) = (user, pass, from) {
                    let port = std::env::var(format!("EMAIL_SMTP_PORT_{label_upper}"))
                        .ok()
                        .and_then(|p| p.parse().ok())
                        .unwrap_or(587);
                    let tls = std::env::var(format!("EMAIL_SMTP_TLS_{label_upper}"))
                        .map(|v| v != "0" && v.to_lowercase() != "false")
                        .unwrap_or(true);
                    store.add(Credential {
                        provider: "email".into(),
                        account_id: label.to_lowercase(),
                        base_url: None,
                        auth: AuthMethod::Smtp {
                            host,
                            port,
                            username: user,
                            password: pass,
                            tls,
                            from_address: from,
                        },
                    });
                }
            }
        }

        store
    }
}

impl Default for AuthStore {
    fn default() -> Self {
        Self::new()
    }
}

fn base64_encode(input: &[u8]) -> String {
    const CHARS: &[u8] = b"ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";
    let mut result = String::new();
    for chunk in input.chunks(3) {
        let b0 = chunk[0] as u32;
        let b1 = chunk.get(1).copied().unwrap_or(0) as u32;
        let b2 = chunk.get(2).copied().unwrap_or(0) as u32;
        let triple = (b0 << 16) | (b1 << 8) | b2;
        result.push(CHARS[((triple >> 18) & 0x3F) as usize] as char);
        result.push(CHARS[((triple >> 12) & 0x3F) as usize] as char);
        if chunk.len() > 1 {
            result.push(CHARS[((triple >> 6) & 0x3F) as usize] as char);
        } else {
            result.push('=');
        }
        if chunk.len() > 2 {
            result.push(CHARS[(triple & 0x3F) as usize] as char);
        } else {
            result.push('=');
        }
    }
    result
}
