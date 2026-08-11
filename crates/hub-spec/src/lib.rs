mod discovery;
mod openapi;

pub use discovery::GoogleDiscoverySpec;
pub use openapi::OpenApiSpec;

#[derive(Debug, thiserror::Error)]
pub enum SpecError {
    #[error("spec parse error: {0}")]
    Parse(String),
    #[error("unsupported spec format: {0}")]
    UnsupportedFormat(String),
    #[error("missing required field: {0}")]
    MissingField(String),
}

#[derive(Debug, Clone, serde::Serialize, serde::Deserialize)]
pub struct RawOperation {
    pub id: String,
    pub provider: String,
    pub summary: String,
    pub description: String,
    pub http_method: String,
    pub path: String,
    pub parameters: serde_json::Value,
    pub mutation_class: String,
    pub tags: Vec<String>,
}
