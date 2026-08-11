use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Credential {
    pub provider: String,
    pub account_id: String,
    pub base_url: Option<String>,
    #[serde(flatten)]
    pub auth: AuthMethod,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(tag = "auth_type")]
pub enum AuthMethod {
    #[serde(rename = "bearer")]
    Bearer { token: String },
    #[serde(rename = "basic")]
    Basic { username: String, password: String },
    #[serde(rename = "header")]
    Header { name: String, value: String },
    #[serde(rename = "oauth2")]
    OAuth2 {
        client_id: String,
        client_secret: String,
        refresh_token: String,
        token_url: String,
        #[serde(default)]
        scopes: Vec<String>,
        #[serde(skip_serializing_if = "Option::is_none")]
        access_token: Option<String>,
        #[serde(skip_serializing_if = "Option::is_none")]
        expires_at: Option<u64>,
    },
    #[serde(rename = "hmac")]
    Hmac {
        app_key: String,
        app_secret: String,
        consumer_key: String,
    },
    #[serde(rename = "password_grant")]
    PasswordGrant {
        client_id: String,
        client_secret: String,
        username: String,
        password: String,
        token_url: String,
    },
}
