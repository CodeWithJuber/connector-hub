use std::collections::HashMap;

use crate::AuthError;
use crate::credential::Credential;

pub struct AuthStore {
    credentials: HashMap<(String, String), Credential>,
}

impl AuthStore {
    pub fn new() -> Self {
        Self {
            credentials: HashMap::new(),
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
                auth: crate::credential::AuthMethod::Bearer { token },
            });
        }

        if let Ok(token) = std::env::var("GITHUB_TOKEN") {
            store.add(Credential {
                provider: "github".into(),
                account_id: "default".into(),
                base_url: Some("https://api.github.com".into()),
                auth: crate::credential::AuthMethod::Bearer { token },
            });
        }

        if let Ok(key) = std::env::var("OPENAI_API_KEY") {
            store.add(Credential {
                provider: "openai".into(),
                account_id: "default".into(),
                base_url: Some("https://api.openai.com/v1".into()),
                auth: crate::credential::AuthMethod::Bearer { token: key },
            });
        }

        if let Ok(key) = std::env::var("ANTHROPIC_API_KEY") {
            store.add(Credential {
                provider: "anthropic".into(),
                account_id: "default".into(),
                base_url: Some("https://api.anthropic.com/v1".into()),
                auth: crate::credential::AuthMethod::Header {
                    name: "x-api-key".into(),
                    value: key,
                },
            });
        }

        // Gmail OAuth2 accounts: GMAIL_CLIENT_ID, GMAIL_CLIENT_SECRET, plus
        // GMAIL_REFRESH_TOKEN (default account) or GMAIL_REFRESH_TOKEN_<LABEL>
        // for named accounts.
        let gmail_client_id = std::env::var("GMAIL_CLIENT_ID").ok();
        let gmail_client_secret = std::env::var("GMAIL_CLIENT_SECRET").ok();

        if let (Some(client_id), Some(client_secret)) = (gmail_client_id, gmail_client_secret) {
            if let Ok(token) = std::env::var("GMAIL_REFRESH_TOKEN") {
                store.add(Credential {
                    provider: "gmail".into(),
                    account_id: "default".into(),
                    base_url: Some("https://gmail.googleapis.com/gmail/v1/users/me".into()),
                    auth: crate::credential::AuthMethod::OAuth2 {
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
                        base_url: Some("https://gmail.googleapis.com/gmail/v1/users/me".into()),
                        auth: crate::credential::AuthMethod::OAuth2 {
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

        store
    }
}

impl Default for AuthStore {
    fn default() -> Self {
        Self::new()
    }
}
